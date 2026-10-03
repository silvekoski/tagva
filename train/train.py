import argparse
import json
import time
from pathlib import Path

import yaml

FORBIDDEN = ("real-test", "real_test")


def split_paths(spec, base):
    items = spec if isinstance(spec, list) else [spec]
    return [str(p if Path(p).is_absolute() else (base / p).resolve()) for p in map(str, items)]


def dataset_base(yaml_path, data):
    root = data.get("path")
    if not root:
        return yaml_path.parent.resolve()
    root = Path(root)
    if root.is_absolute():
        return root
    return (yaml_path.parent / root).resolve() if (yaml_path.parent / root).exists() else root.resolve()


def load_part(yaml_path):
    data = yaml.safe_load(yaml_path.read_text())
    base = dataset_base(yaml_path, data)
    names = data.get("names")
    names = list(names.values()) if isinstance(names, dict) else list(names or [])
    return {"train": split_paths(data["train"], base), "val": split_paths(data["val"], base), "names": names}


def resolve_data(path):
    """A yaml file, DIR/data.yaml, or DIR with part folders (DIR/*/data.yaml), written to data-resolved.yaml."""
    p = Path(path)
    if p.is_file():
        yaml_paths, out_dir = [p], p.parent
    else:
        yaml_paths, out_dir = sorted(p.glob("*/data.yaml")) or sorted(p.glob("data.yaml")), p
    if not yaml_paths:
        raise SystemExit(f"no data.yaml in {p} or in its subfolders")
    parts = [load_part(y) for y in yaml_paths]
    names = parts[0]["names"]
    if len(names) != 1 or any(q["names"] != names for q in parts):
        raise SystemExit(f"expected one class with the same name in each part, got {[q['names'] for q in parts]}")
    data = {
        "train": [t for q in parts for t in q["train"]],
        "val": [v for q in parts for v in q["val"]],
        "names": {0: names[0]},
    }
    bad = [d for d in data["train"] + data["val"] if any(f in d for f in FORBIDDEN)]
    if bad:
        raise SystemExit(f"the real test crops must not be used for training or validation, got {bad}")
    missing = [d for d in data["train"] + data["val"] if not Path(d).exists()]
    if missing:
        raise SystemExit(f"missing dataset paths: {missing}")
    out = out_dir / "data-resolved.yaml"
    out.write_text(yaml.safe_dump(data, sort_keys=False))
    return out.resolve()


def time_cap(hours):
    def check(trainer):
        elapsed = time.time() - trainer.train_time_start
        done = trainer.epoch - trainer.start_epoch + 1
        if elapsed * (done + 1) / done > hours * 3600:
            trainer.stop = True
    return check


def main(argv=None):
    p = argparse.ArgumentParser(description="Train the one-class REX615 detector.")
    p.add_argument("--data", required=True, help="dataset DIR (with data.yaml or part folders) or a data.yaml")
    p.add_argument("--model", default="yolo26s.pt", choices=["yolo26s.pt", "yolo26m.pt", "yolo26n.pt", "yolo26n.yaml"])
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--name", required=True)
    p.add_argument("--project", default="runs")
    p.add_argument("--imgsz", type=int, default=1280)
    p.add_argument("--device", default=None)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--hours", type=float, default=0.9, help="stop before the next epoch passes this wall-clock budget (0: no budget)")
    p.add_argument("--patience", type=int, default=15)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args(argv)

    from ultralytics import YOLO

    data = resolve_data(a.data)
    model = YOLO(a.model)
    if a.hours > 0:
        model.add_callback("on_fit_epoch_end", time_cap(a.hours))
    model.train(
        data=str(data),
        imgsz=a.imgsz,
        epochs=a.epochs,
        batch=a.batch,
        project=str(Path(a.project).resolve()),
        name=a.name,
        exist_ok=True,
        fliplr=0.0,
        flipud=0.0,
        device=a.device,
        workers=a.workers,
        patience=a.patience,
        seed=a.seed,
    )
    save_dir = Path(model.trainer.save_dir)
    best = save_dir / "weights" / "best.pt"
    if not best.is_file():
        raise SystemExit(f"training finished without {best}")
    metrics = {k: round(float(v), 5) for k, v in (model.trainer.metrics or {}).items()}
    (save_dir / "summary.json").write_text(json.dumps({"best": str(best), "data": str(data), "metrics": metrics}, indent=2) + "\n")
    print(f"best: {best}")


if __name__ == "__main__":
    main()

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval import realtest  # noqa: E402
from pipeline.detect import Detector  # noqa: E402

THRESHOLDS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def load_test(test_dir):
    gt = json.loads((test_dir / "gt.json").read_text())
    by_tile = {}
    for b in gt["boxes"]:
        by_tile.setdefault(b["tile"], []).append(b)
    return gt["tiles"], [by_tile.get(t["name"], []) for t in gt["tiles"]]


def detect(detector, test_dir, tiles, dark_gain=None, batch=16):
    out = []
    for i in range(0, len(tiles), batch):
        images = [cv2.imread(str(test_dir / t["image"])) for t in tiles[i:i + batch]]
        if dark_gain:
            images = [realtest.darken(img, dark_gain, seed=i + k) for k, img in enumerate(images)]
        out += [[(tuple(float(v) for v in box), float(score)) for box, score in dets] for dets in detector(images)]
    return out


def fmt(v):
    return "-" if v is None else f"{v:.3f}"


def print_report(report, title):
    h = report["headline"]
    print(f"{title}: {h['targets']} target boxes, conf {h['conf']}")
    print(f"recall {fmt(h['recall'])}  precision {fmt(h['precision'])}  fp/tile {h['fp_per_tile']:.3f}  "
          f"fp {h['fp']} (on e2 {h['e2_detections']})")
    for name, b in h["recall_by_width"].items():
        print(f"  width {name:>7} px: {b['found']:4d} / {b['total']:4d}  recall {fmt(b['recall'])}")
    print(f"{'conf':>5} {'recall':>7} {'prec':>6} {'fp':>5} {'e2':>4} {'fp/tile':>8}")
    for row in report["sweep"]:
        print(f"{row['conf']:5.2f} {fmt(row['recall']):>7} {fmt(row['precision']):>6} {row['fp']:5d} "
              f"{row['e2_detections']:4d} {row['fp_per_tile']:8.3f}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--weights", required=True)
    p.add_argument("--conf", type=float, default=0.25)
    p.add_argument("--test", default=str(realtest.TEST_DIR))
    p.add_argument("--device", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--dark-gain", type=float, default=realtest.DARK_GAIN, help="exposure gain of the dark pass, 0 skips it")
    a = p.parse_args()
    test_dir, weights = Path(a.test), Path(a.weights)
    tiles, gts = load_test(test_dir)
    detector = Detector(weights, device=a.device, conf=min([a.conf] + THRESHOLDS))

    def run(dark_gain):
        dets = detect(detector, test_dir, tiles, dark_gain)
        return {
            "headline": realtest.score_tiles(dets, gts, a.conf),
            "sweep": [realtest.score_tiles(dets, gts, c) for c in THRESHOLDS],
            "detections": {t["name"]: [[round(v, 1) for v in box] + [round(s, 4)] for box, s in d] for t, d in zip(tiles, dets) if d},
        }

    report = {"weights": str(weights), "test": str(test_dir), "tiles": len(tiles), "iou": realtest.IOU_MATCH, **run(None)}
    if a.dark_gain:
        report["dark"] = {"gain": a.dark_gain, **run(a.dark_gain)}
    out = Path(a.out) if a.out else weights.with_name(f"{weights.stem}-real-eval.json")
    out.write_text(json.dumps(report, indent=1) + "\n")
    print_report(report, f"real test ({len(tiles)} tiles)")
    if "dark" in report:
        print_report(report["dark"], f"real test dark (gain {a.dark_gain})")
    print(f"report: {out}")


if __name__ == "__main__":
    main()

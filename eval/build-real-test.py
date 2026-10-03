import argparse
import json
import random
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval import realtest  # noqa: E402
from pipeline import sphere, tiles  # noqa: E402
from pipeline.ingest import sweep_id  # noqa: E402
from pipeline.scan import Scan  # noqa: E402

NEGATIVES = 60
SEED = 615
JPEG_QUALITY = 92


def tile_name(sid, spec):
    return f"{sid}-tile-{spec.index:02d}"


def tile_boxes(spec, sid, position, devices, visible, pano_w, pano_h):
    out = []
    for d in devices:
        xyxy = realtest.project_box(spec, position, d)
        if xyxy is None:
            continue
        clipped = realtest.clip(spec, xyxy)
        if clipped is None:
            continue
        angle = realtest.view_angle(position, d)
        if angle >= 90:
            continue
        los, fraction = visible[d["id"]]
        if not los and fraction < realtest.MIN_PARTIAL:
            continue
        if not los or fraction < realtest.MIN_VISIBLE:
            reason = "occluded"
        elif angle > realtest.MAX_VIEW_ANGLE:
            reason = "grazing"
        else:
            reason = None if realtest.inside(spec, xyxy) else "cut"
        box = clipped if reason else xyxy
        out.append({
            "tile": tile_name(sid, spec),
            "sweep": sid,
            "tile_index": spec.index,
            "device": d["id"],
            "target": d["target"],
            "ignore": reason is not None,
            "ignore_reason": reason,
            "xyxy": [round(v, 2) for v in box],
            "pano": [round(v, 2) for v in tiles.tile_box_to_pano(spec, box, pano_w, pano_h)],
            "width_px": round(box[2] - box[0], 2),
            "height_px": round(box[3] - box[1], 2),
            "visible_fraction": round(fraction, 2),
            "view_angle": round(angle, 1),
            "distance": round(float(np.linalg.norm(np.asarray(d["center"]) - position)), 3),
        })
    return out


def yolo_lines(spec, boxes):
    s = spec.size
    return [
        f"0 {(b[0] + b[2]) / 2 / s:.6f} {(b[1] + b[3]) / 2 / s:.6f} {(b[2] - b[0]) / s:.6f} {(b[3] - b[1]) / s:.6f}"
        for b in (g["xyxy"] for g in boxes if g["target"] and not g["ignore"])
    ]


def build(e57, scan_dir, out_dir):
    manifest = json.loads((scan_dir / "manifest.json").read_text())
    pano_w, pano_h = manifest["pano_width"], manifest["pano_height"]
    devices = realtest.load_devices()
    specs = tiles.tile_specs()
    scan = Scan(e57)
    positive, empty = {}, []
    for sweep in scan.sweeps:
        sid = sweep_id(sweep.index)
        grid = np.load(scan_dir / "depth" / f"{sid}.npz")["range"]
        visible = {d["id"]: realtest.visibility(grid, sweep.rotation, sweep.position, d) for d in devices}
        for spec in specs:
            boxes = tile_boxes(spec, sid, sweep.position, devices, visible, pano_w, pano_h)
            if any(not b["ignore"] for b in boxes):
                positive[(sweep.index, spec.index)] = boxes
            elif not boxes:
                empty.append((sweep.index, spec.index))
    negatives = sorted(random.Random(SEED).sample(empty, NEGATIVES))
    keep = sorted(set(positive) | set(negatives))

    for sub in ("images", "labels"):
        if (out_dir / sub).exists():
            shutil.rmtree(out_dir / sub)
    (out_dir / "gt.json").unlink(missing_ok=True)
    (out_dir / "images").mkdir(parents=True)
    (out_dir / "labels").mkdir()
    tile_rows = []
    for index in sorted({k[0] for k in keep}):
        faces = scan.faces(index)
        sid = sweep_id(index)
        for spec in (specs[t] for s, t in keep if s == index):
            name = tile_name(sid, spec)
            boxes = positive.get((index, spec.index), [])
            img = sphere.render_tile(faces, spec.yaw, spec.pitch, spec.fov, spec.size)
            cv2.imwrite(str(out_dir / "images" / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            lines = yolo_lines(spec, boxes)
            (out_dir / "labels" / f"{name}.txt").write_text("".join(line + "\n" for line in lines))
            tile_rows.append({
                "name": name,
                "image": f"images/{name}.jpg",
                "sweep": sid,
                "tile_index": spec.index,
                "yaw": spec.yaw,
                "pitch": spec.pitch,
                "negative": not boxes,
            })
        del faces
        print(sid, flush=True)
    all_boxes = [b for k in keep for b in positive.get(k, [])]
    gt = {
        "source": Path(e57).name,
        "pano_width": pano_w,
        "pano_height": pano_h,
        "tile_size": tiles.TILE_SIZE,
        "tile_fov_deg": float(np.degrees(tiles.TILE_FOV)),
        "devices": devices,
        "tiles": tile_rows,
        "boxes": all_boxes,
    }
    (out_dir / "gt.json").write_text(json.dumps(gt, indent=1) + "\n")
    kept = [b for b in all_boxes if not b["ignore"]]
    print(f"tiles {len(tile_rows)} ({len(negatives)} negative), boxes {len(kept)} "
          f"(targets {sum(b['target'] for b in kept)}), ignore {len(all_boxes) - len(kept)} "
          f"{dict(Counter(b['ignore_reason'] for b in all_boxes if b['ignore']))}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--e57", default=str(realtest.ROOT / "cloud_0.e57"))
    p.add_argument("--scan", default=str(realtest.ROOT / "data" / "scan"))
    p.add_argument("--out", default=str(realtest.TEST_DIR))
    a = p.parse_args()
    build(a.e57, Path(a.scan), Path(a.out))

import json
from pathlib import Path

import numpy as np

from pipeline import tiles
from pipeline.scan import local_dirs_to_grid

ROOT = Path(__file__).resolve().parents[1]
DEVICES = ROOT / "eval" / "real-devices.json"
TEST_DIR = ROOT / "data" / "real-test"
LOS_TOLERANCE = 0.05
LOS_TOLERANCE_PER_M = 0.01
MIN_VISIBLE = 0.75
MIN_PARTIAL = 0.25
MAX_VIEW_ANGLE = 75.0
IOU_MATCH = 0.5
IGNORE_OVERLAP = 0.5
ANCHOR_RADIUS = 0.3
DARK_GAIN = 0.05
DARK_GAMMA = 2.2
DARK_SHOT_NOISE = 0.001
DARK_READ_NOISE = 0.002
SIZE_BINS = [("<30", 0, 30), ("30-60", 30, 60), ("60-120", 60, 120), (">120", 120, float("inf"))]


def load_devices(path=DEVICES):
    return json.loads(Path(path).read_text())["devices"]


def plate_axes(device):
    n = np.asarray(device["normal"], float)
    n /= np.linalg.norm(n)
    r = np.cross(-n, [0.0, 0.0, 1.0])
    r /= np.linalg.norm(r)
    return n, r, np.cross(r, -n)


def plate_points(device, steps=(-0.5, 0.5)):
    """3D points on the plate front at the given fractions of width and height, row by row from the top."""
    _, r, u = plate_axes(device)
    c = np.asarray(device["center"], float)
    return np.array([c + a * device["width"] * r + b * device["height"] * u for b in steps[::-1] for a in steps])


def view_angle(position, device):
    """Degrees between the plate normal and the direction to the viewer."""
    n, _, _ = plate_axes(device)
    v = np.asarray(position, float) - np.asarray(device["center"], float)
    return float(np.degrees(np.arccos(np.clip(v @ n / np.linalg.norm(v), -1.0, 1.0))))


def range_margins(range_grid, rotation, position, points):
    """Depth grid range minus point distance for each point seen from position. NaN where the grid is empty."""
    v = points - position
    dist = np.linalg.norm(v, axis=1)
    row, col = local_dirs_to_grid((v / dist[:, None]) @ rotation)
    r = range_grid[row, col].astype(np.float64)
    return np.where(r > 0, r - dist, np.nan)


def visibility(range_grid, rotation, position, device):
    """(center has line of sight, visible fraction of the plate). The range tolerance grows with distance."""
    center = range_margins(range_grid, rotation, position, plate_points(device, np.linspace(-0.2, 0.2, 5)))
    whole = range_margins(range_grid, rotation, position, plate_points(device, np.linspace(-0.45, 0.45, 7)))
    tolerance = LOS_TOLERANCE + LOS_TOLERANCE_PER_M * float(np.linalg.norm(np.asarray(device["center"], float) - position))
    seen = whole[np.isfinite(whole)]
    fraction = float(np.mean(seen >= -tolerance)) if seen.size else 0.0
    center = center[np.isfinite(center)]
    return bool(center.size and np.median(center) >= -tolerance), fraction


def project_box(spec, position, device):
    """Tile box (x0, y0, x1, y1) of the plate corners, or None when a corner is behind the camera."""
    v = plate_points(device) - position
    x, y = tiles.dirs_to_tile_pixel(spec, v / np.linalg.norm(v, axis=1, keepdims=True))
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        return None
    return float(x.min()), float(y.min()), float(x.max()), float(y.max())


def inside(spec, xyxy):
    return xyxy[0] >= 0 and xyxy[1] >= 0 and xyxy[2] <= spec.size and xyxy[3] <= spec.size


def clip(spec, xyxy):
    x0, y0, x1, y1 = (min(max(v, 0.0), float(spec.size)) for v in xyxy)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection(a, b):
    return area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def iou(a, b):
    i = intersection(a, b)
    return i / max(area(a) + area(b) - i, 1e-9)


def size_bin(width):
    return next(name for name, lo, hi in SIZE_BINS if lo <= width < hi)


def darken(img, gain=DARK_GAIN, seed=0):
    """Low-light copy of a BGR uint8 image: exposure drop in linear light, shot and read noise, gamma back."""
    rng = np.random.default_rng(seed)
    lin = (img.astype(np.float32) / 255) ** DARK_GAMMA * gain
    noise = rng.standard_normal(img.shape, dtype=np.float32) * np.sqrt(DARK_SHOT_NOISE * lin + DARK_READ_NOISE ** 2)
    return (np.clip(lin + noise, 0, 1) ** (1 / DARK_GAMMA) * 255 + 0.5).astype(np.uint8)


def match_tile(dets, gts):
    """Match one tile. dets: list of (xyxy, score). gts: list of dicts with xyxy, device, target, ignore.

    Greedy by score: a detection takes the free non-ignore box with the best IoU >= IOU_MATCH.
    An unmatched detection that lies mostly inside an ignore region is dropped. Returns one
    outcome per detection ("tp", "e2", "fp", "ignored") with the matched gt index, in det order."""
    order = sorted(range(len(dets)), key=lambda i: -dets[i][1])
    taken = set()
    out = [None] * len(dets)
    for i in order:
        box = dets[i][0]
        best, best_iou = None, IOU_MATCH
        for j, g in enumerate(gts):
            if g["ignore"] or j in taken:
                continue
            o = iou(box, g["xyxy"])
            if o >= best_iou:
                best, best_iou = j, o
        if best is not None:
            taken.add(best)
            out[i] = ("tp" if gts[best]["target"] else "e2", best)
        elif any(g["ignore"] and intersection(box, g["xyxy"]) >= IGNORE_OVERLAP * area(box) for g in gts):
            out[i] = ("ignored", None)
        else:
            out[i] = ("fp", None)
    return out


def score_tiles(tile_dets, tile_gts, conf):
    """Counts over all tiles at one confidence threshold. fp includes the e2 detections."""
    bins = {name: [0, 0] for name, _, _ in SIZE_BINS}
    tp = fp = e2 = 0
    for dets, gts in zip(tile_dets, tile_gts):
        dets = [d for d in dets if d[1] >= conf]
        found = set()
        for kind, j in match_tile(dets, gts):
            if kind == "tp":
                tp += 1
                found.add(j)
            elif kind == "e2":
                e2 += 1
            elif kind == "fp":
                fp += 1
        for j, g in enumerate(gts):
            if g["target"] and not g["ignore"]:
                b = bins[size_bin(g["width_px"])]
                b[0] += j in found
                b[1] += 1
    targets = sum(b[1] for b in bins.values())
    return {
        "conf": conf,
        "tp": tp,
        "targets": targets,
        "recall": tp / targets if targets else None,
        "fp": fp + e2,
        "e2_detections": e2,
        "fp_per_tile": (fp + e2) / max(len(tile_dets), 1),
        "precision": tp / (tp + fp + e2) if tp + fp + e2 else None,
        "recall_by_width": {k: {"found": f, "total": n, "recall": f / n if n else None} for k, (f, n) in bins.items()},
    }


def match_anchors(anchors, devices, radius=ANCHOR_RADIUS):
    """One-to-one match of anchors (list of xyz or None) to devices by distance, nearest pairs first.

    Returns (device id or None, distance or None) per anchor."""
    pairs = []
    for i, a in enumerate(anchors):
        if a is None:
            continue
        for d in devices:
            dist = float(np.linalg.norm(np.asarray(a, float) - np.asarray(d["center"], float)))
            if dist <= radius:
                pairs.append((dist, i, d["id"]))
    out = [(None, None)] * len(anchors)
    used = set()
    for dist, i, dev in sorted(pairs):
        if out[i][0] is None and dev not in used:
            out[i] = (dev, dist)
            used.add(dev)
    return out

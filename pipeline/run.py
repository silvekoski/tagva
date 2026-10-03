import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from functools import cache
from pathlib import Path

import numpy as np

from pipeline import cabinets, documents, review, tagfile, tiles
from pipeline.anchor import box_anchor
from pipeline.merge import Observation, merge
from pipeline.scan import Scan
from pipeline.sphere import equirect_to_dirs

DEVICE_TYPE = "REX615"
SWEEPS_SHARE = 0.9


MIN_CONFIDENCE = 0.5
TILE_CONFIDENCE = 0.25


def pano_boxes(specs, detections, pano_width, pano_height):
    """Per-tile ((x0, y0, x1, y1), score) lists to NMS-merged equirect boxes: list of (box, score)."""
    boxes, scores, edges = [], [], []
    for spec, dets in zip(specs, detections):
        for xyxy, score in dets:
            boxes.append(tiles.tile_box_to_pano(spec, xyxy, pano_width, pano_height))
            scores.append(float(score))
            edges.append(tiles.touches_edge(spec, xyxy))
    kept, best = tiles.nms_pano(boxes, scores, edges, pano_width)
    return [(boxes[k], s) for k, s in zip(kept, best)]


def contains(outer, box, pano_width):
    """True when the center of pano box box lies in pano box outer."""
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    return (cx - outer[0]) % pano_width <= outer[2] and outer[1] <= cy <= outer[1] + outer[3]


def polygon_xyxy(poly):
    p = np.asarray(poly, float)
    return (*p.min(0), *p.max(0))


def box_entry(o):
    x, y, w, h = o.box
    return {
        "scan_position": o.sweep,
        "x": round(float(x), 1),
        "y": round(float(y), 1),
        "width": round(float(w), 1),
        "height": round(float(h), 1),
        "confidence": round(o.score, 3),
        "ocr_text": o.text,
    }


def run_pipeline(
    project,
    site,
    scan_dir,
    e57_path,
    weights,
    tags_dir,
    docs_dir,
    review_threshold=0.5,
    merge_radius=0.2,
    cabinet_radius=2.0,
    min_confidence=MIN_CONFIDENCE,
    progress=None,
    detector=None,
    ocr=None,
):
    progress = progress or (lambda step, fraction, message: None)
    scan_dir = Path(scan_dir)
    manifest = json.loads((scan_dir / "manifest.json").read_text())
    W, H = manifest["pano_width"], manifest["pano_height"]
    sweeps = [(s["id"], s["index"], np.array(s["position"], float), np.array(s["rotation"], float)) for s in manifest["sweeps"]]

    progress("load", 0.0, "loading models")
    ocr_lib = importlib.import_module("pipeline.ocr")
    if detector is None:
        from pipeline.detect import Detector

        detector = Detector(weights, conf=min(TILE_CONFIDENCE, min_confidence))

    @cache
    def load_grid(sid):
        with np.load(scan_dir / "depth" / f"{sid}.npz") as z:
            return z["range"]

    def observe(sid, position, rotation, box, score, text, text_score):
        anchor, _ = box_anchor(load_grid(sid), rotation, position, box, W, H)
        x, y, w, h = box
        ray = equirect_to_dirs(x + w / 2, y + h / 2, W, H)
        return Observation(sid, position, ray, box, score, text, text_score, anchor)

    def read_sweep(sid, position, rotation, devices, device_views, label_views):
        found = []
        for (box, score), lines in zip(devices, ocr.reads(device_views)):
            text_score = float(np.mean([s for _, s in lines])) if lines else 0.0
            found.append(observe(sid, position, rotation, box, score, ocr_lib.device_name(lines), text_score))
        labels = [observe(sid, position, rotation, *label) for label in ocr.read_labels(label_views)]
        return found, labels

    scan = Scan(e57_path)
    readings = []
    with ThreadPoolExecutor(1) as background, (nullcontext(ocr) if ocr else ocr_lib.Ocr()) as ocr:
        for k, (sid, index, position, rotation) in enumerate(sweeps):
            progress("detect", SWEEPS_SHARE * k / len(sweeps), f"{sid}: tiles")
            faces = scan.faces(index)
            specs, images = zip(*tiles.render_tiles(faces))
            progress("detect", SWEEPS_SHARE * (k + 0.3) / len(sweeps), f"{sid}: detector and text detection")
            polys = background.submit(ocr.detect, list(images))
            devices = pano_boxes(specs, detector(list(images)), W, H)
            texts = [[(polygon_xyxy(p), s) for p, s in found] for found in polys.result()]
            del images
            plates = [box for box, score in devices if score >= review_threshold]
            text_boxes = [(b, s) for b, s in pano_boxes(specs, texts, W, H) if not any(contains(p, b, W) for p in plates)]
            device_views = [ocr_lib.box_view(faces, box, W, H) for box, _ in devices]
            label_views = ocr_lib.label_views(faces, text_boxes, W, H)
            del faces
            readings.append(background.submit(read_sweep, sid, position, rotation, devices, device_views, label_views))
            progress("detect", SWEEPS_SHARE * (k + 1) / len(sweeps), f"{sid}: {len(devices)} device boxes, {len(text_boxes)} text boxes")
        device_obs, label_obs = [], []
        for reading in readings:
            found, labels = reading.result()
            device_obs += found
            label_obs += labels

    progress("merge", SWEEPS_SHARE, f"merging {len(device_obs)} device and {len(label_obs)} label observations")
    geometry = [(sid, position, rotation) for sid, _, position, rotation in sweeps]
    groups = [g for g in merge(device_obs, merge_radius) if g.score >= min_confidence]
    labels = [g for g in merge(label_obs, merge_radius) if cabinets.confirmed(g, geometry, load_grid)]
    assignment = cabinets.assign([g.anchor for g in groups], [g.anchor for g in labels], cabinet_radius)
    docs = documents.lookup(docs_dir, DEVICE_TYPE, project)

    progress("review", 0.95, "review flags")
    entries = []
    for g, (label, ambiguous) in zip(groups, assignment):
        name = g.text
        few = review.few_observations(g, geometry, load_grid)
        reasons = review.reasons(g, name, review_threshold, merge_radius, ambiguous, few)
        observations = sorted(g.observations, key=lambda o: (o.sweep, o.box))
        entries.append((label, {
            "name": name,
            "device_type": DEVICE_TYPE,
            "boxes": [box_entry(o) for o in observations],
            "anchor": tagfile.point(g.anchor),
            "confidence": round(g.score, 3),
            "documents": docs,
            "review": bool(reasons),
            "review_reasons": reasons,
        }))
    data = tagfile.build(
        project, site or project, review_threshold, merge_radius, cabinet_radius, Path(e57_path).name,
        [(g.text, g.anchor) for g in labels], entries,
    )
    data["min_confidence"] = min_confidence
    progress("write", 0.98, "writing the tag file")
    data = tagfile.save(tags_dir, data)
    progress("done", 1.0, f"{len(groups)} devices, {len(labels)} cabinet labels")
    return data

import json
import sys
from contextlib import nullcontext
import time
import types
from pathlib import Path

import numpy as np
import pytest

from pipeline import review, run, tiles
from pipeline.merge import text_key
from pipeline.scan import GRID_COLS, GRID_ROW_HORIZON, GRID_ROWS, GRID_STEP
from pipeline.sphere import equirect_to_dirs

ROOT = Path(__file__).resolve().parent.parent
W, H = 8192, 4096
UP = np.array([0.0, 0.0, 1.0])


def plate_box(spec, position, center, normal, width, height):
    """Tile box (x0, y0, x1, y1) of a plate, or None when a corner is outside the tile."""
    side = np.cross(UP, normal)
    side /= np.linalg.norm(side)
    corners = np.array([center + a * width / 2 * side + b * height / 2 * UP for a in (-1, 1) for b in (-1, 1)])
    d = corners - position
    x, y = tiles.dirs_to_tile_pixel(spec, d / np.linalg.norm(d, axis=1, keepdims=True))
    if not (np.all(np.isfinite(x)) and x.min() >= 0 and y.min() >= 0 and x.max() <= spec.size and y.max() <= spec.size):
        return None
    return (float(x.min()), float(y.min()), float(x.max()), float(y.max()))


def fake_ocr_module(ocr, box_view=lambda faces, box, w, h: (faces, box), device_name=None):
    m = types.ModuleType("pipeline.ocr")
    m.Ocr = lambda: nullcontext(ocr)
    m.box_view = box_view
    m.label_views = lambda faces, boxes, w, h: [(box, score, 1, box_view(faces, box, w, h)) for box, score in boxes]
    m.device_name = device_name or (lambda lines: " ".join(t for t, _ in lines if t != "REX615"))
    return m


# Synthetic room: a wall at x = 3 m, two sweeps, three devices and two cabinet labels on the wall.
WALL_X = 3.0
NORMAL = np.array([-1.0, 0.0, 0.0])
SWEEPS = [np.array([0.0, 0.0, 1.5]), np.array([1.0, 0.0, 1.5])]
DEVICES = [(np.array([3.0, 0.5, 1.8]), 0.9, "Q01"), (np.array([3.0, -0.5, 1.8]), 0.8, "Q02"), (np.array([3.0, 3.0, 1.8]), 0.3, "Q03")]
LABELS = [(np.array([3.0, 0.5, 1.2]), "H01 FEED"), (np.array([3.0, -0.5, 1.2]), "H02 FEED")]


def wall_grid(x0):
    el = (np.arange(GRID_ROWS) - GRID_ROW_HORIZON) * GRID_STEP
    az = (np.arange(GRID_COLS) + 0.5) * GRID_STEP
    dx = np.cos(el)[:, None] * np.cos(az)[None, :]
    return np.where(dx > 0.05, (WALL_X - x0) / np.maximum(dx, 0.05), 0).astype(np.float16)


def nearest(sweep, box, items):
    x, y, w, h = box
    d = equirect_to_dirs(x + w / 2, y + h / 2, W, H)
    return min(items, key=lambda it: np.linalg.norm((it[0] - SWEEPS[sweep]) / np.linalg.norm(it[0] - SWEEPS[sweep]) - d))


class SyntheticDetector:
    def __call__(self, images):
        out = []
        for sweep, spec in images:
            boxes = [(plate_box(spec, SWEEPS[sweep], c, NORMAL, 0.26, 0.18), s) for c, s, _ in DEVICES]
            out.append([(b, s) for b, s in boxes if b is not None])
        return out


class SyntheticOcr:
    def detect(self, images):
        out = []
        for sweep, spec in images:
            boxes = [plate_box(spec, SWEEPS[sweep], c, NORMAL, 0.2, 0.05) for c, _ in LABELS]
            out.append([(np.array([[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]), 0.9) for b in boxes if b is not None])
        return out

    def reads(self, crops):
        return [[("REX615", 0.95), (nearest(sweep, box, DEVICES)[2], 0.8)] for sweep, box in crops]

    def read_labels(self, views):
        return [(box, score, nearest(sweep, box, LABELS)[1], 0.9) for box, score, _, (sweep, _) in views]


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    scan_dir = tmp_path / "scan"
    (scan_dir / "depth").mkdir(parents=True)
    sweeps = []
    for i, p in enumerate(SWEEPS):
        np.savez_compressed(scan_dir / "depth" / f"sweep-{i:02d}.npz", range=wall_grid(p[0]))
        sweeps.append({"id": f"sweep-{i:02d}", "index": i, "name": f"Sweep {i}", "position": p.tolist(),
                       "rotation": np.eye(3).tolist(), "pano": f"panos/sweep-{i:02d}.jpg"})
    (scan_dir / "manifest.json").write_text(json.dumps({"source": "x.e57", "pano_width": W, "pano_height": H, "sweeps": sweeps}))
    docs = tmp_path / "docs" / "devices" / "REX615"
    docs.mkdir(parents=True)
    (docs / "rex615-manual.pdf").write_bytes(b"x")

    class FakeScan:
        def __init__(self, path):
            pass

        def faces(self, index):
            return index

    monkeypatch.setattr(run, "Scan", FakeScan)
    monkeypatch.setattr(tiles, "render_tiles", lambda faces, specs=None: ((s, (faces, s)) for s in specs or tiles.tile_specs()))
    monkeypatch.setitem(sys.modules, "pipeline.ocr", fake_ocr_module(SyntheticOcr()))
    return tmp_path, scan_dir


def test_run_pipeline_synthetic(synthetic):
    tmp_path, scan_dir = synthetic
    steps = []
    data = run.run_pipeline(
        "VEO DEMO", "", scan_dir, "x.e57", "missing.pt", tmp_path / "tags", tmp_path / "docs",
        progress=lambda step, fraction, message: steps.append((step, fraction)), detector=SyntheticDetector(),
    )
    assert json.loads((tmp_path / "tags" / "VEO-DEMO.json").read_text()) == data
    assert data["site"] == "VEO DEMO" and data["scan"] == "x.e57"
    assert [t["cabinet"] for t in data["tags"]] == ["H01 FEED", "H02 FEED", "unassigned"]
    assert [t["id"] for t in data["tags"]] == ["tag-001", "tag-002", "tag-unassigned"]
    for tag, (center, _), (device_center, score, name) in zip(data["tags"], LABELS + [(None, None)], DEVICES):
        if center is not None:
            assert np.linalg.norm([tag["anchor"][k] - center[i] for i, k in enumerate("xyz")]) < 0.03
        (d,) = tag["devices"]
        assert np.linalg.norm([d["anchor"][k] - device_center[i] for i, k in enumerate("xyz")]) < 0.03
        assert d["name"] == name and d["confidence"] == score and d["device_type"] == "REX615"
        assert sorted(b["scan_position"] for b in d["boxes"]) == ["sweep-00", "sweep-01"]
        assert all(b["ocr_text"] == name for b in d["boxes"])
        assert d["documents"] == [{"title": "rex615 manual", "kind": "manual", "url": "/documents/devices/REX615/rex615-manual.pdf"}]
        assert d["review_reasons"] == ([] if score >= 0.5 else ["low_confidence"])
    assert steps[-1] == ("done", 1.0)
    assert all(a[1] <= b[1] for a, b in zip(steps, steps[1:]))


def test_run_pipeline_flags_missing_anchor_and_empty_ocr(synthetic, monkeypatch):
    tmp_path, scan_dir = synthetic
    monkeypatch.setitem(sys.modules, "pipeline.ocr", fake_ocr_module(SyntheticOcr(), device_name=lambda lines: ""))
    for i in range(len(SWEEPS)):
        np.savez_compressed(scan_dir / "depth" / f"sweep-{i:02d}.npz", range=np.zeros((GRID_ROWS, GRID_COLS), np.float16))
    data = run.run_pipeline("P", "S", scan_dir, "x.e57", "missing.pt", tmp_path / "tags", tmp_path / "docs", detector=SyntheticDetector())
    assert [t["id"] for t in data["tags"]] == ["tag-unassigned"]
    devices = data["tags"][0]["devices"]
    assert len(devices) == 6
    assert all(d["anchor"] is None and "no_anchor" in d["review_reasons"] and "empty_ocr" in d["review_reasons"] for d in devices)


def test_run_pipeline_drops_label_read_by_one_sweep_of_two_that_see_it(synthetic, monkeypatch):
    tmp_path, scan_dir = synthetic

    class OneSweepOcr(SyntheticOcr):
        def read_labels(self, views):
            labels = super().read_labels(views)
            return [label for label, (_, _, _, (sweep, _)) in zip(labels, views) if sweep == 0 or label[2] != "H02 FEED"]

    monkeypatch.setitem(sys.modules, "pipeline.ocr", fake_ocr_module(OneSweepOcr()))
    data = run.run_pipeline("P", "S", scan_dir, "x.e57", "missing.pt", tmp_path / "tags", tmp_path / "docs", detector=SyntheticDetector())
    assert [(t["cabinet"], [d["name"] for d in t["devices"]]) for t in data["tags"]] == [("H01 FEED", ["Q02", "Q01"]), ("unassigned", ["Q03"])]


def test_contains_uses_box_center_across_seam():
    assert run.contains((8100.0, 100.0, 200.0, 50.0), (8180.0, 110.0, 40.0, 20.0), W)
    assert run.contains((8100.0, 100.0, 200.0, 50.0), (60.0, 110.0, 40.0, 20.0), W)
    assert not run.contains((8100.0, 100.0, 200.0, 50.0), (200.0, 110.0, 40.0, 20.0), W)
    assert not run.contains((8100.0, 100.0, 200.0, 50.0), (8180.0, 140.0, 40.0, 40.0), W)


def test_run_pipeline_skips_text_on_device_plates(synthetic, monkeypatch):
    tmp_path, scan_dir = synthetic

    class PlateTextOcr(SyntheticOcr):
        def detect(self, images):
            out = super().detect(images)
            for (sweep, spec), polys in zip(images, out):
                b = plate_box(spec, SWEEPS[sweep], DEVICES[0][0], NORMAL, 0.05, 0.03)
                if b is not None:
                    polys.append((np.array([[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]), 0.9))
            return out

    monkeypatch.setitem(sys.modules, "pipeline.ocr", fake_ocr_module(PlateTextOcr()))
    data = run.run_pipeline("P", "S", scan_dir, "x.e57", "missing.pt", tmp_path / "tags", tmp_path / "docs", detector=SyntheticDetector())
    assert [t["cabinet"] for t in data["tags"]] == ["H01 FEED", "H02 FEED", "unassigned"]
    data = run.run_pipeline("P", "S", scan_dir, "x.e57", "missing.pt", tmp_path / "tags", tmp_path / "docs",
                            review_threshold=0.95, detector=SyntheticDetector())
    assert [t["cabinet"] for t in data["tags"]] == ["H01 FEED", "H01 FEED", "H02 FEED", "unassigned"]


E57 = ROOT / "cloud_0.e57"
SCAN_DIR = ROOT / "data" / "scan"
REAL_DEVICES = ROOT / "eval" / "real-devices.json"


REAL_SCAN = pytest.mark.skipif(not (E57.is_file() and (SCAN_DIR / "manifest.json").is_file()), reason="needs the real scan")


class TruthDetector:
    """Ground truth plate boxes of each visible device, one call per sweep in manifest order."""

    def __init__(self, sweeps, truth):
        self.sweeps, self.truth, self.calls = sweeps, truth, 0

    def __call__(self, images):
        s = self.sweeps[self.calls]
        self.calls += 1
        position, rotation = np.array(s["position"]), np.array(s["rotation"])
        with np.load(SCAN_DIR / "depth" / f"{s['id']}.npz") as z:
            grid = z["range"]
        visible = [
            d for d in self.truth
            if np.dot(position - d["center"], d["normal"]) > 0 and review.line_of_sight(grid, rotation, position, d["center"])
        ]
        out = []
        for spec, _ in zip(tiles.tile_specs(), images):
            boxes = [plate_box(spec, position, np.array(d["center"]), np.array(d["normal"], float), d["width"], d["height"]) for d in visible]
            out.append([(b, 0.9) for b in boxes if b is not None])
        return out


@pytest.mark.slow
@REAL_SCAN
def test_run_pipeline_real_scan_ground_truth(tmp_path, monkeypatch):
    truth = json.loads(REAL_DEVICES.read_text())["devices"]
    manifest = json.loads((SCAN_DIR / "manifest.json").read_text())

    class EmptyOcr:
        def detect(self, images):
            return [[] for _ in images]

        def reads(self, crops):
            return [[] for _ in crops]

        def read_labels(self, views):
            return []

    render, render_times = tiles.render_tiles, []

    def timed_render(faces, specs=None):
        start = time.perf_counter()
        out = list(render(faces, specs))
        render_times.append(time.perf_counter() - start)
        return iter(out)

    monkeypatch.setattr(tiles, "render_tiles", timed_render)
    monkeypatch.setitem(sys.modules, "pipeline.ocr", fake_ocr_module(
        EmptyOcr(), box_view=lambda *a, **k: None, device_name=lambda lines: ""))
    start = time.perf_counter()
    data = run.run_pipeline("REAL", "", SCAN_DIR, E57, "missing.pt", tmp_path / "tags", tmp_path / "docs", detector=TruthDetector(manifest["sweeps"], truth))
    print(f"run {time.perf_counter() - start:.1f} s, tile rendering per sweep: mean {np.mean(render_times):.2f} s, "
          f"min {np.min(render_times):.2f} s, max {np.max(render_times):.2f} s, sweeps {len(render_times)}")
    devices = [d for t in data["tags"] for d in t["devices"]]
    anchors = np.array([[d["anchor"][k] for k in "xyz"] for d in devices if d["anchor"] is not None])
    assert len(devices) == len(truth) == len(anchors)
    dist = np.linalg.norm(anchors[None] - np.array([d["center"] for d in truth])[:, None], axis=2)
    print({d["id"]: round(float(dist[i].min()), 3) for i, d in enumerate(truth)})
    assert len(set(dist.argmin(1))) == len(truth)
    assert dist.min(1).max() < 0.3


REAL_CABINETS = {"w1": "H01 PT1", "w2": "H02 STATION TRANSFORMER", "w3": "H03 METERING", "w4": "H04 SOLAR 1", "w5": "H05 SOLAR 2", "e1": "OT1"}


@pytest.mark.slow
@REAL_SCAN
def test_run_pipeline_real_ocr(tmp_path):
    """Full run with the real OCR and the ground truth detector: each relay goes to the nameplate of its own panel."""
    truth = json.loads(REAL_DEVICES.read_text())["devices"]
    manifest = json.loads((SCAN_DIR / "manifest.json").read_text())
    start = time.perf_counter()
    data = run.run_pipeline("REAL", "", SCAN_DIR, E57, "missing.pt", tmp_path / "tags", tmp_path / "docs",
                            detector=TruthDetector(manifest["sweeps"], truth))
    print(f"run {time.perf_counter() - start:.1f} s, cabinets {[t['cabinet'] for t in data['tags']]}")
    cabinet = {}
    for t in data["tags"]:
        for d in t["devices"]:
            near = [g["id"] for g in truth if np.linalg.norm([d["anchor"][k] - g["center"][i] for i, k in enumerate("xyz")]) < 0.1]
            cabinet.update({i: t["cabinet"] for i in near})
    print(cabinet)
    assert sorted(cabinet) == sorted(g["id"] for g in truth)
    assert {i: text_key(cabinet[i]) for i in REAL_CABINETS} == {i: text_key(c) for i, c in REAL_CABINETS.items()}

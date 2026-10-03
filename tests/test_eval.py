import numpy as np
import pytest

from eval import acceptance, realtest
from pipeline import tiles


def gt(xyxy, device="w1", target=True, ignore=False):
    return {"xyxy": xyxy, "device": device, "target": target, "ignore": ignore, "width_px": xyxy[2] - xyxy[0]}


def test_iou():
    assert realtest.iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert realtest.iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)
    assert realtest.iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0


def test_size_bins():
    assert [realtest.size_bin(w) for w in (5, 29.9, 30, 60, 119, 120, 500)] == ["<30", "<30", "30-60", "60-120", "60-120", ">120", ">120"]


def test_match_tile_outcomes():
    gts = [gt((100, 100, 200, 170)), gt((400, 100, 460, 160), "e2", target=False), gt((1200, 0, 1280, 50), "w2", ignore=True)]
    dets = [
        ((102, 98, 203, 171), 0.9),
        ((101, 101, 199, 169), 0.8),
        ((400, 100, 458, 161), 0.7),
        ((1210, 5, 1270, 45), 0.6),
        ((700, 700, 760, 740), 0.5),
    ]
    out = realtest.match_tile(dets, gts)
    assert [o[0] for o in out] == ["tp", "fp", "e2", "ignored", "fp"]
    assert out[0][1] == 0 and out[2][1] == 1


def test_match_tile_prefers_higher_score():
    gts = [gt((100, 100, 200, 170))]
    out = realtest.match_tile([((110, 100, 210, 170), 0.3), ((100, 100, 200, 170), 0.9)], gts)
    assert [o[0] for o in out] == ["fp", "tp"]


def test_low_iou_is_fp_and_miss():
    r = realtest.score_tiles([[((100, 100, 140, 170), 0.9)]], [[gt((100, 100, 200, 170))]], 0.5)
    assert r["tp"] == 0 and r["fp"] == 1 and r["recall"] == 0.0


def test_score_tiles_counts_and_threshold():
    gts = [[gt((0, 0, 20, 10)), gt((100, 0, 200, 50)), gt((300, 0, 340, 40), "e2", target=False)], [], [gt((0, 0, 80, 40), ignore=True)]]
    dets = [[((0, 0, 20, 10), 0.4), ((100, 0, 200, 50), 0.9), ((300, 0, 340, 40), 0.6)], [((5, 5, 50, 50), 0.3)], [((0, 0, 80, 40), 0.9)]]
    r = realtest.score_tiles(dets, gts, 0.25)
    assert (r["tp"], r["targets"], r["fp"], r["e2_detections"]) == (2, 2, 2, 1)
    assert r["recall"] == 1.0 and r["precision"] == pytest.approx(0.5) and r["fp_per_tile"] == pytest.approx(2 / 3)
    assert r["recall_by_width"]["<30"] == {"found": 1, "total": 1, "recall": 1.0}
    assert r["recall_by_width"][">120"]["total"] == 0
    r = realtest.score_tiles(dets, gts, 0.5)
    assert (r["tp"], r["fp"], r["e2_detections"]) == (1, 1, 1)
    assert r["recall_by_width"]["<30"]["found"] == 0


DEVICES = [
    {"id": "e1", "target": True, "center": [-2.765, -5.922, 1.723], "normal": [-1, 0, 0], "width": 0.258, "height": 0.168},
    {"id": "e2", "target": False, "center": [-2.764, -5.921, 1.428], "normal": [-1, 0, 0], "width": 0.173, "height": 0.169},
    {"id": "w1", "target": True, "center": [-5.701, -5.85, 1.842], "normal": [1, 0, 0], "width": 0.258, "height": 0.168},
]


def test_match_anchors_one_to_one_nearest_first():
    a = [[-2.765, -5.922, 1.60], [-2.765, -5.922, 1.70], [-5.70, -5.85, 1.84], [-5.70, -5.80, 1.84], [0, 0, 0], None]
    out = realtest.match_anchors(a, DEVICES)
    assert [m[0] for m in out] == ["e2", "e1", "w1", None, None, None]
    assert out[1][1] == pytest.approx(0.023, abs=1e-3)


def tagfile(anchors):
    devs = [{"device_id": f"dev-{i}", "anchor": None if a is None else dict(zip("xyz", a))} for i, a in enumerate(anchors)]
    return {"tags": [{"devices": devs[:1]}, {"devices": devs[1:]}]}


def test_acceptance_pass_with_one_fp():
    passed, rows, missed, fps = acceptance.check(tagfile([[-2.75, -5.9, 1.75], [-5.7, -5.85, 1.9], [1, 1, 1]]), DEVICES)
    assert passed and missed == 0 and fps == 1


def test_acceptance_fails_on_miss_or_two_fps():
    assert not acceptance.check(tagfile([[-2.75, -5.9, 1.75]]), DEVICES)[0]
    passed, _, missed, fps = acceptance.check(tagfile([[-2.75, -5.9, 1.75], [-5.7, -5.85, 1.9], [-2.76, -5.92, 1.43], None]), DEVICES)
    assert not passed and missed == 0 and fps == 2


def test_acceptance_duplicate_is_fp():
    _, rows, missed, fps = acceptance.check(tagfile([[-5.7, -5.85, 1.84], [-5.7, -5.85, 1.9], [-2.75, -5.9, 1.75]]), DEVICES)
    assert missed == 0 and fps == 1
    assert rows[-1]["device_id"] == "dev-1" and rows[-1]["result"].startswith("false_positive")


def test_project_box_matches_plate_size():
    spec = tiles.tile_specs()[12]
    d = {"center": [3.0, 0.0, 0.0], "normal": [-1, 0, 0], "width": 0.3, "height": 0.2}
    x0, y0, x1, y1 = realtest.project_box(spec, np.zeros(3), d)
    f = spec.size / 2 / np.tan(spec.fov / 2)
    assert x1 - x0 == pytest.approx(0.3 / 3 * f, rel=1e-3) and y1 - y0 == pytest.approx(0.2 / 3 * f, rel=1e-3)
    assert (x0 + x1) / 2 == pytest.approx(spec.size / 2) and realtest.inside(spec, (x0, y0, x1, y1))


def test_visibility_sees_plate_and_detects_occluder():
    d = {"center": [2.0, 0.0, 0.0], "normal": [-1, 0, 0], "width": 0.3, "height": 0.2}
    grid = np.full((1800, 3600), 2.0, np.float32)
    assert realtest.visibility(grid, np.eye(3), np.zeros(3), d) == (True, 1.0)
    grid[:] = 1.0
    los, fraction = realtest.visibility(grid, np.eye(3), np.zeros(3), d)
    assert not los and fraction == 0.0


def test_visibility_tolerance_grows_with_distance():
    d = {"center": [5.0, 0.0, 0.0], "normal": [-1, 0, 0], "width": 0.3, "height": 0.2}
    grid = np.full((1800, 3600), 4.92, np.float32)
    assert realtest.visibility(grid, np.eye(3), np.zeros(3), d)[0]
    grid[:] = 4.85
    assert not realtest.visibility(grid, np.eye(3), np.zeros(3), d)[0]


def load_builder():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_real_test", realtest.ROOT / "eval" / "build-real-test.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tile_boxes_keep_cut_and_hidden():
    builder = load_builder()
    spec = tiles.tile_specs()[12]
    inside = {"id": "a", "target": True, "center": [3.0, 0.0, 0.0], "normal": [-1, 0, 0], "width": 0.3, "height": 0.2}
    cut = {"id": "b", "target": True, "center": [3.0, np.tan(spec.fov / 2) * 3.0, 0.0], "normal": [-1, 0, 0], "width": 0.3, "height": 0.2}
    hidden = {"id": "c", "target": False, "center": [3.0, -1.0, 0.0], "normal": [-1, 0, 0], "width": 0.3, "height": 0.2}
    visible = {"a": (True, 1.0), "b": (True, 1.0), "c": (False, 0.0)}
    boxes = builder.tile_boxes(spec, "sweep-00", np.zeros(3), [inside, cut, hidden], visible, 8192, 4096)
    by = {b["device"]: b for b in boxes}
    assert set(by) == {"a", "b"}
    assert not by["a"]["ignore"] and by["b"]["ignore"] and by["b"]["ignore_reason"] == "cut"
    assert max(by["b"]["xyxy"]) <= spec.size and by["a"]["width_px"] == pytest.approx(0.1 * spec.size / 2 / np.tan(spec.fov / 2), rel=1e-3)
    assert builder.yolo_lines(spec, boxes)[0].startswith("0 0.5")
    occluded = builder.tile_boxes(spec, "sweep-00", np.zeros(3), [inside], {"a": (False, 0.5)}, 8192, 4096)
    assert occluded[0]["ignore_reason"] == "occluded"


def test_darken_drops_exposure_and_is_repeatable():
    img = np.full((64, 64, 3), 180, np.uint8)
    dark = realtest.darken(img, 0.2, seed=3)
    assert dark.shape == img.shape and dark.dtype == np.uint8
    assert 60 < dark.mean() < 110 and dark.std() > 0
    assert np.array_equal(dark, realtest.darken(img, 0.2, seed=3))
    assert realtest.darken(np.zeros_like(img), 0.2).mean() < 30

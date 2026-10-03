import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pipeline import ocr, sphere

W, H = 8192, 4096
E57 = Path(__file__).resolve().parents[1] / "cloud_0.e57"
FACE = 512


@pytest.fixture
def small_faces(monkeypatch):
    monkeypatch.setattr(sphere, "FACE_SIZE", FACE)
    monkeypatch.setattr(sphere, "FACE_FOCAL", FACE / 2)
    monkeypatch.setattr(sphere, "REMAP_COLS", FACE)

    def make(lon0, lon1, lat0, lat1):
        s = (np.arange(FACE) + 0.5) / FACE * 2 - 1
        cx, cy = np.meshgrid(s, -s)
        cam = np.stack([cx, cy, -np.ones_like(cx)], -1)
        cam /= np.linalg.norm(cam, axis=-1, keepdims=True)
        faces = []
        for f, up in [((1, 0, 0), (0, 0, 1)), ((-1, 0, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, 1)),
                      ((0, -1, 0), (0, 0, 1)), ((0, 0, 1), (1, 0, 0)), ((0, 0, -1), (1, 0, 0))]:
            f, up = np.array(f, float), np.array(up, float)
            R = np.stack([np.cross(f, up), up, -f], 1)
            d = cam @ R.T
            lon, lat = np.arctan2(d[..., 1], d[..., 0]), np.arcsin(d[..., 2])
            dlon = np.mod(lon - lon0 + np.pi, 2 * np.pi) - np.pi
            inside = (dlon >= 0) & (dlon <= np.mod(lon1 - lon0, 2 * np.pi)) & (lat >= lat0) & (lat <= lat1)
            img = np.where(inside[..., None], 255, 0).astype(np.uint8).repeat(3, -1)
            faces.append((img, R))
        return faces

    return make


def pano_box(lon0, lon1, lat0, lat1):
    u1, v0 = sphere.dirs_to_equirect(sphere.lonlat_to_dirs(np.float64(lon0), np.float64(lat1)), W, H)
    u0, v1 = sphere.dirs_to_equirect(sphere.lonlat_to_dirs(np.float64(lon1), np.float64(lat0)), W, H)
    return (float(np.mod(u0, W)), float(v0), float(np.mod(u1 - u0, W)), float(v1 - v0))


def white_bbox(img):
    ys, xs = np.nonzero(img[..., 0] > 127)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


@pytest.mark.parametrize("lon0, lat0", [(0.5, -0.2), (np.pi - 0.1, 0.1), (-2.0, -0.6), (1.0, 0.7)])
def test_box_view_centers_box_with_margin(small_faces, lon0, lat0):
    lon1, lat1 = lon0 + 0.3, lat0 + 0.12
    view = ocr.box_view(small_faces(lon0, lon1, lat0, lat1), pano_box(lon0, lon1, lat0, lat1), W, H, min_width=10)
    h, w = view.shape[:2]
    x0, y0, x1, y1 = white_bbox(view)
    assert abs((x0 + x1) / 2 - w / 2) <= 1.5 and abs((y0 + y1) / 2 - h / 2) <= 1.5
    assert (x1 - x0) / w == pytest.approx(1 / (1 + ocr.VIEW_MARGIN), abs=0.02)
    assert (y1 - y0) / h == pytest.approx(1 / (1 + ocr.VIEW_MARGIN), abs=0.04)


def test_box_view_native_focal_and_min_width(small_faces):
    lon0, lat0 = 1.0, 0.0
    faces = small_faces(lon0, lon0 + 0.4, lat0, lat0 + 0.2)
    box = pano_box(lon0, lon0 + 0.4, lat0, lat0 + 0.2)
    x0, x1, _, _ = ocr.view_bounds(box, W, H, *ocr.view_direction(box, W, H))
    big = ocr.box_view(faces, box, W, H, min_width=10)
    assert big.shape[1] == pytest.approx((x1 - x0) * (1 + ocr.VIEW_MARGIN) * FACE / 2, abs=1)
    small = ocr.box_view(faces, pano_box(lon0, lon0 + 0.01, lat0, lat0 + 0.005), W, H, min_width=640)
    assert small.shape[1] == pytest.approx(640, abs=1)
    assert small.shape[0] < small.shape[1]


def test_box_view_seam_and_size_cap(small_faces):
    lon0 = np.pi - 0.05
    faces = small_faces(lon0, lon0 + 0.1, 0.0, 0.05)
    box = pano_box(lon0, lon0 + 0.1, 0.0, 0.05)
    assert box[0] + box[2] > W
    view = ocr.box_view(faces, box, W, H, min_width=200)
    x0, _, x1, _ = white_bbox(view)
    assert abs((x0 + x1) / 2 - view.shape[1] / 2) <= 8
    huge = ocr.box_view(faces, box, W, H, min_width=100000)
    assert max(huge.shape[:2]) <= ocr.VIEW_MAX_SIZE


def test_box_view_zero_size_box(small_faces):
    view = ocr.box_view(small_faces(0.5, 0.6, 0.0, 0.1), (100.0, 1000.0, 0.0, 0.0), W, H)
    assert view.ndim == 3 and min(view.shape[:2]) >= 1


def test_view_direction_is_box_center():
    box = (W - 40, 1000, 80, 60)
    yaw, pitch = ocr.view_direction(box, W, H)
    u, v = sphere.dirs_to_equirect(sphere.lonlat_to_dirs(np.float64(yaw), np.float64(pitch)), W, H)
    assert np.mod(u, W) == pytest.approx(0, abs=1e-6) or np.mod(u, W) == pytest.approx(W, abs=1e-6)
    assert v == pytest.approx(1030)


def test_device_name_removes_plate_print():
    lines = [("615", 0.99), ("READY START PICKUP TRIP", 0.9), ("F1", 0.95), ("F16", 0.9), ("ESC", 0.97), ("CLEAR", 0.9),
             ("Menu", 0.9), ("HELP", 0.9), ("Close", 0.9), ("Open", 0.9), ("R", 0.9), ("L", 0.9), ("ABB", 0.99)]
    assert ocr.device_name(lines) == ""
    assert ocr.device_name(lines + [("=Q1 Feeder 2", 0.9)]) == "Q1 FEEDER 2"
    assert ocr.device_name(lines + [("Q1 FEEDER 1", 0.9)]) == "Q1 FEEDER 1"
    assert ocr.device_name(lines + [("MAIN INCOMER", 0.9)]) == "MAIN INCOMER"
    assert ocr.device_name([("XYZ", 0.1)]) == ""
    assert ocr.device_name([]) == ""


def test_device_name_drops_misread_plate_print():
    misread = [("F24", 0.72), ("F1S", 0.78), ("FI", 0.71), ("FL", 0.73), ("XEADY", 0.8), ("TRIF", 0.85), ("HELF", 0.91), ("CPEN", 0.69), ("415", 0.62),
               ("FL3", 0.66), ("HEL", 0.97), ("O", 0.76), ("\u5382", 0.79), ("TRI", 0.83), ("XEAD", 0.8), ("FU", 0.77),
               ("MEAD", 0.76), ("TCU", 0.61), ("14", 0.85), ("PICKUPTRIP", 0.91), ("F23", 0.71)]
    assert ocr.device_name(misread) == ""
    assert ocr.device_name(misread + [("J07 Incomer", 0.9)]) == "J07 INCOMER"
    assert ocr.device_name([("J07 Incomer", 0.8)]) == ""


W1_SWEEP_10 = [
    ('ABB', 0.96), ('START', 0.69), ('F', 0.51), ('XEAD', 0.8), ('615', 1.0), ('F2', 0.86), ('F3', 0.5),
    ('CLEAR', 0.99), ('12', 0.3), ('74', 0.54), ('n', 0.36), ('ESC', 0.94), ('MENU', 0.97), ('F', 0.22),
    ('CLOSE', 0.99), ('F14', 0.95), ('HELF', 0.86), ('F5', 0.32), ('F7', 0.51), ('', 0.0), ('OPEN', 0.98),
    ('F', 0.15),
]
W2_SWEEP_11 = [
    ('ABB', 0.97), ('615', 0.99), ('A', 0.2), ('口', 0.09), ('CLEAR', 0.99), ('FU', 0.77), ('ESC', 0.79),
    ('MENU', 0.99), ('E', 0.09), ('CLOSE', 0.95), ('F14', 0.53), ('HELP', 0.97), ('F0', 0.47), ('F5', 0.27),
    ('O', 0.67), ('OPEN', 0.67),
]


@pytest.mark.parametrize("lines", [W1_SWEEP_10, W2_SWEEP_11])
def test_device_name_real_blank_plates(lines):
    """Lines read from two real REX615 views with blank label strips (XEAD and FU are misreads of plate print)."""
    assert ocr.device_name(lines) == ""


@pytest.mark.parametrize("text, score, ok", [
    ("H03 METERING", 0.95, True), ("OT1", 0.9, True), ("TSk2", 0.72, True), ("H02 STATION TRANSFORMER", 0.9, True),
    ("OT1", 0.1, False), ("ABB", 0.99, False), ("UniGear", 0.99, False), ("UniSear", 0.84, False), ("ELCON", 0.99, False),
    ("AB", 0.86, False), ("AB\u5668", 0.65, False), ("A", 0.87, False), ("TESTED", 0.96, False), ("--:", 0.99, False),
    ("", 0.99, False), ("KOKOOJA KISKO EI MOMENTISSA", 0.8, False), ("F23", 0.9, False), ("PICKUPTRIP", 0.9, False),
    *[(t, 0.95, True) for t in ["H10", "H12", "H15", "H16", "K15", "Q12", "B12", "J10", "A11", "T615", "TR1", "H12 FEEDER",
                                "H10 INCOMER"]],
])
def test_is_cabinet_label_filters(text, score, ok):
    assert ocr.is_cabinet_label(text, score) is ok


def test_label_text_joins_lines_and_rejects_badges():
    assert ocr.label_text([("h03", 0.98), ("metering", 0.99)]) == ("H03 METERING", pytest.approx(0.985))
    assert ocr.label_text([("ELCON", 0.93), ("CE", 0.61)]) == ("", 0.0)
    assert ocr.label_text([("TESTED", 0.98), ("TEST EDILMISTIR", 0.91)]) == ("", 0.0)
    assert ocr.label_text([("x", 0.2)]) == ("", 0.0)
    assert ocr.label_text([("H15 SOLAR 3", 0.95)]) == ("H15 SOLAR 3", 0.95)


def test_distance_and_stopped():
    assert ocr.distance("HELF", "HELP") == 1 and ocr.distance("HEL", "HELP") == 1 and ocr.distance("UUNIGER", "UNIGEAR") == 2
    cfg = ocr.stoplist()
    assert ocr.stopped("FI", {"F1"}, cfg) and ocr.stopped("F1S", {"F15"}, cfg) and ocr.stopped("UNICEAR", {"UNIGEAR"}, cfg)
    assert ocr.stopped("JUNIEAR", {"UNIGEAR"}, cfg) and not ocr.stopped("IUNICEARR", {"UNIGEAR"}, cfg)
    assert not ocr.stopped("H03", {"F13"}, cfg) and not ocr.stopped("Q1", {"F1"}, cfg) and not ocr.stopped("OT1", {"OPEN"}, cfg)
    assert ocr.stopped("F23", {"F13"}, cfg) and ocr.stopped("14", {"F14"}, cfg) and ocr.stopped("AB", {"ABB"}, cfg)
    assert ocr.stopped("XEAD", {"READY"}, cfg) and ocr.stopped("PICKUPTRIP", {"PICKUP", "TRIP"}, cfg)
    assert not ocr.stopped("H12", {"F12"}, cfg) and not ocr.stopped("B12", {"F12"}, cfg) and not ocr.stopped("TR1", {"TRIP"}, cfg)
    assert not ocr.stopped("1", {"L"}, cfg)


def test_stoplist_file_is_configurable(tmp_path):
    p = tmp_path / "stop.json"
    p.write_text(json.dumps({"min_score": 0.3, "name_min_score": 0.8, "min_chars": 2, "max_words": 3, "fuzzy_min_length": 3,
                             "fuzzy_long_length": 6, "plate_print": ["foo"], "not_label": ["bar"]}))
    cfg = ocr.stoplist(p)
    assert cfg["min_score"] == 0.3 and cfg["plate_print"] == {"FOO"} and cfg["not_label"] == {"BAR"}


def test_group_lines_joins_stacked_lines_only():
    h03, metering = (8096.5, 2097.4, 50.8, 24.2), (8079.9, 2124.2, 82.6, 16.3)
    far_below = (8080.0, 2200.0, 80.0, 16.0)
    beside = (8300.0 - W, 2100.0, 40.0, 20.0)
    blocks = ocr.group_lines([(h03, 0.95), (metering, 0.99), (far_below, 0.8), (beside, 0.7)], W)
    assert len(blocks) == 3
    joined, = [b for b, s, n in blocks if s == 0.99 and n == 2]
    assert joined == pytest.approx((8079.9, 2097.4, 82.6, 2140.5 - 2097.4))


def test_group_lines_across_seam():
    a, b = (W - 20.0, 100.0, 40.0, 20.0), (5.0, 125.0, 30.0, 18.0)
    (box, score, n), = ocr.group_lines([(a, 0.5), (b, 0.9)], W)
    assert score == 0.9 and n == 2 and box == pytest.approx((W - 20.0, 100.0, 55.0, 43.0))


def test_labels_pads_multi_line_views(monkeypatch):
    calls = []
    monkeypatch.setattr(ocr, "box_view", lambda faces, box, pw, ph, min_width: calls.append((box, min_width)) or box)
    reader = ocr.Ocr.__new__(ocr.Ocr)
    reader.pool = None
    reader.models = SimpleNamespace(recognize=lambda crops: [("OT1", 0.9)] * len(crops), read=lambda view: [("H04", 0.99), ("SOLAR 1", 0.98)])
    lines = [((1000.0, 2080.0, 20.0, 12.0), 0.9), ((1000.0, 2093.0, 20.0, 12.0), 0.8), ((3000.0, 2000.0, 30.0, 10.0), 0.7)]
    out = reader.labels(None, lines, W, H)
    assert [(text, box) for box, _, text, _ in out] == [("H04 SOLAR 1", (1000.0, 2080.0, 20.0, 25.0)), ("OT1", (3000.0, 2000.0, 30.0, 10.0))]
    (block, block_width), (single, single_width) = calls
    pad = ocr.LABEL_PAD * 25.0 / 2
    assert block == pytest.approx((1000.0 - pad, 2080.0, 20.0 + 2 * pad, 25.0))
    assert block_width == pytest.approx(ocr.LABEL_VIEW_WIDTH * (20.0 + 2 * pad) / 20.0)
    assert single == (3000.0, 2000.0, 30.0, 10.0) and single_width == ocr.LABEL_VIEW_WIDTH


def poly(x, y, w=40, h=10):
    return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], float)


def test_reading_order_rows_then_columns():
    polys = [poly(100, 52), poly(0, 50), poly(0, 0), poly(60, 3)]
    assert [tuple(p[0]) for p in ocr.reading_order(polys)] == [(0, 0), (60, 3), (0, 50), (100, 52)]


def test_reading_order_joins_split_line():
    out = ocr.reading_order([poly(0, 0, 80, 20), poly(90, 2, 15, 18), poly(0, 40, 30, 10)])
    assert len(out) == 2
    np.testing.assert_allclose(out[0], [[0, 0], [105, 0], [105, 20], [0, 20]])


@pytest.mark.slow
@pytest.mark.skipif(not E57.exists(), reason="needs cloud_0.e57")
def test_real_labels_full_path_sweep_12():
    """Tiles, text detection, pano boxes, NMS, line groups, views and recognition on two real labels."""
    from pipeline import tiles
    from pipeline.scan import Scan

    faces = Scan(E57).faces(12)
    reader = ocr.Ocr()
    targets = {"H03 METERING": (8121.0, 2119.0), "TSK2": (4433.0, 1992.0)}
    found = {}
    for truth, (u, v) in targets.items():
        d = sphere.equirect_to_dirs(u, v, W, H)
        specs = [s for s in tiles.tile_specs() if 100 < np.nan_to_num(tiles.dirs_to_tile_pixel(s, d)[0], nan=-1) < 1180
                 and 100 < np.nan_to_num(tiles.dirs_to_tile_pixel(s, d)[1], nan=-1) < 1180]
        images = [img for _, img in tiles.render_tiles(faces, specs)]
        boxes, scores, edges = [], [], []
        for spec, polys in zip(specs, reader.detect(images)):
            for p, score in polys:
                xyxy = (*p.min(0), *p.max(0))
                boxes.append(tiles.tile_box_to_pano(spec, xyxy, W, H))
                scores.append(score)
                edges.append(tiles.touches_edge(spec, xyxy))
        kept, best = tiles.nms_pano(boxes, scores, edges, W)
        labels = reader.labels(faces, [(boxes[k], s) for k, s in zip(kept, best)], W, H)
        found[truth] = [text for box, _, text, _ in labels if box[0] <= u <= box[0] + box[2] and box[1] <= v <= box[1] + box[3]]
    assert found == {"H03 METERING": ["H03 METERING"], "TSK2": ["TSK2"]}

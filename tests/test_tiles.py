import cv2
import numpy as np

from pipeline import sphere, tiles

W, H = 8192, 4096


def test_tile_pixel_round_trip():
    for spec in tiles.tile_specs()[::7]:
        px = np.array([0.5, 100.0, 640.0, 1279.5])
        py = np.array([0.5, 900.0, 640.0, 1279.5])
        d = sphere.tile_pixel_to_dir(spec.yaw, spec.pitch, spec.fov, spec.size, px, py)
        x, y = tiles.dirs_to_tile_pixel(spec, d)
        assert np.allclose(x, px, atol=1e-6) and np.allclose(y, py, atol=1e-6)


def test_tile_dirs_match_pixel_to_dir():
    spec = tiles.tile_specs()[13]
    grid = sphere.tile_dirs(spec.yaw, spec.pitch, spec.fov, 64)
    d = sphere.tile_pixel_to_dir(spec.yaw, spec.pitch, spec.fov, 64, np.array([10.5]), np.array([3.5]))
    assert np.allclose(grid[3, 10], d[0])


def test_equirect_round_trip():
    u = np.array([0.5, 4096.0, 8191.5])
    v = np.array([10.0, 2048.0, 4000.0])
    uu, vv = sphere.dirs_to_equirect(sphere.equirect_to_dirs(u, v, W, H), W, H)
    assert np.allclose(uu, u) and np.allclose(vv, v)


def test_box_to_pano_contains_center_direction():
    spec = tiles.tile_specs()[12]
    box = tiles.tile_box_to_pano(spec, (600, 500, 700, 580), W, H)
    d = sphere.tile_pixel_to_dir(spec.yaw, spec.pitch, spec.fov, spec.size, 650.0, 540.0)
    u, v = sphere.dirs_to_equirect(d, W, H)
    assert box[0] <= u <= box[0] + box[2] and box[1] <= v <= box[1] + box[3]
    assert 0 <= box[0] < W


def test_box_across_seam_wraps():
    spec = next(s for s in tiles.tile_specs() if np.isclose(s.yaw, np.pi) and s.pitch == 0.0)
    box = tiles.tile_box_to_pano(spec, (600, 600, 680, 680), W, H)
    assert box[2] < 200 and (box[0] > W - 200 or box[0] + box[2] > W)


def test_every_object_fits_one_tile():
    """Every 24 degree wide object between -45 and +45 degrees of elevation is inside at least one tile."""
    specs = tiles.tile_specs()
    half = np.radians(12)
    for lat in np.radians(np.arange(-45, 46, 5)):
        for lon in np.radians(np.arange(0, 360, 3)):
            corners = [sphere.lonlat_to_dirs(np.float64(lon + a), np.float64(lat + b)) for a in (-half, half) for b in (-half / 2, half / 2)]
            ok = False
            for spec in specs:
                xy = [tiles.dirs_to_tile_pixel(spec, c) for c in corners]
                if all(np.isfinite(x) and 0 <= x <= spec.size and 0 <= y <= spec.size for x, y in xy):
                    ok = True
                    break
            assert ok, (np.degrees(lon), np.degrees(lat))


def test_nms_prefers_uncut_box_and_keeps_best_score():
    boxes = [(100, 100, 50, 40), (100, 100, 30, 40), (5000, 100, 50, 40)]
    kept, scores = tiles.nms_pano(boxes, [0.5, 0.9, 0.4], [False, True, False], W)
    assert kept == [0, 2]
    assert scores == [0.9, 0.4]


def test_nms_across_seam():
    boxes = [(W - 20, 100, 50, 40), (10, 100, 20, 40)]
    kept, _ = tiles.nms_pano(boxes, [0.9, 0.8], [False, False], W)
    assert kept == [0]


def test_render_tile_matches_sample_cube(monkeypatch):
    size = 256
    monkeypatch.setattr(sphere, "FACE_SIZE", size)
    monkeypatch.setattr(sphere, "FACE_FOCAL", size / 2)
    monkeypatch.setattr(sphere, "REMAP_COLS", size)
    rng = np.random.default_rng(0)
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    axes = [np.array(a, float) for a in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
    faces = []
    for f in axes:
        up = np.array([0.0, 0.0, 1.0]) if abs(f[2]) < 0.5 else np.array([1.0, 0.0, 0.0])
        R = q @ np.stack([np.cross(f, up), up, -f], 1)
        img = cv2.GaussianBlur(rng.integers(0, 256, (size, size, 3), dtype=np.uint8), (0, 0), 2)
        faces.append((img, R))
    for yaw, pitch, fov, n in [(0.3, -0.2, 1.0, 97), (2.9, 1.3, 1.9, 120), (-1.7, 0.0, 0.2, 64)]:
        new = sphere.render_tile(faces, yaw, pitch, fov, n).astype(int)
        old = sphere.sample_cube(faces, sphere.tile_dirs(yaw, pitch, fov, n)).astype(int)
        assert np.abs(new - old).max() <= 3 and np.mean(np.abs(new - old) > 1) < 0.002

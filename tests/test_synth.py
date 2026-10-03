import json
import sys
from pathlib import Path

import cv2
import numpy as np

SYNTH = Path(__file__).resolve().parent.parent / "synth"
sys.path.insert(0, str(SYNTH))

import post  # noqa: E402
import textures  # noqa: E402


def base_profile():
    return json.loads((SYNTH / "profiles" / "base.json").read_text())


def test_resize_matches_opencv():
    a = np.random.default_rng(0).random((137, 511, 3)).astype(np.float32)
    assert np.abs(textures.resize(a, 40, 100) - cv2.resize(a, (100, 40), interpolation=cv2.INTER_AREA)).max() < 1e-5
    assert np.abs(textures.resize(a, 300, 900) - cv2.resize(a, (900, 300), interpolation=cv2.INTER_LINEAR)).max() < 1e-4


def test_gaussian_and_bilinear_match_opencv():
    a = np.random.default_rng(1).random((300, 400, 3)).astype(np.float32)
    ref = cv2.GaussianBlur(a, (7, 7), 1.0, borderType=cv2.BORDER_REPLICATE)
    assert np.abs(post.gaussian(a, 1.0) - ref).max() < 1e-5
    out = post.bilinear(a, 150, 200)
    xs, ys = np.meshgrid(np.arange(200) * 2 + 0.5, np.arange(150) * 2 + 0.5)
    ref = cv2.remap(a, xs.astype(np.float32), ys.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    assert out.flags["C_CONTIGUOUS"] and np.abs(out - ref).max() < 1e-5


def test_profiles_only_override_base_keys():
    base = base_profile()
    for path in (SYNTH / "profiles").glob("*.json"):
        prof = json.loads(path.read_text())
        assert set(prof) <= set(base), path.name
        assert prof["name"] == path.stem


def test_process_output_and_snr_order():
    p = base_profile()
    rng = np.random.default_rng(2)
    lin = np.full((256, 256, 3), 0.3, np.float32)
    lin[40:80, 40:120] = np.where(np.random.default_rng(3).random((40, 80, 1)) < 0.5, 0.05, 0.6)
    img, snr = post.process(lin, rng, p, False, [(40, 40, 120, 80), (150, 150, 200, 200)])
    assert img.shape == lin.shape and img.dtype == np.float32 and 0 <= img.min() and img.max() <= 1
    assert snr[0] > 5 * max(snr[1], 1e-3)
    _, dark = post.process(lin * 1e-3, np.random.default_rng(2), {**p, "brightness_dark": [0.002, 0.002]}, True, [(40, 40, 120, 80)])
    assert dark[0] < snr[0]


def test_fill_box_copies_a_free_neighbor():
    img = np.random.default_rng(4).random((100, 100, 3)).astype(np.float32)
    orig = img.copy()
    post.fill_box(img, (10, 10, 30, 30), np.random.default_rng(5), avoid=[(10, 10, 30, 30), (0, 32, 100, 100)])
    assert np.array_equal(img[10:30, 10:30], orig[10:30, 32:52])


def test_fill_box_fallback_matches_region_noise():
    img = np.random.default_rng(4).normal(0.5, 0.05, (100, 100, 3)).astype(np.float32)
    post.fill_box(img, (10, 10, 60, 60), np.random.default_rng(5), avoid=[(0, 0, 100, 100)])
    assert abs(img[10:60, 10:60].std() - 0.05) < 0.01


def test_regions_inside_plates():
    for name, labels in (("rex615", 27), ("narrow615", 11)):
        r = json.loads((SYNTH / "assets" / f"{name}-regions.json").read_text())
        tex = cv2.imread(str(SYNTH / "assets" / f"{name}-front.png"))
        assert list(tex.shape[1::-1]) == r["size_px"]
        assert len(r["labels"]) == labels
        boxes = [r["lcd"], r["port"]] + r["labels"] + [k["box"] for k in r["keys"]]
        assert all(0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1 for b in boxes)
        assert all(0 < led["x"] < 1 and 0 < led["y"] < 1 for led in r["leds"])
    narrow = json.loads((SYNTH / "assets" / "narrow615-regions.json").read_text())
    assert sorted(k["name"] for k in narrow["keys"] if k["name"][0] == "f") == ["f1", "f2", "f3", "f4"]
    assert abs(narrow["plate_mm"][0] / narrow["plate_mm"][1] - 1) < 0.05


def test_linear_is_the_srgb_decode():
    x = np.array([0.0, 0.04, 0.5, 1.0, 2.0], np.float32)
    assert np.allclose(textures.linear(x), [0.0, 0.04 / 12.92, 0.21404, 1.0, ((2.055) / 1.055) ** 2.4], atol=1e-5)

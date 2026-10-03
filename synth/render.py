import argparse
import contextlib
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import post  # noqa: E402
import textures  # noqa: E402
from scene import HOUSING_DEPTH, PORT_HEIGHT, SynthScene, box_geometry  # noqa: E402

SIZE = 1280
VIS_GRID = (12, 8)
DEVICE_ORDER = {"auto": ["OPTIX", "CUDA", "METAL"], "optix": ["OPTIX"], "cuda": ["CUDA"], "metal": ["METAL"], "cpu": []}


def load_profile(path):
    base = json.loads((ROOT / "profiles" / "base.json").read_text())
    prof = json.loads(Path(path).read_text())
    unknown = set(prof) - set(base)
    if unknown:
        raise SystemExit(f"unknown profile keys: {sorted(unknown)}")
    return {**base, **prof}


def setup_device(scene, kind):
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for t in DEVICE_ORDER[kind]:
        try:
            prefs.compute_device_type = t
        except TypeError:
            continue
        prefs.refresh_devices()
        if any(d.type == t for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == t
            scene.cycles.device = "GPU"
            return t
    if kind not in ("auto", "cpu"):
        raise SystemExit(f"device {kind} not available")
    scene.cycles.device = "CPU"
    return "CPU"


def setup_render(scene, samples, device, tmp):
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.05
    c.use_denoising = True
    c.denoiser = "OPTIX" if device == "OPTIX" else "OPENIMAGEDENOISE"
    if hasattr(c, "denoising_use_gpu"):
        c.denoising_use_gpu = device != "CPU"
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 4, 2, 2
    c.transmission_bounces, c.transparent_max_bounces = 4, 6
    c.caustics_reflective = c.caustics_refractive = False
    c.blur_glossy = 1.0
    r = scene.render
    r.resolution_x = r.resolution_y = SIZE
    r.resolution_percentage = 100
    r.use_persistent_data = True
    r.film_transparent = False
    r.image_settings.file_format = "OPEN_EXR"
    r.image_settings.color_depth = "16"
    r.filepath = str(Path(tmp) / "render.exr")
    scene.view_settings.view_transform = "Standard"


@contextlib.contextmanager
def quiet():
    sys.stdout.flush()
    saved = os.dup(1)
    null = os.open(os.devnull, os.O_WRONLY)
    os.dup2(null, 1)
    try:
        yield
    finally:
        os.dup2(saved, 1)
        os.close(null)
        os.close(saved)


def camera_space(cam, pts):
    m = np.array(cam.matrix_world.inverted())
    return pts @ m[:3, :3].T + m[:3, 3]


def to_pixels(pc, fov):
    t = math.tan(fov / 2)
    z = -pc[:, 2]
    return np.stack([(pc[:, 0] / z / t + 1) / 2 * SIZE, (1 - pc[:, 1] / z / t) / 2 * SIZE], 1)


def clip_near(poly, near=0.01):
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ina, inb = -a[2] >= near, -b[2] >= near
        if ina:
            out.append(a)
        if ina != inb:
            t = (-near - a[2]) / (b[2] - a[2])
            out.append(a + t * (b - a))
    return np.array(out)


def plate_frame(pl):
    m = np.array(pl.obj.matrix_world)
    y = HOUSING_DEPTH
    w, h = pl.width / 2, pl.height / 2
    local = np.array([[-w, y, -h, 1], [w, y, -h, 1], [w, y, h, 1], [-w, y, h, 1]])
    corners = (local @ m.T)[:, :3]
    normal = m[:3, :3] @ np.array([0, 1.0, 0])
    return corners, normal / np.linalg.norm(normal)


def housing_box(cam, pl, fov):
    """Clipped image box of the whole housing (sides and port cover included), the area to mask when a plate is dropped."""
    m = np.array(pl.obj.matrix_world)
    w, h = pl.width / 2, pl.height / 2
    v, faces, _ = box_geometry(-w, w, 0.0, HOUSING_DEPTH + PORT_HEIGHT, -h, h)
    pc = camera_space(cam, (np.c_[np.array(v), np.ones(len(v))] @ m.T)[:, :3])
    px = to_pixels(np.concatenate([q for q in (clip_near(pc[list(f)]) for f in faces) if len(q)]), fov)
    return [round(float(np.clip(c, 0, SIZE)), 2) for c in (px[:, 0].min(), px[:, 1].min(), px[:, 0].max(), px[:, 1].max())]


def visible_fraction(scene, depsgraph, cam_pos, fov, cam, pl, corners, transparent):
    nx, nz = VIS_GRID
    u = (np.arange(nx) + 0.5) / nx
    v = (np.arange(nz) + 0.5) / nz
    a, b, d = corners[0], corners[1], corners[3]
    pts = (a + u[None, :, None] * (b - a) + v[:, None, None] * (d - a)).reshape(-1, 3)
    pts = pts + (np.cross(b - a, d - a) / np.linalg.norm(np.cross(b - a, d - a))) * 0.0003
    px = to_pixels(camera_space(cam, pts), fov)
    pc = camera_space(cam, pts)
    inside = (px[:, 0] >= 0) & (px[:, 0] < SIZE) & (px[:, 1] >= 0) & (px[:, 1] < SIZE) & (-pc[:, 2] > 0.01)
    visible = 0
    name = pl.obj.name
    for p, ok in zip(pts, inside):
        if not ok:
            continue
        origin = np.array(cam_pos, float)
        vec = p - origin
        total = np.linalg.norm(vec)
        direction = vec / total
        travelled = 0.0
        for _ in range(4):
            hit, loc, _, _, ob, _ = scene.ray_cast(depsgraph, tuple(origin), tuple(direction), distance=total - travelled - 0.002)
            if not hit or ob.original.name == name:
                visible += 1
                break
            if ob.original.name not in transparent:
                break
            step = np.linalg.norm(np.array(loc) - origin) + 1e-4
            travelled += step
            origin = origin + direction * step
    return visible / len(pts)


def plate_labels(syn, placed, cam_pos, fov, p):
    scene, cam = syn.scene, syn.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()
    labels, plates = [], []
    for pl in placed:
        corners, normal = plate_frame(pl)
        center = corners.mean(0)
        view = cam_pos - center
        off = math.degrees(math.acos(np.clip(np.dot(view / np.linalg.norm(view), normal), -1, 1)))
        poly = clip_near(camera_space(cam, corners))
        info = {"kind": pl.kind, "off_normal_deg": round(off, 1), "distance_m": round(float(np.linalg.norm(view)), 3)}
        if len(poly) < 3:
            plates.append({**info, "in_view": False})
            continue
        px = to_pixels(poly, fov)
        full = [px[:, 0].min(), px[:, 1].min(), px[:, 0].max(), px[:, 1].max()]
        box = [float(np.clip(full[0], 0, SIZE)), float(np.clip(full[1], 0, SIZE)), float(np.clip(full[2], 0, SIZE)), float(np.clip(full[3], 0, SIZE))]
        in_view = box[2] - box[0] > 0.5 and box[3] - box[1] > 0.5
        info.update({"in_view": bool(in_view), "box": [round(v, 2) for v in box], "width_px": round(full[2] - full[0], 1)})
        if not in_view:
            plates.append(info)
            continue
        if pl.kind != "rex615":
            plates.append(info)
            continue
        vis = visible_fraction(scene, depsgraph, cam_pos, fov, cam, pl, corners, syn.transparent)
        reason = None
        if off > p["max_label_off_normal_deg"]:
            reason = "off_normal"
        elif full[2] - full[0] < p["min_width_px"]:
            reason = "small"
        elif vis < p["min_visible"]:
            reason = "hidden"
        info.update({"visible": round(vis, 3), "labeled": reason is None, "drop_reason": reason, "mask_box": housing_box(cam, pl, fov)})
        plates.append(info)
        if reason is None:
            labels.append(box)
    return labels, plates


def save_jpeg(rgb, path, quality):
    img = bpy.data.images.new("output", rgb.shape[1], rgb.shape[0], alpha=False, float_buffer=False)
    img.colorspace_settings.name = "sRGB"
    rgba = np.concatenate([rgb, np.ones(rgb.shape[:2] + (1,), np.float32)], -1)
    img.pixels.foreach_set(textures.srgb_rgba(rgba))
    img.file_format = "JPEG"
    img.save(filepath=str(path), quality=int(quality))
    bpy.data.images.remove(img)


def write_data_yaml(out):
    path = out / "data.yaml"
    if not path.exists():
        tmp = out / f".data-{os.getpid()}.yaml"
        tmp.write_text("train: images/train\nval: images/val\nnames:\n  0: rex615\n")
        os.replace(tmp, path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--profile", default=str(ROOT / "profiles" / "base.json"))
    ap.add_argument("--device", default="auto", choices=list(DEVICE_ORDER))
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--val-fraction", type=float, default=0.1)
    a = ap.parse_args(argv)
    p = load_profile(a.profile)
    out = Path(a.out)
    for split in ("train", "val"):
        for kind in ("images", "labels", "meta"):
            (out / kind / split).mkdir(parents=True, exist_ok=True)
    write_data_yaml(out)
    tmp = tempfile.mkdtemp(prefix="synth-")
    with quiet():
        syn = SynthScene(ROOT / "assets", p)
        scene = syn.scene
        device = setup_device(scene, a.device)
        setup_render(scene, a.samples, device, tmp)
    exr = None
    print(f"device {device}, profile {p['name']}, images {a.start} to {a.start + a.count - 1}", flush=True)
    times, t_all = [], time.time()
    for index in range(a.start, a.start + a.count):
        t0 = time.time()
        rng = np.random.default_rng([a.seed, index])
        split = "val" if np.random.default_rng([a.seed, index, 7]).random() < a.val_fraction else "train"
        want_target = rng.random() >= p["no_target_fraction"]
        placed, target, fov = syn.randomize(rng, want_target)
        cam_pos = np.array(syn.camera.location)
        labels, plates = plate_labels(syn, placed, cam_pos, fov, p)
        t1 = time.time()
        with quiet():
            bpy.ops.render.render(write_still=True)
        t2 = time.time()
        if exr is None:
            exr = bpy.data.images.load(scene.render.filepath)
        else:
            exr.reload()
        buf = np.empty(SIZE * SIZE * 4, np.float32)
        exr.pixels.foreach_get(buf)
        lin = buf.reshape(SIZE, SIZE, 4)[::-1, :, :3]
        kept = [pl for pl in plates if pl.get("labeled")]
        img, snr = post.process(lin, rng, p, syn.dark, [pl["box"] for pl in kept])
        for pl, s in zip(kept, snr):
            pl["snr"] = round(s, 2)
            if s < p["min_snr"]:
                pl.update({"labeled": False, "drop_reason": "dark"})
        labels = [pl["box"] for pl in plates if pl.get("labeled")]
        ignore = [pl["mask_box"] for pl in plates if pl.get("labeled") is False]
        if p["mask_dropped"]:
            avoid = [pl.get("mask_box", pl["box"]) for pl in plates if pl.get("in_view")]
            for pl in plates:
                if pl.get("labeled") is False:
                    box = next((b for b in (pl["mask_box"], pl["box"]) if not any(post.overlaps(b, lb) for lb in labels)), None)
                    if box:
                        post.fill_box(img, box, rng, avoid)
        name = f"s{a.seed:04d}-{index:07d}"
        quality = rng.uniform(*p["jpeg_quality"])
        save_jpeg(img, out / "images" / split / f"{name}.jpg", quality)
        lines = [f"0 {(b[0] + b[2]) / 2 / SIZE:.6f} {(b[1] + b[3]) / 2 / SIZE:.6f} {(b[2] - b[0]) / SIZE:.6f} {(b[3] - b[1]) / SIZE:.6f}" for b in labels]
        (out / "labels" / split / f"{name}.txt").write_text("".join(line + "\n" for line in lines))
        meta = {"seed": a.seed, "index": index, "profile": p["name"], "fov_deg": round(math.degrees(fov), 2), "dark": syn.dark,
                "camera": [round(float(v), 3) for v in cam_pos], "jpeg_quality": int(quality), "plates": plates, "ignore": ignore,
                "mask_dropped": p["mask_dropped"]}
        (out / "meta" / split / f"{name}.json").write_text(json.dumps(meta) + "\n")
        t3 = time.time()
        times.append((t1 - t0, t2 - t1, t3 - t2, t3 - t0))
        if (index - a.start) % 10 == 0 or index == a.start + a.count - 1:
            print(f"{name} {split} labels {len(labels)} scene {t1 - t0:.2f}s render {t2 - t1:.2f}s post {t3 - t2:.2f}s", flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    t = np.array(times)
    steady = t[1:] if len(t) > 1 else t
    print(f"done {len(t)} images in {time.time() - t_all:.1f}s; mean per image after the first: scene {steady[:, 0].mean():.2f}s "
          f"render {steady[:, 1].mean():.2f}s post {steady[:, 2].mean():.2f}s total {steady[:, 3].mean():.2f}s", flush=True)


if __name__ == "__main__":
    main()

from dataclasses import dataclass

import numpy as np

from pipeline import sphere

TILE_SIZE = 1280
TILE_FOV = np.radians(60.0)
TILE_YAWS = 12
TILE_PITCHES = np.radians([-30.0, 0.0, 30.0])
EDGE_MARGIN = 2.0
BORDER_SAMPLES = 16


@dataclass(frozen=True)
class TileSpec:
    index: int
    yaw: float
    pitch: float
    fov: float = TILE_FOV
    size: int = TILE_SIZE


def tile_specs():
    specs = []
    for pitch in TILE_PITCHES:
        for k in range(TILE_YAWS):
            specs.append(TileSpec(len(specs), float(2 * np.pi * k / TILE_YAWS), float(pitch)))
    return specs


def render_tiles(faces, specs=None):
    for spec in specs or tile_specs():
        yield spec, sphere.render_tile(faces, spec.yaw, spec.pitch, spec.fov, spec.size)


def dirs_to_tile_pixel(spec, dirs):
    """World unit dirs (..., 3) to continuous tile pixel coords. Points behind the camera get NaN."""
    f, r, up = sphere.tile_basis(spec.yaw, spec.pitch)
    t = np.tan(spec.fov / 2)
    z = dirs @ f
    with np.errstate(divide="ignore", invalid="ignore"):
        x = ((dirs @ r) / z / t + 1) / 2 * spec.size
        y = (1 - (dirs @ up) / z / t) / 2 * spec.size
    behind = z <= 1e-6
    return np.where(behind, np.nan, x), np.where(behind, np.nan, y)


def touches_edge(spec, xyxy):
    x0, y0, x1, y1 = xyxy
    return min(x0, y0) <= EDGE_MARGIN or max(x1, y1) >= spec.size - EDGE_MARGIN


def tile_box_to_pano(spec, xyxy, pano_width, pano_height):
    """Tile box (x0, y0, x1, y1) to an equirect box (x, y, w, h) with 0 <= x < pano_width.

    x + w can exceed pano_width when the box crosses the panorama seam."""
    x0, y0, x1, y1 = xyxy
    t = np.linspace(0, 1, BORDER_SAMPLES)
    xs = np.concatenate([x0 + (x1 - x0) * t, np.full_like(t, x1), x1 - (x1 - x0) * t, np.full_like(t, x0)])
    ys = np.concatenate([np.full_like(t, y0), y0 + (y1 - y0) * t, np.full_like(t, y1), y1 - (y1 - y0) * t])
    u, v = sphere.dirs_to_equirect(sphere.tile_pixel_to_dir(spec.yaw, spec.pitch, spec.fov, spec.size, xs, ys), pano_width, pano_height)
    cu, _ = sphere.dirs_to_equirect(
        sphere.tile_pixel_to_dir(spec.yaw, spec.pitch, spec.fov, spec.size, (x0 + x1) / 2, (y0 + y1) / 2), pano_width, pano_height
    )
    u = cu + np.mod(u - cu + pano_width / 2, pano_width) - pano_width / 2
    left = u.min()
    return (float(np.mod(left, pano_width)), float(v.min()), float(u.max() - left), float(v.max() - v.min()))


def _intersection(a, b, pano_width):
    best = 0.0
    for shift in (-pano_width, 0.0, pano_width):
        iw = min(a[0] + a[2], b[0] + shift + b[2]) - max(a[0], b[0] + shift)
        ih = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
        if iw > 0 and ih > 0:
            best = max(best, iw * ih)
    return best


def nms_pano(boxes, scores, edge, pano_width, threshold=0.6):
    """Greedy NMS on equirect boxes (x, y, w, h) by intersection over the smaller area.

    Boxes that do not touch a tile edge win over cut boxes. Returns kept indices and the
    best score of each kept group."""
    order = sorted(range(len(boxes)), key=lambda i: (bool(edge[i]), -scores[i]))
    kept, groups = [], []
    for i in order:
        a = boxes[i]
        for g, k in enumerate(kept):
            b = boxes[k]
            if _intersection(a, b, pano_width) / max(min(a[2] * a[3], b[2] * b[3]), 1e-9) >= threshold:
                groups[g].append(i)
                break
        else:
            kept.append(i)
            groups.append([i])
    return kept, [max(scores[j] for j in g) for g in groups]

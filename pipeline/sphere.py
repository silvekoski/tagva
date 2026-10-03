import numpy as np
import cv2

FACE_SIZE = 4096
FACE_FOCAL = 2048.0
REMAP_COLS = 4096


def lonlat_to_dirs(lon, lat):
    cl = np.cos(lat)
    return np.stack([cl * np.cos(lon), cl * np.sin(lon), np.sin(lat)], -1)


def dirs_to_equirect(d, w, h):
    lon = np.arctan2(d[..., 1], d[..., 0])
    lat = np.arcsin(np.clip(d[..., 2], -1.0, 1.0))
    return (np.pi - lon) / (2 * np.pi) * w, (np.pi / 2 - lat) / np.pi * h


def equirect_to_dirs(u, v, w, h):
    return lonlat_to_dirs(np.pi - np.asarray(u) / w * 2 * np.pi, np.pi / 2 - np.asarray(v) / h * np.pi)


def equirect_grid_dirs(w, h, row0=0, row1=None):
    row1 = h if row1 is None else row1
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(row0, row1) + 0.5)
    return equirect_to_dirs(u, v, w, h)


def tile_basis(yaw, pitch):
    f = lonlat_to_dirs(np.float64(yaw), np.float64(pitch))
    r = np.cross(f, [0.0, 0.0, 1.0])
    r /= np.linalg.norm(r)
    return f, r, np.cross(r, f)


def tile_dirs(yaw, pitch, fov, size):
    f, r, up = tile_basis(yaw, pitch)
    s = np.tan(fov / 2) * ((np.arange(size) + 0.5) / size * 2 - 1)
    d = f + s[None, :, None] * r - s[:, None, None] * up
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def tile_pixel_to_dir(yaw, pitch, fov, size, x, y):
    f, r, up = tile_basis(yaw, pitch)
    t = np.tan(fov / 2)
    d = f + (np.asarray(x) / size * 2 - 1)[..., None] * t * r - (np.asarray(y) / size * 2 - 1)[..., None] * t * up
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def sample_cube(faces, dirs):
    """faces: list of (image, R cam-to-world). dirs: (..., 3) world unit vectors."""
    shape = dirs.shape[:-1]
    d = dirs.reshape(-1, 3)
    cams = [d @ R for _, R in faces]
    best = np.argmax(np.stack([-c[:, 2] for c in cams]), 0)
    out = np.zeros((d.shape[0], 3), np.uint8)
    for k, (img, _) in enumerate(faces):
        m = best == k
        if not m.any():
            continue
        c = cams[k][m]
        z = -c[:, 2]
        n = len(z)
        pad = -n % REMAP_COLS
        mx = np.pad(FACE_SIZE / 2 + FACE_FOCAL * c[:, 0] / z - 0.5, (0, pad)).astype(np.float32).reshape(-1, REMAP_COLS)
        my = np.pad(FACE_SIZE / 2 - FACE_FOCAL * c[:, 1] / z - 0.5, (0, pad)).astype(np.float32).reshape(-1, REMAP_COLS)
        sampled = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        out[m] = sampled.reshape(-1, 3)[:n]
    return out.reshape(*shape, 3)


def render_tile(faces, yaw, pitch, fov, size):
    return sample_cube(faces, tile_dirs(yaw, pitch, fov, size))


def render_equirect(faces, w, h, strip=256):
    out = np.empty((h, w, 3), np.uint8)
    for r0 in range(0, h, strip):
        r1 = min(h, r0 + strip)
        out[r0:r1] = sample_cube(faces, equirect_grid_dirs(w, h, r0, r1))
    return out

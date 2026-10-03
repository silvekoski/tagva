import math

import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def gaussian(img, sigma):
    if sigma < 0.2:
        return img
    r = max(1, int(math.ceil(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2).astype(np.float32)
    k /= k.sum()
    for axis in (0, 1):
        pad = [(0, 0)] * img.ndim
        pad[axis] = (r, r)
        p = np.pad(img, pad, mode="edge")
        n = img.shape[axis]
        out = np.zeros_like(img)
        for i, w in enumerate(k):
            out += w * (p[i:i + n] if axis == 0 else p[:, i:i + n])
        img = out
    return img


def bilinear(img, h, w):
    """Bilinear point sampling without a prefilter, like cv2.remap in pipeline.sphere.sample_cube."""
    for axis, n in ((0, h), (1, w)):
        size = img.shape[axis]
        pos = np.clip((np.arange(n) + 0.5) * size / n - 0.5, 0, size - 1)
        i0 = np.floor(pos).astype(int)
        i1 = np.minimum(i0 + 1, size - 1)
        f = (pos - i0).astype(np.float32).reshape((-1, 1, 1) if axis == 0 else (1, -1, 1))
        a = np.take(img, i0, axis)
        img = a + (np.take(img, i1, axis) - a) * f
    return img


def log_uniform(rng, lo, hi):
    return math.exp(rng.uniform(math.log(lo), math.log(hi)))


def white_balance(lin, rng, p):
    """Gray world gains on the mid tones (camera auto white balance), partial strength, plus a residual cast."""
    lum = lin @ LUMA
    lo, hi = np.percentile(lum[::4, ::4], [5, 95])
    m = (lum > lo) & (lum < hi)
    means = lin[m].mean(0) if m.sum() > 100 else lin.reshape(-1, 3).mean(0)
    gains = (means @ LUMA) / np.maximum(means, 1e-6)
    gains = gains ** rng.uniform(*p["wb_strength"]) * np.array(p["wb_bias"]) * (1 + rng.normal(0, p["wb_jitter"], 3))
    return lin * (gains / (gains @ LUMA)).astype(np.float32)


def tone(x, k):
    x = np.where(x < k, x, k + (1 - k) * (1 - np.exp(-(x - k) / (1 - k))))
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(np.maximum(x, 0.0031308), 1 / 2.4) - 0.055)


def box_snr(x, box, shot, read, k):
    """Texture contrast of the clean crop over the sensor noise, both in display values."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    c = x[y0:max(y1, y0 + 1), x0:max(x1, x0 + 1)] @ LUMA
    if c.size < 4:
        return 0.0
    signal = float(tone(c, k).std())
    slope = (tone(c + 1e-3, k) - tone(c, k)) / 1e-3
    noise = float((np.sqrt(shot * c + read * read) * slope).mean())
    return signal / max(noise, 1e-6)


def process(lin, rng, p, dark, boxes=()):
    """Linear render (H, W, 3) -> (sRGB float image, SNR of each box) with white balance, exposure, noise,
    tone curve and resample blur."""
    lin = white_balance(lin, rng, p)
    lum = lin @ LUMA
    mean = float(np.minimum(lum, np.percentile(lum[::2, ::2], 99.5)).mean())
    target = log_uniform(rng, *(p["brightness_dark"] if dark else p["brightness"]))
    x = lin * (target / max(mean, 1e-6))
    gain = p["dark_noise_gain"] if dark else 1.0
    shot = rng.uniform(*p["shot_noise"]) * gain
    read = rng.uniform(*p["read_noise"]) * gain
    k = rng.uniform(*p["shoulder"])
    snr = [box_snr(x, b, shot, read, k) for b in boxes]
    x = x + rng.standard_normal(x.shape, dtype=np.float32) * np.sqrt(shot * np.maximum(x, 0) + read * read)
    x = tone(np.maximum(x, 0), k)
    if rng.random() < p["resample_prob"]:
        s = rng.uniform(*p["resample"])
        h, w = x.shape[:2]
        x = bilinear(bilinear(x, int(h / s), int(w / s)), h, w)
    x = gaussian(x, rng.uniform(*p["blur_sigma"]))
    if rng.random() < p["sharpen_prob"]:
        x = x + rng.uniform(*p["sharpen"]) * (x - gaussian(x, rng.uniform(0.7, 1.5)))
    return np.clip(x, 0, 1).astype(np.float32), snr


def overlaps(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def fill_box(img, box, rng, avoid=()):
    """Cover an unlabeled plate area with a neighboring patch that touches no box in avoid. Fallback: the mean color
    with noise at the level of the region (robust MAD estimate)."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    if x1 - x0 < 2 or y1 <= y0:
        return
    w, h = x1 - x0, y1 - y0
    H, W = img.shape[:2]
    shifts = [(-w, 0), (w, 0), (0, -h), (0, h)]
    for k in rng.permutation(len(shifts)):
        dx, dy = (int(round(v * 1.1)) for v in shifts[k])
        src = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        if src[0] >= 0 and src[1] >= 0 and src[2] <= W and src[3] <= H and not any(overlaps(src, b) for b in avoid):
            img[y0:y1, x0:x1] = img[src[1]:src[3], src[0]:src[2]]
            return
    region = img[y0:y1, x0:x1]
    sigma = np.median(np.abs(np.diff(region, axis=1)), axis=(0, 1)) / 0.6745 / math.sqrt(2)
    region[:] = region.reshape(-1, 3).mean(0) + rng.normal(0, 1, region.shape).astype(np.float32) * np.maximum(sigma, 0.004)

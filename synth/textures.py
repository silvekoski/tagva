import json

import numpy as np

LABEL_WORDS = [
    "CB", "Q0", "Q1", "Q8", "Q9", "OPEN", "CLOSE", "AR", "ON", "OFF", "BLOCK", "LOCAL", "REMOTE", "I>", "I>>", "Io>", "U<", "U>",
    "f<", "TRIP", "ALARM", "SF6", "LOW", "EF", "DIFF", "TEMP", "FAIL", "TCS", "CBFP", "ARC", "LOCKOUT", "RESET", "GAS", "SPRING",
    "CHARGED", "EARTH", "LINE", "BUS", "TR1", "TR2", "M1", "FEEDER", "INCOMER", "VT", "MCB", "DC", "AUX", "HEAT", "FAN", "DOOR",
]
LCD_WORDS = ["U12=", "U23=", "IL1=", "IL2=", "IL3=", "P=", "Q=", "f=", "Io=", "cos=", "SLD", "page", "Main", "menu", "Events", "Measure"]
LCD_UNITS = ["kV", "A", "kW", "kVAr", "Hz", "%", ""]
LED_COLORS = {
    "green": (0.25, 1.0, 0.35), "red": (1.0, 0.12, 0.08), "yellow": (1.0, 0.75, 0.1), "white": (1.0, 1.0, 0.95),
}
LED_OFF = np.array([0.6, 0.62, 0.63])


def srgb_rgba(img):
    """Blender image pixels: (H, W, 4) top-down float -> flat bottom-up array for foreach_set."""
    return np.ascontiguousarray(img[::-1]).ravel()


def linear(x):
    """sRGB display values -> linear values (emission maps are linear float images)."""
    x = np.asarray(x, np.float32)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def resize_axis(img, n_out, axis):
    """Exact area average when shrinking (from the cumulative sum), bilinear when growing. O(n) per axis."""
    img = np.moveaxis(np.asarray(img, np.float32), axis, 0)
    n_in = img.shape[0]
    if n_out == n_in:
        out = img
    elif n_out < n_in:
        c = np.concatenate([np.zeros((1,) + img.shape[1:], np.float64), np.cumsum(img, 0, dtype=np.float64)])
        e = np.linspace(0, n_in, n_out + 1)
        i = np.minimum(np.floor(e).astype(int), n_in - 1)
        f = (e - i).reshape((-1,) + (1,) * (img.ndim - 1))
        ce = c[i] + f * (c[i + 1] - c[i])
        out = ((ce[1:] - ce[:-1]) * (n_out / n_in)).astype(np.float32)
    else:
        pos = np.clip((np.arange(n_out) + 0.5) * n_in / n_out - 0.5, 0, n_in - 1)
        i0 = np.floor(pos).astype(int)
        i1 = np.minimum(i0 + 1, n_in - 1)
        f = (pos - i0).astype(np.float32).reshape((-1,) + (1,) * (img.ndim - 1))
        out = img[i0] * (1 - f) + img[i1] * f
    return np.moveaxis(out, 0, axis)


def resize(img, h, w):
    """Area resize when shrinking, bilinear when growing. img (H, W) or (H, W, C)."""
    return resize_axis(resize_axis(img, h, 0), w, 1)


class Glyphs:
    def __init__(self, atlas, meta_path):
        meta = json.loads(open(meta_path).read())
        self.atlas = atlas
        self.chars = {c: i for i, c in enumerate(meta["chars"])}
        self.fonts = {f: i for i, f in enumerate(meta["fonts"])}
        self.cw, self.ch = meta["cell"]
        self.advance = meta["advance"]
        self.cache = {}

    def text_mask(self, text, font, height):
        key = (text, font, height)
        if key in self.cache:
            return self.cache[key]
        row = self.fonts[font]
        parts = []
        for c in text:
            i = self.chars.get(c, self.chars[" "])
            cell = self.atlas[row * self.ch:(row + 1) * self.ch, i * self.cw:(i + 1) * self.cw]
            adv = self.advance[font][i]
            x0 = max(0, (self.cw - adv) // 2)
            parts.append(cell[:, x0:x0 + adv])
        strip = np.concatenate(parts, 1) if parts else np.zeros((self.ch, 1), np.float32)
        h = max(2, int(round(height)))
        w = max(1, int(round(strip.shape[1] * h / self.ch)))
        mask = np.clip(resize(strip, h, w), 0, 1)
        if len(self.cache) > 4000:
            self.cache.clear()
        self.cache[key] = mask
        return mask

    def draw(self, img, text, font, x, y, height, color, alpha=1.0, max_width=None):
        """Draw text with the top left of the glyph cell at (x, y) in px. Clips to img."""
        m = self.text_mask(text, font, height)
        if max_width is not None and m.shape[1] > max_width:
            m = m[:, :int(max_width)]
        x, y = int(round(x)), int(round(y))
        H, W = img.shape[:2]
        x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + m.shape[1], W), min(y + m.shape[0], H)
        if x1 <= x0 or y1 <= y0:
            return
        a = (m[y0 - y:y1 - y, x0 - x:x1 - x] * alpha)[..., None]
        img[y0:y1, x0:x1, :3] = img[y0:y1, x0:x1, :3] * (1 - a) + np.asarray(color, np.float32) * a


def random_word(rng):
    if rng.random() < 0.7:
        return " ".join(rng.choice(LABEL_WORDS, rng.integers(1, 3)))
    alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-")
    return "".join(rng.choice(alphabet, rng.integers(2, 8)))


def smooth_noise(rng, h, w, cells):
    g = rng.random((cells + 1, cells + 1)).astype(np.float32)
    return resize(g, h, w)


class PlateTexture:
    """Randomized REX615 (or narrow 615) front plate. Works at a fixed px size; regions come from the regions JSON."""

    def __init__(self, base, regions, glyphs):
        self.base = base
        self.h, self.w = base.shape[:2]
        self.glyphs = glyphs
        self.lcd = self.box(regions["lcd"])
        self.labels = [self.box(b) for b in regions["labels"]]
        self.leds = [(led["name"], led["x"] * self.w, led["y"] * self.h, led["r"] * self.w, led["color"]) for led in regions["leds"]]
        gray = base[..., :3].mean(-1)
        sat = base[..., :3].max(-1) - base[..., :3].min(-1)
        self.key_mask = np.zeros((self.h, self.w), bool)
        for k in regions["keys"]:
            x0, y0, x1, y1 = self.box(k["box"])
            self.key_mask[y0:y1, x0:x1] = True
        self.key_mask &= (gray > 0.4) & (gray < 0.8) & (sat < 0.12)
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        self.led_masks = []
        for _, x, y, r, _ in self.leds:
            x0, y0, x1, y1 = int(x - r - 2), int(y - r - 2), int(x + r + 3), int(y + r + 3)
            d = np.hypot(xx[y0:y1, x0:x1] + 0.5 - x, yy[y0:y1, x0:x1] + 0.5 - y)
            self.led_masks.append(((y0, y1, x0, x1), np.clip(r - d + 0.5, 0, 1)[..., None].astype(np.float32)))

    def box(self, b):
        return int(round(b[0] * self.w)), int(round(b[1] * self.h)), int(round(b[2] * self.w)), int(round(b[3] * self.h))

    def generate(self, rng, p):
        img = self.base.copy()
        emit = np.zeros((self.h, self.w, 3), np.float32)
        if rng.random() < p["key_lighten_prob"]:
            a = rng.uniform(0.3, 0.85)
            img[self.key_mask, :3] = img[self.key_mask, :3] * (1 - a) + 0.88 * a
        self.label_strips(img, rng, p)
        self.lcd_content(img, emit, rng, p)
        self.led_states(img, emit, rng, p)
        tint = 1 + rng.normal(0, 0.012, 3)
        img[..., :3] *= tint * rng.uniform(0.92, 1.06)
        if rng.random() < p["plate_dirt_prob"]:
            dirt = smooth_noise(rng, self.h, self.w, int(rng.integers(3, 12)))
            img[..., :3] *= (1 - rng.uniform(0.05, 0.25) * dirt ** 3)[..., None]
        np.clip(img, 0, 1, out=img)
        return img, emit

    def label_strips(self, img, rng, p):
        mode = rng.choice(["blank", "pocket", "printed", "hand"], p=p["label_modes"])
        base_col = {"blank": rng.uniform(0.9, 1.0), "pocket": rng.uniform(0.62, 0.85)}.get(mode, rng.uniform(0.85, 1.0))
        for x0, y0, x1, y1 in self.labels:
            col = np.clip(base_col + rng.normal(0, 0.015), 0, 1) * np.array([1.0, 1.0, rng.uniform(0.95, 1.0)])
            img[y0:y1, x0:x1, :3] = col
            if mode in ("printed", "hand") and rng.random() < p["label_fill_prob"]:
                h = y1 - y0
                lines = 1 if h < 30 or rng.random() < 0.6 else 2
                th = h / (lines + 0.6) * rng.uniform(0.8, 1.15)
                font = "hand" if mode == "hand" else ("sans" if rng.random() < 0.7 else "bold")
                ink = (0.05, 0.05, 0.08) if rng.random() < 0.8 else (0.1, 0.15, 0.5)
                for li in range(lines):
                    self.glyphs.draw(img, random_word(rng), font, x0 + rng.uniform(1, 6), y0 + (li + 0.2) * th - th * 0.15,
                                     th * 1.3, ink, rng.uniform(0.6, 1.0), max_width=x1 - x0 - 2)
            if rng.random() < p["label_wear_prob"]:
                wear = smooth_noise(rng, y1 - y0, x1 - x0, 4)[..., None]
                img[y0:y1, x0:x1, :3] = img[y0:y1, x0:x1, :3] * (1 - 0.35 * wear) + 0.75 * 0.35 * wear
        if rng.random() < 0.5:
            pocket = rng.uniform(0.0, 0.12)
            for x0, y0, x1, y1 in self.labels:
                img[y0:y1, x0:x1, :3] *= 1 - pocket

    def lcd_content(self, img, emit, rng, p):
        x0, y0, x1, y1 = self.lcd
        state = rng.choice(["off", "dim", "lit", "reference"], p=p["lcd_states"])
        if state == "reference":
            emit[y0:y1, x0:x1] = linear(img[y0:y1, x0:x1, :3] * rng.uniform(0.04, 0.3))
            return
        if state == "lit":
            bg = np.array(rng.choice([[0.72, 0.82, 0.98], [0.85, 0.9, 0.95], [0.75, 0.9, 0.75]])) + rng.normal(0, 0.03, 3)
            ink = np.array([0.15, 0.2, 0.55]) if rng.random() < 0.7 else np.array([0.08, 0.08, 0.1])
        else:
            bg = np.array([0.55, 0.58, 0.5]) * rng.uniform(0.75, 1.15) + rng.normal(0, 0.02, 3)
            ink = bg * 0.55
        img[y0:y1, x0:x1, :3] = np.clip(bg, 0, 1)
        h, w = y1 - y0, x1 - x0
        if state != "off" or rng.random() < 0.15:
            th = h / rng.uniform(7, 11)
            y = y0 + th * 0.3
            if rng.random() < 0.6:
                self.glyphs.draw(img, " ".join(rng.choice(LCD_WORDS, 2)), "sans", x0 + w * 0.15, y, th, ink, 0.9, max_width=w)
                yy = int(y + th * 1.1)
                img[yy:yy + max(1, int(th * 0.08)), x0 + 4:x1 - 4, :3] = ink
                y += th * 1.4
            while y < y1 - th:
                if rng.random() < 0.25:
                    cx = int(x0 + rng.uniform(0.5, 0.9) * w)
                    img[int(y):int(y + th), cx:cx + max(1, int(th * 0.08)), :3] = ink
                else:
                    text = f"{rng.choice(LCD_WORDS)}{rng.uniform(0, 999):.{int(rng.integers(0, 3))}f}{rng.choice(LCD_UNITS)}"
                    self.glyphs.draw(img, text, "sans", x0 + w * 0.03, y, th, ink, 0.9, max_width=w * 0.95)
                y += th * rng.uniform(1.0, 1.4)
        if state == "lit":
            emit[y0:y1, x0:x1] = linear(img[y0:y1, x0:x1, :3] * rng.uniform(0.04, 0.3))
        elif rng.random() < 0.5:
            glare = smooth_noise(rng, h, w, 3)[..., None]
            img[y0:y1, x0:x1, :3] = np.clip(img[y0:y1, x0:x1, :3] + 0.15 * glare ** 2, 0, 1)

    def led_states(self, img, emit, rng, p):
        for (name, _, _, _, color), ((y0, y1, x0, x1), m) in zip(self.leds, self.led_masks):
            on_prob = p["led_ready_on_prob"] if name == "ready" else p["led_on_prob"]
            if rng.random() < on_prob:
                if color == "any":
                    color = rng.choice(["red", "yellow", "green"])
                c = np.array(LED_COLORS[color])
                img[y0:y1, x0:x1, :3] = img[y0:y1, x0:x1, :3] * (1 - m) + (0.6 + 0.4 * c) * m
                emit[y0:y1, x0:x1] = emit[y0:y1, x0:x1] * (1 - m) + linear(c) * m * rng.uniform(1.5, 4.0)
            else:
                off = LED_OFF * rng.uniform(0.85, 1.05)
                img[y0:y1, x0:x1, :3] = img[y0:y1, x0:x1, :3] * (1 - m) + off * m


def generic_device(rng, glyphs, w, h):
    """Other relays, meters and displays: a body, a screen, a key grid, LEDs and text. Returns (color, emission)."""
    body = rng.choice([[0.85, 0.86, 0.86], [0.93, 0.93, 0.92], [0.55, 0.57, 0.6], [0.2, 0.21, 0.23], [0.8, 0.78, 0.7], [0.3, 0.35, 0.45]])
    img = np.ones((h, w, 4), np.float32)
    img[..., :3] = np.array(body) + rng.normal(0, 0.02, 3)
    emit = np.zeros((h, w, 3), np.float32)
    b = int(rng.uniform(0.02, 0.08) * min(w, h))
    frame = np.clip(np.array(body) * rng.uniform(0.7, 1.2), 0, 1)
    img[:b, :, :3] = frame
    img[-b:, :, :3] = frame
    img[:, :b, :3] = frame
    img[:, -b:, :3] = frame
    sx0, sy0 = rng.uniform(0.1, 0.5) * w, rng.uniform(0.08, 0.35) * h
    sw, sh = rng.uniform(0.25, 0.55) * w, rng.uniform(0.15, 0.4) * h
    sx1, sy1 = int(min(w - b, sx0 + sw)), int(min(h - b, sy0 + sh))
    sx0, sy0 = int(sx0), int(sy0)
    kind = rng.choice(["lcd", "dark", "segment", "blue"])
    scr = {"lcd": [0.55, 0.62, 0.45], "dark": [0.05, 0.06, 0.07], "segment": [0.05, 0.05, 0.05], "blue": [0.6, 0.75, 0.95]}[kind]
    img[sy0:sy1, sx0:sx1, :3] = scr
    th = max(4, (sy1 - sy0) / rng.uniform(3, 6))
    ink = {"lcd": (0.1, 0.12, 0.1), "dark": (0.3, 0.9, 0.4), "segment": (1.0, 0.25, 0.1), "blue": (0.1, 0.1, 0.4)}[kind]
    y = sy0 + 2
    while y < sy1 - th:
        glyphs.draw(img, f"{rng.uniform(0, 9999):.1f}" if kind == "segment" else random_word(rng), "bold" if kind == "segment" else "sans",
                    sx0 + 3, y, th, ink, 1.0, max_width=sx1 - sx0 - 4)
        y += th * 1.2
    if kind in ("dark", "segment", "blue") and rng.random() < 0.7:
        emit[sy0:sy1, sx0:sx1] = linear(img[sy0:sy1, sx0:sx1, :3]) * rng.uniform(0.5, 2.0)
    key_col = np.clip(np.array(body) * rng.uniform(0.5, 1.3) + rng.uniform(-0.1, 0.1), 0, 1)
    rows, cols = int(rng.integers(1, 5)), int(rng.integers(1, 6))
    kx0, ky0 = rng.uniform(0.08, 0.3) * w, max(sy1 + 0.05 * h, rng.uniform(0.45, 0.6) * h)
    kw, kh = (w * 0.9 - kx0) / cols, (h * 0.92 - ky0) / rows
    for r in range(rows):
        for c in range(cols):
            if rng.random() < 0.85 and kh > 3 and kw > 3:
                x, y = int(kx0 + c * kw), int(ky0 + r * kh)
                img[y:y + int(kh * 0.7), x:x + int(kw * 0.7), :3] = key_col
    for _ in range(int(rng.integers(0, 8))):
        x, y = int(rng.uniform(0.05, 0.95) * w), int(rng.uniform(0.05, 0.95) * h)
        r = max(1, int(0.015 * w))
        c = np.array(LED_COLORS[rng.choice(list(LED_COLORS))])
        on = rng.random() < 0.4
        img[y - r:y + r, x - r:x + r, :3] = c * (0.9 if on else 0.4)
        if on:
            emit[y - r:y + r, x - r:x + r] = linear(c) * 2
    if rng.random() < 0.6:
        logo = rng.choice(["ABB", "SEL", "GE", "VAMP", "SIEMENS", "SEPAM", "MICOM", "615", "620", "630", "REF", "RET"])
        col = (0.85, 0.1, 0.1) if rng.random() < 0.5 else (0.1, 0.1, 0.1)
        glyphs.draw(img, logo, "bold", rng.uniform(0.05, 0.7) * w, b + 2, max(4, 0.07 * h), col, 1.0)
    return np.clip(img, 0, 1), emit


def nameplate(rng, glyphs, w, h, kind):
    """kind: nameplate, tape, sticker. Returns RGBA."""
    img = np.zeros((h, w, 4), np.float32)
    img[..., 3] = 1
    if kind == "tape":
        img[..., :3] = np.array([1.0, 0.45, 0.08]) * rng.uniform(0.85, 1.05) + rng.normal(0, 0.02, 3)
        th = h * rng.uniform(0.3, 0.45)
        lines = int(rng.integers(1, 3))
        for li in range(lines):
            glyphs.draw(img, random_word(rng), "hand", rng.uniform(0.02, 0.2) * w, h * 0.08 + li * th * 1.1, th * 1.3, (0.05, 0.05, 0.05), 0.9)
        return np.clip(img, 0, 1)
    if kind == "sticker":
        shape = rng.choice(["circle", "triangle", "rect"])
        col = np.array(rng.choice([[1.0, 0.85, 0.05], [0.95, 0.95, 0.95], [0.1, 0.3, 0.8], [0.9, 0.1, 0.1], [0.2, 0.7, 0.3]]))
        yy, xx = (np.mgrid[0:h, 0:w] + 0.5) / np.array([h, w])[:, None, None]
        if shape == "circle":
            a = (np.hypot(xx - 0.5, yy - 0.5) < 0.5).astype(np.float32)
        elif shape == "triangle":
            a = ((yy > 0.1) & (np.abs(xx - 0.5) < (yy - 0.1) * 0.55)).astype(np.float32)
        else:
            a = np.ones((h, w), np.float32)
        img[..., :3] = col
        img[..., 3] = a
        glyphs.draw(img, random_word(rng)[:4], "bold", w * 0.25, h * 0.35, h * 0.25, (0.05, 0.05, 0.05), 0.9)
        return np.clip(img, 0, 1)
    dark = rng.random() < 0.3
    img[..., :3] = (0.12 if dark else rng.uniform(0.88, 1.0)) + rng.normal(0, 0.01, 3)
    ink = (0.95, 0.95, 0.95) if dark else (0.05, 0.05, 0.05)
    glyphs.draw(img, random_word(rng)[:10], "bold", w * 0.08, h * 0.12, h * 0.42, ink, 1.0, max_width=w * 0.9)
    glyphs.draw(img, " ".join(rng.choice(LABEL_WORDS, 2)), "sans", w * 0.08, h * 0.58, h * 0.3, ink, 1.0, max_width=w * 0.9)
    return np.clip(img, 0, 1)


def vent(h, w, slats):
    img = np.ones((h, w, 4), np.float32)
    img[..., :3] = 0.75
    period = h / slats
    rows = (np.arange(h) % period) / period
    img[(rows > 0.45), :, :3] = 0.08
    img[:4, :, :3] = img[-4:, :, :3] = img[:, :4, :3] = img[:, -4:, :3] = 0.8
    return img


def opening(rng, h, w):
    img = np.ones((h, w, 4), np.float32)
    img[..., :3] = 0.03
    for _ in range(int(rng.integers(3, 12))):
        x = int(rng.uniform(0, w))
        c = np.array(rng.choice([[0.6, 0.5, 0.05], [0.1, 0.1, 0.1], [0.5, 0.5, 0.5], [0.2, 0.4, 0.15]]))
        img[:, x:x + int(rng.integers(3, 20)), :3] = c * rng.uniform(0.2, 0.6)
    return img

import json
import multiprocessing
import os
import re
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from functools import cache
from itertools import repeat
from pathlib import Path

import cv2
import numpy as np

from pipeline import sphere

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("FLAGS_use_system_allocator", "1")

DET_MODEL = "PP-OCRv5_mobile_det"
REC_MODEL = "PP-OCRv5_server_rec"
DET_SIDE = 1280
REC_BATCH = 8
WORKERS = int(os.environ.get("REX_OCR_WORKERS", (os.cpu_count() or 2) // 2 + 1))
VIEW_MARGIN = 0.25
LABEL_VIEW_WIDTH = 320
LABEL_PAD = 1.0
VIEW_MAX_SIZE = 2048
STOPLIST = Path(__file__).with_name("ocr-stoplist.json")
CONFUSABLE = str.maketrans("OILSZB", "011528")


class Models:
    """The PP-OCRv5 predictors of one process. A Paddle CPU predictor uses one core here, so Ocr runs several."""

    def __init__(self, det_model, rec_model, device, det_side):
        from paddleocr import TextDetection, TextRecognition

        self.det = TextDetection(model_name=det_model, device=device, limit_side_len=det_side, limit_type="max")
        self.rec = TextRecognition(model_name=rec_model, device=device)

    def detect(self, image):
        (r,) = self.det.predict([image], batch_size=1)
        return [(np.asarray(p, np.float64).reshape(4, 2), float(s)) for p, s in zip(r["dt_polys"], r["dt_scores"])]

    def recognize(self, crops):
        return [(str(r["rec_text"]), float(r["rec_score"])) for r in self.rec.predict(list(crops), batch_size=REC_BATCH)]

    def read(self, image):
        polys = reading_order(p for p, _ in self.detect(image))
        return self.recognize([line_crop(image, p) for p in polys] or [image])


_models = None


def _start(*args):
    global _models
    _models = Models(*args)


def _work(method, item):
    return getattr(_models, method)(item)


class Ocr:
    def __init__(self, det_model=DET_MODEL, rec_model=REC_MODEL, device="cpu", det_side=DET_SIDE, workers=WORKERS):
        """workers: number of worker processes, each with its own predictors. 0 runs the predictors in this process."""
        args = (det_model, rec_model, device, det_side)
        self.models = None if workers else Models(*args)
        self.pool = ProcessPoolExecutor(workers, multiprocessing.get_context("spawn"), initializer=_start, initargs=args) if workers else None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.pool is not None:
            self.pool.shutdown(cancel_futures=True)

    def _map(self, method, items):
        """Iterator over the results of the items. The worker processes get all items at once."""
        if self.pool is None:
            return (getattr(self.models, method)(item) for item in items)
        return self.pool.map(_work, repeat(method), items)

    def _recognize(self, crops):
        crops = list(crops)
        batches = self._map("recognize", [crops[i:i + REC_BATCH] for i in range(0, len(crops), REC_BATCH)])
        return (r for batch in batches for r in batch)

    def detect(self, images):
        return list(self._map("detect", images))

    def recognize(self, crops):
        return list(self._recognize(crops))

    def read(self, image):
        """Text lines of one view in reading order: list of (text, score). One line of the full view when no text is detected."""
        return self.reads([image])[0]

    def reads(self, images):
        return list(self._map("read", images))

    def labels(self, faces, boxes, pano_width, pano_height):
        """Cabinet labels among the pano text line boxes of one sweep: list of (block box, detection score, text, text score)."""
        return self.read_labels(label_views(faces, boxes, pano_width, pano_height))

    def read_labels(self, views):
        """Cabinet labels of the label_views output. It does not need the faces."""
        single = self._recognize(v for _, _, n, v in views if n == 1)
        multi = self._map("read", [v for _, _, n, v in views if n > 1])
        out = []
        for box, score, n, _ in views:
            text, text_score = label_text([next(single)] if n == 1 else next(multi))
            if is_cabinet_label(text, text_score):
                out.append((box, score, text, text_score))
        return out


def label_views(faces, boxes, pano_width, pano_height):
    """Line blocks of the pano text line boxes of one sweep, with their views: list of (block box, detection score,
    line count, view). The view of a block with two or more lines has LABEL_PAD line heights of extra space on the
    left and the right, for a text box that is too narrow."""
    out = []
    for (x, y, w, h), score, n in group_lines(boxes, pano_width):
        pad = LABEL_PAD * h / n if n > 1 else 0.0
        width = LABEL_VIEW_WIDTH * (1 + 2 * pad / max(w, 1.0))
        out.append(((x, y, w, h), score, n, box_view(faces, (x - pad, y, w + 2 * pad, h), pano_width, pano_height, width)))
    return out


def reading_order(polys, gap=1.0):
    """Line polygons in rows from top to bottom, left to right in a row. Polygons in a row that are less than
    gap times the row height apart join into one axis-aligned polygon, so a split line is read as one."""
    rows = []
    for p in sorted(polys, key=lambda p: p[:, 1].mean()):
        y, h = p[:, 1].mean(), np.ptp(p[:, 1])
        if rows and abs(y - rows[-1][0]) <= 0.5 * max(h, rows[-1][1]):
            rows[-1][2].append(p)
        else:
            rows.append((y, h, [p]))
    out = []
    for _, h, row in rows:
        groups = []
        for p in sorted(row, key=lambda p: p[:, 0].min()):
            if groups and p[:, 0].min() - max(q[:, 0].max() for q in groups[-1]) <= gap * h:
                groups[-1].append(p)
            else:
                groups.append([p])
        for g in groups:
            if len(g) == 1:
                out.append(g[0])
            else:
                x0, y0 = np.min([q.min(0) for q in g], 0)
                x1, y1 = np.max([q.max(0) for q in g], 0)
                out.append(np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]]))
    return out


def line_crop(image, poly):
    p = np.asarray(poly, np.float32)
    w = int(round(max(np.linalg.norm(p[0] - p[1]), np.linalg.norm(p[2] - p[3]))))
    h = int(round(max(np.linalg.norm(p[0] - p[3]), np.linalg.norm(p[1] - p[2]))))
    w, h = max(w, 1), max(h, 1)
    m = cv2.getPerspectiveTransform(p, np.float32([[0, 0], [w, 0], [w, h], [0, h]]))
    crop = cv2.warpPerspective(image, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return np.rot90(crop) if h >= 1.5 * w else crop


def box_view(faces, box, pano_width, pano_height, min_width=640, margin=VIEW_MARGIN):
    """Rectified, upscaled, full-resolution perspective crop centered on a pano box."""
    yaw, pitch = view_direction(box, pano_width, pano_height)
    x0, x1, y0, y1 = view_bounds(box, pano_width, pano_height, yaw, pitch)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (max(b - a, 1 / sphere.FACE_FOCAL) / 2 * (1 + margin) for a, b in ((x0, x1), (y0, y1)))
    t = max(abs(cx) + hx, abs(cy) + hy)
    focal = min(max(sphere.FACE_FOCAL, min_width / (2 * hx)), VIEW_MAX_SIZE / (2 * t))
    size = int(np.ceil(2 * t * focal))
    tile = sphere.render_tile(faces, yaw, pitch, 2 * np.arctan(t), size)
    rows = np.rint((np.array([cy - hy, cy + hy, cx - hx, cx + hx]) / t + 1) / 2 * size).astype(int)
    return tile[rows[0]:rows[1], rows[2]:rows[3]]


def view_direction(box, pano_width, pano_height):
    x, y, w, h = box
    d = sphere.equirect_to_dirs(x + w / 2, y + h / 2, pano_width, pano_height)
    return float(np.arctan2(d[1], d[0])), float(np.arcsin(np.clip(d[2], -1.0, 1.0)))


def view_bounds(box, pano_width, pano_height, yaw, pitch, samples=16):
    """Bounds (x0, x1, y0, y1) in tan units, y down, of the box border seen from a view with this yaw and pitch."""
    x, y, w, h = box
    t = np.linspace(0, 1, samples)
    us = np.concatenate([x + w * t, np.full_like(t, x + w), x + w * t, np.full_like(t, x)])
    vs = np.concatenate([np.full_like(t, y), y + h * t, np.full_like(t, y + h), y + h * t])
    d = sphere.equirect_to_dirs(us, vs, pano_width, pano_height)
    f, r, up = sphere.tile_basis(yaw, pitch)
    z = d @ f
    a, b = d @ r / z, -(d @ up) / z
    return float(a.min()), float(a.max()), float(b.min()), float(b.max())


def group_lines(boxes, pano_width, gap=1.0, overlap=0.5):
    """Join stacked text line boxes of one plate: list of (pano box, score) to list of (block box, best score, line count)."""
    parent = list(range(len(boxes)))

    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i

    for i, (a, _) in enumerate(boxes):
        for j in range(i):
            b = boxes[j][0]
            dx = np.mod(b[0] - a[0] + pano_width / 2, pano_width) - pano_width / 2
            ox = min(a[2], dx + b[2]) - max(0.0, dx)
            dy = max(b[1] - a[1] - a[3], a[1] - b[1] - b[3])
            if ox >= overlap * min(a[2], b[2]) and dy <= gap * max(a[3], b[3]):
                parent[root(i)] = root(j)
    blocks = {}
    for i in range(len(boxes)):
        blocks.setdefault(root(i), []).append(i)
    out = []
    for members in blocks.values():
        x0 = boxes[members[0]][0][0]
        lefts = [x0 + np.mod(boxes[k][0][0] - x0 + pano_width / 2, pano_width) - pano_width / 2 for k in members]
        left = min(lefts)
        right = max(lx + boxes[k][0][2] for lx, k in zip(lefts, members))
        top = min(boxes[k][0][1] for k in members)
        bottom = max(boxes[k][0][1] + boxes[k][0][3] for k in members)
        out.append(((float(np.mod(left, pano_width)), float(top), float(right - left), float(bottom - top)),
                    max(boxes[k][1] for k in members), len(members)))
    return out


@cache
def stoplist(path=STOPLIST):
    cfg = json.loads(Path(path).read_text())
    return {
        **cfg,
        "plate_print": {w.upper() for w in cfg["plate_print"]},
        "not_label": {w.upper() for w in cfg["not_label"]},
    }


def tokens(text):
    return re.findall(r"[0-9A-Z\u00C0-\u024F]+", text.upper())


def is_latin(text):
    return all(not c.isalpha() or "LATIN" in unicodedata.name(c, "") for c in text)


def distance(a, b):
    """Levenshtein distance."""
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[-1]


def stopped(token, words, cfg):
    """True when the token is a stop word or a misread of one. A misread is the same after CONFUSABLE (stop words of
    2 or more characters), a join of stop words, a stop word of 3 or more characters with one character missing (AB,
    14), a stop word with letters and digits with one other digit (F23), or for an alphabetic stop word of
    fuzzy_min_length characters or more, edit distance 1 (2 from fuzzy_long_length characters)."""
    if token in words:
        return True
    t = token.translate(CONFUSABLE)
    long_words = {w.translate(CONFUSABLE) for w in words if len(w) > 1}
    if t in long_words or joined(t, long_words):
        return True
    n, long = cfg["fuzzy_min_length"], cfg["fuzzy_long_length"]
    for w in words:
        if len(token) == len(w) - 1 >= 2 and any(w[:i] + w[i + 1:] == token for i in range(len(w))):
            return True
        if w.isalpha():
            limit = 2 if len(w) >= long else 1 if len(w) >= n else 0
            if limit and abs(len(token) - len(w)) <= limit and distance(token, w) <= limit:
                return True
        elif not w.isdigit() and len(token) == len(w):
            diff = [(a, b) for a, b in zip(token, w) if a != b]
            if len(diff) == 1 and diff[0][0].isdigit() and diff[0][1].isdigit():
                return True
    return False


def joined(token, words):
    """True when the token is a join of two or more of the words."""
    ends = {0: 0}
    for i in range(1, len(token) + 1):
        parts = [ends[j] + 1 for j in ends if token[j:i] in words]
        if parts:
            ends[i] = max(parts)
    return ends.get(len(token), 0) >= 2


def clean_lines(text_lines, words):
    """Usable lines: list of (kept tokens, score, stopped token count)."""
    cfg = stoplist()
    out = []
    for text, score in text_lines:
        if score < cfg["min_score"] or not is_latin(text):
            continue
        all_tokens = tokens(text)
        kept = [t for t in all_tokens if not stopped(t, words, cfg)]
        if sum(map(len, kept)) >= cfg["min_chars"] or (all_tokens and not kept):
            out.append((kept, score, len(all_tokens) - len(kept)))
    return out


def device_name(text_lines):
    """-> str, the name with the fixed plate print removed ("" when nothing is left)"""
    cfg = stoplist()
    lines = [(t, s) for t, s in text_lines if s >= cfg["name_min_score"]]
    return " ".join(t for kept, _, _ in clean_lines(lines, cfg["plate_print"]) for t in kept)


def label_text(text_lines):
    """Cabinet label text and score of the lines read from one label view.

    A view with a line of only stop words, or with as many stop words as other words, is a badge, a sticker or
    device print, not a label: ("", 0.0)."""
    lines = clean_lines(text_lines, stoplist()["not_label"])
    kept = [t for k, _, _ in lines for t in k]
    if not kept or any(not k for k, _, _ in lines) or sum(n for _, _, n in lines) >= len(kept):
        return "", 0.0
    return " ".join(kept), float(np.mean([s for _, s, _ in lines]))


def is_cabinet_label(text, score):
    cfg = stoplist()
    lines = clean_lines([(text, score)], cfg["not_label"])
    return bool(lines) and lines[0][2] < len(lines[0][0]) and len(tokens(text)) <= cfg["max_words"]

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
PLATE_MM = (262.2, 177.0)
TEX_WIDTH = 2048

F_ROWS = [279, 389, 499, 609, 719, 829, 939]
F_LED_ROWS = [294, 404, 514, 624, 734, 844, 954]
ALARM_LED_ROWS = [268, 312, 358, 402, 446, 492, 538, 582, 628, 672, 718]

NARROW_LEFT = 95
NARROW_RIGHT_FROM = 760
NARROW_PASTES = [((120, 100, 215, 170), (125, 100)), ((110, 270, 215, 700), (120, 270))]

GLYPH_CHARS = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-./=:+%<>()#_,"
GLYPH_FONTS = {"sans": cv2.FONT_HERSHEY_SIMPLEX, "bold": cv2.FONT_HERSHEY_DUPLEX, "hand": cv2.FONT_HERSHEY_SCRIPT_SIMPLEX}
GLYPH_CELL = (48, 64)


def edge_line(mask, axis, positions, first):
    pts = []
    for p in positions:
        line = mask[p] if axis == 0 else mask[:, p]
        idx = np.flatnonzero(line)
        q = idx[0] if first else idx[-1] + 1
        pts.append((q, p) if axis == 0 else (p, q))
    pts = np.float64(pts)
    if axis == 0:
        a, b = np.polyfit(pts[:, 1], pts[:, 0], 1)
        return lambda y: (a * y + b, y)
    a, b = np.polyfit(pts[:, 0], pts[:, 1], 1)
    return lambda x: (x, a * x + b)


def find_corners(img):
    """Outer frame corners (tl, tr, br, bl) from robust edge fits against the white background."""
    mask = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) < 250
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    rows = np.linspace(y0 + 0.2 * (y1 - y0), y1 - 0.1 * (y1 - y0), 15).astype(int)
    cols = np.linspace(x0 + 0.1 * (x1 - x0), x1 - 0.1 * (x1 - x0), 15).astype(int)
    cols = [c for c in cols if abs(c - (x0 + x1) / 2) > 0.05 * (x1 - x0)]
    left, right = edge_line(mask, 0, rows, True), edge_line(mask, 0, rows, False)
    top, bottom = edge_line(mask, 1, cols, True), edge_line(mask, 1, cols, False)

    def meet(vert, horiz):
        y = horiz(vert(0)[0])[1]
        for _ in range(5):
            x = vert(y)[0]
            y = horiz(x)[1]
        return x, y

    return np.float32([meet(left, top), meet(right, top), meet(right, bottom), meet(left, bottom)])


def rectify(img):
    corners = find_corners(img)
    w, h = TEX_WIDTH, round(TEX_WIDTH * PLATE_MM[1] / PLATE_MM[0])
    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    return cv2.warpPerspective(img, cv2.getPerspectiveTransform(corners, dst), (w, h), flags=cv2.INTER_AREA), corners


def components(mask, min_area):
    n, _, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=4)
    return [tuple(int(v) for v in s[:4]) for s in st[1:] if s[4] >= min_area]


def measure(tex):
    """Regions in texture px as (x0, y0, x1, y1). Positions come from the rectified reference and are checked by detection."""
    gray = cv2.cvtColor(tex, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(tex, cv2.COLOR_BGR2HSV)
    blue = (hsv[..., 0] > 95) & (hsv[..., 0] < 130) & (hsv[..., 1] > 40)
    lx, ly, lw, lh = max(components(blue, 10000), key=lambda s: s[2] * s[3])
    labels = sorted(
        [(x, y, x + w, y + h) for x, y, w, h in components(gray >= 250, 8000) if 60 <= h <= 120 and 150 <= w <= 200 or 35 <= h <= 50 and w > 250],
        key=lambda b: (b[0] // 100, b[1]),
    )
    if len(labels) != 27:
        raise SystemExit(f"expected 27 label strips, found {len(labels)}")
    leds = [{"name": "ready", "x": 982, "y": 192, "r": 12, "color": "green"},
            {"name": "start", "x": 1186, "y": 192, "r": 13, "color": "yellow"},
            {"name": "trip", "x": 1388, "y": 194, "r": 13, "color": "red"}]
    for col, x in ((0, 186), (1, 520)):
        for i, y in enumerate(F_LED_ROWS):
            leds.append({"name": f"f{col * 8 + i + 1}", "x": x, "y": y, "r": 11, "color": "any"})
        leds.append({"name": f"f{col * 8 + 8}", "x": 160 + col * 334, "y": 1114, "r": 12, "color": "any"})
    for i, y in enumerate(ALARM_LED_ROWS):
        leds.append({"name": f"alarm{i + 1}", "x": 1586, "y": y, "r": 12, "color": "any"})
    leds += [{"name": "remote", "x": 1684, "y": 1142, "r": 12, "color": "white"},
             {"name": "local", "x": 1684, "y": 1212, "r": 12, "color": "yellow"}]
    keys = []
    for col, x in ((0, 118), (1, 452)):
        for i, y in enumerate(F_ROWS + [1149]):
            keys.append({"name": f"f{col * 8 + i + 1}", "box": [x, y, x + 84, y + 85]})
    for name, (x, y, w, h) in {"close-open": (765, 827, 142, 421), "esc": (949, 839, 115, 117), "up": (1173, 839, 115, 117),
                               "enter": (1397, 839, 115, 117), "left": (1032, 978, 115, 118), "right": (1315, 979, 115, 117),
                               "down": (1174, 1118, 115, 118), "key": (1397, 1119, 115, 117), "clear": (1592, 840, 116, 114),
                               "menu": (1592, 979, 116, 115), "rl": (1593, 1119, 115, 117), "help": (1770, 1118, 116, 118)}.items():
        keys.append({"name": name, "box": [x, y, x + w, y + h]})
    for led in leds:
        patch = gray[led["y"] - 3:led["y"] + 4, led["x"] - 3:led["x"] + 4]
        if patch.mean() < 100:
            raise SystemExit(f"LED {led['name']} does not sit on a lamp")
    return {"lcd": [lx, ly, lx + lw, ly + lh], "labels": labels, "leds": leds, "keys": keys, "port": [1723, 870, 1966, 1055]}


def to_uv(regions, w, h):
    def box(b):
        return [round(b[0] / w, 5), round(b[1] / h, 5), round(b[2] / w, 5), round(b[3] / h, 5)]

    return {
        "lcd": box(regions["lcd"]),
        "labels": [box(b) for b in regions["labels"]],
        "leds": [{**led, "x": round(led["x"] / w, 5), "y": round(led["y"] / h, 5), "r": round(led["r"] / w, 5)} for led in regions["leds"]],
        "keys": [{"name": k["name"], "box": box(k["box"])} for k in regions["keys"]],
        "port": box(regions["port"]),
    }


def narrow(tex, regions):
    """615 plate with F1 to F4 only: left frame strip + right part of the wide plate, F1 to F4 keys and the 615 print pasted in."""
    out = np.concatenate([tex[:, :NARROW_LEFT], tex[:, NARROW_RIGHT_FROM:]], 1).copy()
    for (x0, y0, x1, y1), (dx, dy) in NARROW_PASTES:
        out[dy:dy + y1 - y0, dx:dx + x1 - x0] = tex[y0:y1, x0:x1]
    shift = NARROW_RIGHT_FROM - NARROW_LEFT
    key_dx = NARROW_PASTES[1][1][0] - NARROW_PASTES[1][0][0]

    def moved(b):
        return [b[0] - shift, b[1], b[2] - shift, b[3]]

    leds, keys = [], []
    for led in regions["leds"]:
        if led["name"] in ("f1", "f2", "f3", "f4"):
            leds.append({**led, "x": led["x"] + key_dx})
        elif led["x"] >= NARROW_RIGHT_FROM:
            leds.append({**led, "x": led["x"] - shift})
    for k in regions["keys"]:
        if k["name"] in ("f1", "f2", "f3", "f4"):
            b = k["box"]
            keys.append({"name": k["name"], "box": [b[0] + key_dx, b[1], b[2] + key_dx, b[3]]})
        elif k["box"][0] >= NARROW_RIGHT_FROM:
            keys.append({"name": k["name"], "box": moved(k["box"])})
    out_regions = {
        "lcd": moved(regions["lcd"]),
        "labels": [moved(b) for b in regions["labels"] if b[0] >= NARROW_RIGHT_FROM],
        "leds": leds,
        "keys": keys,
        "port": moved(regions["port"]),
    }
    return out, out_regions


def glyph_atlas():
    cw, ch = GLYPH_CELL
    atlas = np.zeros((ch * len(GLYPH_FONTS), cw * len(GLYPH_CHARS)), np.uint8)
    advance = {}
    for row, (name, font) in enumerate(GLYPH_FONTS.items()):
        advance[name] = []
        for i, c in enumerate(GLYPH_CHARS):
            (w, _), _ = cv2.getTextSize(c, font, 1.4, 3)
            x = max(0, (cw - w) // 2)
            cv2.putText(atlas[row * ch:(row + 1) * ch, i * cw:(i + 1) * cw], c, (x, 46), font, 1.4, 255, 3, cv2.LINE_AA)
            advance[name].append(int(min(cw, w + 6)) if c != " " else 22)
    return atlas, {"chars": GLYPH_CHARS, "fonts": list(GLYPH_FONTS), "cell": [cw, ch], "baseline": 46, "cap_height": 32, "advance": advance}


def write_regions(path, regions, w, h, plate_mm, source):
    data = {
        "source": source,
        "size_px": [w, h],
        "plate_mm": [round(v, 1) for v in plate_mm],
        "uv": "normalized texture coordinates, x right and y down from the top left corner of the plate front face",
        **to_uv(regions, w, h),
    }
    path.write_text(json.dumps(data, indent=1) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reference", default=str(ROOT.parent / "9PAA00000215623_master.jpg"))
    p.add_argument("--out", default=str(ROOT / "assets"))
    p.add_argument("--debug", help="write overlays of the regions to this folder")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(a.reference)
    tex, corners = rectify(img)
    h, w = tex.shape[:2]
    regions = measure(tex)
    cv2.imwrite(str(out / "rex615-front.png"), tex)
    source = Path(a.reference).name
    write_regions(out / "rex615-regions.json", regions, w, h, PLATE_MM, source)
    ntex, nregions = narrow(tex, regions)
    nh, nw = ntex.shape[:2]
    cv2.imwrite(str(out / "narrow615-front.png"), ntex)
    write_regions(out / "narrow615-regions.json", nregions, nw, nh, (PLATE_MM[0] * nw / w, PLATE_MM[1]), source)
    atlas, meta = glyph_atlas()
    cv2.imwrite(str(out / "glyphs.png"), atlas)
    (out / "glyphs.json").write_text(json.dumps(meta) + "\n")
    print("corners", np.round(corners, 1).tolist(), "texture", (w, h), "narrow", (nw, nh))
    if a.debug:
        dbg = Path(a.debug)
        dbg.mkdir(parents=True, exist_ok=True)
        for name, t, r in (("rex615", tex, regions), ("narrow615", ntex, nregions)):
            o = t.copy()
            cv2.rectangle(o, tuple(r["lcd"][:2]), tuple(r["lcd"][2:]), (255, 0, 255), 3)
            for b in r["labels"]:
                cv2.rectangle(o, tuple(b[:2]), tuple(b[2:]), (0, 160, 0), 2)
            for k in r["keys"]:
                cv2.rectangle(o, tuple(k["box"][:2]), tuple(k["box"][2:]), (255, 0, 0), 2)
            for led in r["leds"]:
                cv2.circle(o, (led["x"], led["y"]), led["r"], (0, 0, 255), 2)
            cv2.rectangle(o, tuple(r["port"][:2]), tuple(r["port"][2:]), (0, 128, 255), 2)
            cv2.imwrite(str(dbg / f"{name}-regions.jpg"), o)
        cv2.imwrite(str(dbg / "glyphs.png"), atlas)


if __name__ == "__main__":
    main()

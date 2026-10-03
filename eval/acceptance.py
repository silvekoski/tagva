import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval import realtest  # noqa: E402

MAX_FALSE_POSITIVES = 1


def check(tagfile, devices, radius=realtest.ANCHOR_RADIUS):
    """Device-level check. Returns (passed, rows, missed, false positives). One row per target and per false positive."""
    found = [d for tag in tagfile["tags"] for d in tag["devices"]]
    anchors = [None if d["anchor"] is None else [d["anchor"][k] for k in "xyz"] for d in found]
    matches = realtest.match_anchors(anchors, devices, radius)
    by_device = {dev: (found[i], dist) for i, (dev, dist) in enumerate(matches) if dev is not None}
    rows = []
    for g in devices:
        if g["target"]:
            hit = by_device.get(g["id"])
            rows.append({"gt": g["id"], "device_id": hit[0]["device_id"] if hit else None,
                         "distance": hit[1] if hit else None, "result": "found" if hit else "missed"})
    fps = 0
    target = {g["id"]: g["target"] for g in devices}
    for d, (dev, dist) in zip(found, matches):
        if dev is not None and target[dev]:
            continue
        fps += 1
        reason = "no_anchor" if d["anchor"] is None else ("hard_negative" if dev else "no_match")
        rows.append({"gt": dev, "device_id": d["device_id"], "distance": dist, "result": f"false_positive ({reason})"})
    missed = sum(r["result"] == "missed" for r in rows)
    return missed == 0 and fps <= MAX_FALSE_POSITIVES, rows, missed, fps


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tagfile")
    p.add_argument("--devices", default=str(realtest.DEVICES))
    p.add_argument("--radius", type=float, default=realtest.ANCHOR_RADIUS)
    a = p.parse_args()
    devices = realtest.load_devices(a.devices)
    passed, rows, missed, fps = check(json.loads(Path(a.tagfile).read_text()), devices, a.radius)
    print(f"{'gt':<5} {'device_id':<12} {'dist m':>7}  result")
    for r in rows:
        dist = "-" if r["distance"] is None else f"{r['distance']:.3f}"
        print(f"{r['gt'] or '-':<5} {r['device_id'] or '-':<12} {dist:>7}  {r['result']}")
    targets = sum(g["target"] for g in devices)
    print(f"targets found {targets - missed} / {targets}, false positives {fps} (max {MAX_FALSE_POSITIVES}): "
          f"{'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

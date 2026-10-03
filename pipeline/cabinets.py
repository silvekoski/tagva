import numpy as np

from pipeline import review
from pipeline.merge import Group, text_key
from pipeline.ocr import CONFUSABLE, distance

AMBIGUOUS_RATIO = 1.2
TEXT_EDIT_CHARS = 8


def agrees(a, b):
    """Two texts agree with spaces and case removed and the OCR confusions (O and 0, I and 1, ...) mapped, with one edit
    per TEXT_EDIT_CHARS characters (none below that length)."""
    a, b = (text_key(t).upper().translate(CONFUSABLE) for t in (a, b))
    return distance(a, b) <= max(len(a), len(b)) // TEXT_EDIT_CHARS


def confirmed(group, sweeps, load_grid):
    """True when two or more sweeps read the voted text of a label group. One sweep is enough only when it is within
    review.NEIGHBOR_RADIUS and no other sweep in that radius sees the label anchor. sweeps: list of (id, position, rotation)."""
    text = group.text
    if not text or group.anchor is None:
        return False
    support = Group([o for o in group.observations if agrees(o.text, text)], group.anchor)
    if len(support.sweeps) >= 2:
        return True
    near = all(np.linalg.norm(group.anchor - o.origin) <= review.NEIGHBOR_RADIUS for o in support.observations)
    return near and not review.few_observations(support, sweeps, load_grid)


def assign(device_anchors, label_anchors, radius):
    """Nearest label for each device anchor: 3D within radius, else horizontal distance within radius.

    Returns a list of (label index or None, ambiguous) per device."""
    labels = np.array([a for a in label_anchors if a is not None], float).reshape(-1, 3)
    index = [i for i, a in enumerate(label_anchors) if a is not None]
    out = []
    for anchor in device_anchors:
        result = (None, False)
        if anchor is not None and len(index):
            delta = labels - np.asarray(anchor, float)
            for dist in (np.linalg.norm(delta, axis=1), np.linalg.norm(delta[:, :2], axis=1)):
                order = np.argsort(dist, kind="stable")
                if dist[order[0]] <= radius:
                    ambiguous = len(order) > 1 and dist[order[1]] <= AMBIGUOUS_RATIO * dist[order[0]]
                    result = (index[order[0]], bool(ambiguous))
                    break
        out.append(result)
    return out

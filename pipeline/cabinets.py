import numpy as np

AMBIGUOUS_RATIO = 1.2


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

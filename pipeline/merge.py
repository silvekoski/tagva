from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Observation:
    sweep: str
    origin: np.ndarray
    ray: np.ndarray
    box: tuple
    score: float
    text: str = ""
    text_score: float = 0.0
    anchor: np.ndarray | None = None


@dataclass
class Group:
    observations: list = field(default_factory=list)
    anchor: np.ndarray | None = None

    @property
    def score(self):
        return max(o.score for o in self.observations)

    @property
    def sweeps(self):
        return {o.sweep for o in self.observations}

    @property
    def text(self):
        return vote_text(self.observations)


def normalize_text(text):
    return " ".join(text.split())


def text_key(text):
    return "".join(text.split()).casefold()


def vote_text(observations):
    """The text that the most sweeps read, compared with spaces and case removed, then the largest text score sum.
    Of its variants, the one with the most words wins, because the recognizer drops spaces more often than it adds them."""
    sweeps, weights, variants = defaultdict(set), defaultdict(float), defaultdict(lambda: defaultdict(float))
    for o in observations:
        text = normalize_text(o.text)
        key = text_key(text)
        if key:
            sweeps[key].add(o.sweep)
            weights[key] += o.text_score
            variants[key][text] += o.text_score
    if not weights:
        return ""
    key = min(weights, key=lambda k: (-len(sweeps[k]), -weights[k], k))
    return min(variants[key], key=lambda t: (-len(t.split()), -variants[key][t], t))


def _find(parent, i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def ray_distance(origin, ray, point):
    """Perpendicular distance from point to the ray, or inf when the point is behind the origin."""
    d = point - origin
    t = d @ ray
    return float(np.linalg.norm(d - t * ray)) if t > 0 else np.inf


def merge(observations, radius):
    """Single-linkage clusters of anchored observations within radius. Unanchored observations
    join the group whose anchor is nearest to their ray, or become their own group."""
    anchored = [o for o in observations if o.anchor is not None]
    parent = list(range(len(anchored)))
    if anchored:
        pts = np.array([o.anchor for o in anchored])
        for i in range(len(anchored)):
            for j in np.flatnonzero(np.linalg.norm(pts[i + 1:] - pts[i], axis=1) <= radius) + i + 1:
                parent[_find(parent, j)] = _find(parent, i)
    members = defaultdict(list)
    for i, o in enumerate(anchored):
        members[_find(parent, i)].append(o)
    groups = [Group(obs, np.median([o.anchor for o in obs], axis=0)) for obs in members.values()]
    anchored_groups = list(groups)
    for o in observations:
        if o.anchor is not None:
            continue
        dist = [ray_distance(o.origin, o.ray, g.anchor) for g in anchored_groups]
        k = int(np.argmin(dist)) if dist else -1
        if k >= 0 and dist[k] <= radius:
            anchored_groups[k].observations.append(o)
        else:
            groups.append(Group([o], None))
    return groups


def one_per_sweep(groups):
    """Keep the best observation of each sweep in each group (PRD: at most one box per device per panorama)."""
    out = []
    for g in groups:
        best = {}
        for o in g.observations:
            if o.sweep not in best or o.score > best[o.sweep].score:
                best[o.sweep] = o
        obs = list(best.values())
        anchors = [o.anchor for o in obs if o.anchor is not None]
        out.append(Group(obs, np.median(anchors, axis=0) if anchors else g.anchor))
    return out

import numpy as np

from pipeline.merge import normalize_text
from pipeline.scan import local_dirs_to_grid

REASONS = (
    "low_confidence",
    "empty_ocr",
    "no_anchor",
    "few_observations",
    "anchor_variance",
    "ocr_conflict",
    "ambiguous_cabinet",
)
NEIGHBOR_RADIUS = 4.0
SIGHT_TOLERANCE = 0.1


def line_of_sight(range_grid, rotation, position, point):
    d = np.asarray(point, float) - position
    dist = np.linalg.norm(d)
    row, col = local_dirs_to_grid((d / dist) @ rotation)
    return float(range_grid[row, col]) >= dist - SIGHT_TOLERANCE


def few_observations(group, sweeps, load_grid):
    """sweeps: list of (id, position, rotation). load_grid(id) returns the range grid of the sweep."""
    seen = group.sweeps
    if group.anchor is None or len(seen) != 1:
        return False
    for sid, position, rotation in sweeps:
        if sid in seen or np.linalg.norm(group.anchor - position) > NEIGHBOR_RADIUS:
            continue
        if line_of_sight(load_grid(sid), rotation, position, group.anchor):
            return True
    return False


def reasons(group, name, threshold, merge_radius, ambiguous, few):
    names = {normalize_text(o.text).casefold() for o in group.observations} - {""}
    flags = {
        "low_confidence": round(group.score, 3) < threshold,
        "empty_ocr": not name,
        "no_anchor": group.anchor is None,
        "few_observations": few,
        "anchor_variance": group.anchor is not None and any(
            np.linalg.norm(o.anchor - group.anchor) > merge_radius for o in group.observations if o.anchor is not None
        ),
        "ocr_conflict": len(names) > 1,
        "ambiguous_cabinet": ambiguous,
    }
    return [r for r in REASONS if flags[r]]

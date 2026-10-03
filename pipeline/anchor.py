import numpy as np

from pipeline.scan import local_dirs_to_grid
from pipeline.sphere import equirect_to_dirs

CENTER_FRACTION = 0.4
SAMPLES = 15
MIN_VALID_FRACTION = 0.2


def box_anchor(range_grid, rotation, position, box, pano_width, pano_height):
    """Median range inside the box center, along the ray through the box center.

    Returns (anchor xyz or None, valid sample fraction)."""
    x, y, w, h = box
    offsets = (np.linspace(0, 1, SAMPLES) - 0.5) * CENTER_FRACTION
    u, v = np.meshgrid(x + w * (0.5 + offsets), y + h * (0.5 + offsets))
    dirs = equirect_to_dirs(u, v, pano_width, pano_height).reshape(-1, 3)
    row, col = local_dirs_to_grid(dirs @ rotation)
    r = range_grid[row, col].astype(np.float64)
    valid = r[r > 0]
    fraction = valid.size / r.size
    if fraction < MIN_VALID_FRACTION:
        return None, fraction
    center = equirect_to_dirs(x + w / 2, y + h / 2, pano_width, pano_height)
    return position + np.median(valid) * center, fraction

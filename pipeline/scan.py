from dataclasses import dataclass, field

import cv2
import numpy as np
import pye57

GRID_ROWS = 1800
GRID_COLS = 3600
GRID_STEP = np.radians(0.1)
GRID_ROW_HORIZON = 900


def quat_to_matrix(w, x, y, z):
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def node_pose(node):
    rot, tr = node["pose"]["rotation"], node["pose"]["translation"]
    return quat_to_matrix(*[rot[k].value() for k in "wxyz"]), np.array([tr[k].value() for k in "xyz"])


@dataclass
class Sweep:
    index: int
    name: str
    guid: str
    rotation: np.ndarray
    position: np.ndarray
    images: list = field(default_factory=list)


def local_dirs_to_grid(local):
    el = np.arcsin(np.clip(local[..., 2], -1.0, 1.0))
    az = np.mod(np.arctan2(local[..., 1], local[..., 0]), 2 * np.pi)
    row = np.rint(el / GRID_STEP + GRID_ROW_HORIZON).astype(int)
    col = np.floor(az / GRID_STEP).astype(int) % GRID_COLS
    return np.clip(row, 0, GRID_ROWS - 1), col


class Scan:
    def __init__(self, path):
        self.e57 = pye57.E57(str(path))
        root = self.e57.image_file.root()
        data3d, images2d = root["data3D"], root["images2D"]
        self.sweeps = []
        by_guid = {}
        for i in range(data3d.childCount()):
            node = data3d[i]
            R, t = node_pose(node)
            sweep = Sweep(i, node["name"].value().strip(), node["guid"].value(), R, t)
            self.sweeps.append(sweep)
            by_guid[sweep.guid] = sweep
        for i in range(images2d.childCount()):
            node = images2d[i]
            R, _ = node_pose(node)
            by_guid[node["associatedData3DGuid"].value()].images.append((R, node["pinholeRepresentation"]["jpegImage"]))

    def faces(self, index):
        out = []
        for R, blob in self.sweeps[index].images:
            buf = np.zeros(blob.byteCount(), np.uint8)
            blob.read(buf, 0, blob.byteCount())
            out.append((cv2.imdecode(buf, cv2.IMREAD_COLOR), R))
        return out

    def raw(self, index):
        return self.e57.read_scan_raw(index)

    def range_grid(self, index, raw=None):
        raw = self.raw(index) if raw is None else raw
        ok = raw["cartesianInvalidState"] == 0
        xyz = np.stack([raw["cartesianX"], raw["cartesianY"], raw["cartesianZ"]], 1)[ok]
        grid = np.zeros((GRID_ROWS, GRID_COLS), np.float32)
        grid[raw["rowIndex"][ok], raw["columnIndex"][ok]] = np.linalg.norm(xyz, axis=1)
        return grid

    def world_points(self, index, raw=None):
        raw = self.raw(index) if raw is None else raw
        ok = raw["cartesianInvalidState"] == 0
        xyz = np.stack([raw["cartesianX"], raw["cartesianY"], raw["cartesianZ"]], 1)[ok]
        rgb = np.stack([raw["colorRed"], raw["colorGreen"], raw["colorBlue"]], 1)[ok]
        s = self.sweeps[index]
        return xyz @ s.rotation.T + s.position, rgb

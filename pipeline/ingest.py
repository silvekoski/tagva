import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from pipeline import sphere
from pipeline.scan import Scan

PANO_WIDTH = 8192
PANO_HEIGHT = 4096


def sweep_id(index):
    return f"sweep-{index:02d}"


def ingest(e57_path, out_dir):
    out = Path(out_dir)
    (out / "panos").mkdir(parents=True, exist_ok=True)
    (out / "depth").mkdir(parents=True, exist_ok=True)
    scan = Scan(e57_path)
    sweeps = []
    for sweep in scan.sweeps:
        sid = sweep_id(sweep.index)
        pano = sphere.render_equirect(scan.faces(sweep.index), PANO_WIDTH, PANO_HEIGHT)
        cv2.imwrite(str(out / "panos" / f"{sid}.jpg"), pano, [cv2.IMWRITE_JPEG_QUALITY, 88])
        grid = scan.range_grid(sweep.index)
        np.savez_compressed(out / "depth" / f"{sid}.npz", range=grid.astype(np.float16))
        sweeps.append({
            "id": sid,
            "index": sweep.index,
            "name": sweep.name,
            "position": sweep.position.round(5).tolist(),
            "rotation": sweep.rotation.round(6).tolist(),
            "pano": f"panos/{sid}.jpg",
        })
        print(sid, flush=True)
    manifest = {
        "source": Path(e57_path).name,
        "pano_width": PANO_WIDTH,
        "pano_height": PANO_HEIGHT,
        "sweeps": sweeps,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("e57")
    p.add_argument("out", nargs="?", default="data/scan")
    a = p.parse_args()
    ingest(a.e57, a.out)

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from pipeline import sphere
from pipeline.scan import Scan

PANO_WIDTH = 8192
PANO_HEIGHT = 4096
CLOUD_MAX_POINTS = 2_000_000
CLOUD_VOXEL = 0.02
CLOUD_VOXEL_GROWTH = 1.05
CLOUD_CROP = 15.0
CLOUD_EXCLUDE = (0,)


def sweep_id(index):
    return f"sweep-{index:02d}"


def export_cloud(scan, out, exclude=CLOUD_EXCLUDE):
    """Voxel-downsampled merged cloud of the sweeps not in exclude, cropped to CLOUD_CROP around the
    mean sweep position. Writes cloud-xyz.bin (float32 LE, N x 3) and cloud-rgb.bin (uint8, N x 3)."""
    import open3d as o3d

    sweeps = [s for s in scan.sweeps if s.index not in set(exclude)]
    center = np.mean([s.position for s in sweeps], axis=0)
    merged = o3d.geometry.PointCloud()
    for sweep in sweeps:
        xyz, rgb = scan.world_points(sweep.index)
        keep = np.linalg.norm(xyz - center, axis=1) <= CLOUD_CROP
        pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(xyz[keep]))
        pc.colors = o3d.utility.Vector3dVector(rgb[keep] / 255.0)
        merged = (merged + pc.voxel_down_sample(CLOUD_VOXEL)).voxel_down_sample(CLOUD_VOXEL)
        print("cloud", sweep_id(sweep.index), len(merged.points), flush=True)
    voxel, down = CLOUD_VOXEL, merged
    while len(down.points) > CLOUD_MAX_POINTS:
        voxel *= CLOUD_VOXEL_GROWTH
        down = merged.voxel_down_sample(voxel)
    xyz = np.asarray(down.points).astype("<f4")
    rgb = np.clip(np.rint(np.asarray(down.colors) * 255), 0, 255).astype(np.uint8)
    xyz.tofile(Path(out) / "cloud-xyz.bin")
    rgb.tofile(Path(out) / "cloud-rgb.bin")
    print(f"cloud {len(xyz)} points, voxel {voxel:.4f} m", flush=True)
    return {"points": len(xyz), "xyz": "cloud-xyz.bin", "rgb": "cloud-rgb.bin"}


def ingest(e57_path, out_dir, cloud_exclude=CLOUD_EXCLUDE):
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
        "cloud": export_cloud(scan, out, cloud_exclude),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def ingest_cloud(e57_path, out_dir, cloud_exclude=CLOUD_EXCLUDE):
    path = Path(out_dir) / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["cloud"] = export_cloud(Scan(e57_path), out_dir, cloud_exclude)
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("e57")
    p.add_argument("out", nargs="?", default="data/scan")
    p.add_argument("--cloud-only", action="store_true", help="update only the dollhouse cloud and the manifest")
    p.add_argument("--cloud-exclude", type=int, nargs="*", default=list(CLOUD_EXCLUDE), help="sweep indices left out of the cloud")
    a = p.parse_args()
    (ingest_cloud if a.cloud_only else ingest)(a.e57, a.out, a.cloud_exclude)

# Contracts

Each component must follow this file. Change it only with the lead.

## Repo layout

| Path | Owner | Content |
| --- | --- | --- |
| `pipeline/scan.py`, `sphere.py`, `tiles.py`, `anchor.py`, `ingest.py` | lead | E57 access, sphere math, tiles, anchors, ingest. Done and tested. |
| `pipeline/detect.py`, `merge.py`, `cabinets.py`, `review.py`, `documents.py`, `tagfile.py`, `run.py`, `api.py` | pipeline | Pipeline steps, run orchestration, FastAPI service. |
| `pipeline/ocr.py`, `pipeline/ocr-stoplist.json` | ocr | PP-OCRv5 wrapper, rectified crops, label and name filters. |
| `viewer/` | viewer | Vite, TypeScript, Three.js player. |
| `synth/` | synth | Blender (bpy) synthetic data generator and texture prep. |
| `train/` | train | Ultralytics training, Verda orchestration. |
| `eval/` | real-test | Real held-out test set builder, ground truth, evaluation. |
| `docs/` | train | Document folder for the player. |
| `tests/` | each owner | pytest tests. Name each file `test_<module>.py` (pytest needs this). |
| `data/` (git ignored) | generated | `data/scan/` (ingest output), `data/tags/` (tag files), `data/real-test/`, `data/synth/`. |
| `models/` (`*.pt` git ignored) | train | Detector weights. The default path is `models/rex615.pt`. The env var `REX_WEIGHTS` overrides it. |

Python: `.venv/bin/python` (3.12, all packages installed: numpy, pye57, opencv-python-headless, pillow, fastapi, uvicorn, pytest, torch, torchvision, ultralytics 8.4, open3d, paddlepaddle 3.3, paddleocr 3.7). Blender: `.venv-bpy/bin/python` (3.11, `bpy` 5.0.1). Do not install other Python packages without the lead.

## Coordinates

- World frame: the E57 file frame, meters, z up. Sweep ids: `sweep-00` to `sweep-17`.
- Panorama: equirect, `pano_width` x `pano_height` = 8192 x 4096 (from `data/scan/manifest.json`), world aligned (no sweep rotation).
  - `lon = atan2(dy, dx)`, `lat = asin(dz)` for a world unit direction d from the sweep position.
  - `u = (pi - lon) / (2 pi) * W`, `v = (pi / 2 - lat) / pi * H`. Pixel i covers `[i, i + 1)`.
  - Python: `pipeline/sphere.py` (`dirs_to_equirect`, `equirect_to_dirs`). The viewer must use the same formula.
- A pano box is `(x, y, width, height)` in equirect pixels with `0 <= x < W`. `x + width` can exceed W at the seam.
- Three.js mapping in the viewer: scan `(x, y, z)` to three `(x, z, -y)`.

## Data in `data/scan/` (from `python -m pipeline.ingest cloud_0.e57`)

- `manifest.json`: `{source, pano_width, pano_height, sweeps: [{id, index, name, position [x,y,z], rotation [[3x3]], pano: "panos/sweep-NN.jpg"}], cloud?}`.
- `panos/sweep-NN.jpg`: equirect panorama.
- `depth/sweep-NN.npz`: key `range`, float16 grid 1800 x 3600 in the sweep local frame, 0 = invalid. Use `pipeline/anchor.py:box_anchor`.
- `cloud-xyz.bin` (float32 little endian, N x 3, world frame) and `cloud-rgb.bin` (uint8, N x 3), with `manifest.cloud = {points: N, xyz: "cloud-xyz.bin", rgb: "cloud-rgb.bin"}`. The pipeline owner adds this to the ingest (Open3D voxel downsample of sweeps 1 to 17, at most 2 000 000 points).

## Tag file

Path: `data/tags/<project-slug>.json`. Slug: keep `[A-Za-z0-9._-]`, change each other character to `-`.

```json
{
  "project": "VEO-DEMO",
  "site": "VEO-DEMO",
  "review_threshold": 0.5,
  "merge_radius": 0.2,
  "cabinet_radius": 2.0,
  "scan": "cloud_0.e57",
  "generated_at": "2026-10-03T21:00:00Z",
  "tags": [
    {
      "id": "tag-001",
      "cabinet": "H03 METERING",
      "anchor": {"x": -5.70, "y": -3.80, "z": 1.30},
      "path": ["VEO-DEMO", "H03 METERING"],
      "devices": [
        {
          "device_id": "dev-001",
          "name": "",
          "device_type": "REX615",
          "boxes": [{"scan_position": "sweep-12", "x": 1200.5, "y": 1500.0, "width": 300.0, "height": 210.0, "confidence": 0.93, "ocr_text": ""}],
          "anchor": {"x": -5.71, "y": -3.78, "z": 1.87},
          "confidence": 0.931,
          "documents": [{"title": "REX615 manual", "kind": "manual", "url": "/documents/devices/REX615/rex615-manual.pdf"}],
          "review": true,
          "review_reasons": ["empty_ocr"]
        }
      ]
    }
  ]
}
```

- The PRD fields are required. `scan`, `generated_at` (RFC 3339, UTC), and the box fields `confidence` and `ocr_text` are extras.
- `confidence`: device confidence, rounded to 3 decimals.
- The "unassigned" tag has `id: "tag-unassigned"`, `cabinet: "unassigned"`, and `anchor` = mean of its device anchors, or null.
- Document `kind`: `manual`, `drawing`, `maintenance_report`, `inspection_report`.
- `review` is true when `review_reasons` is not empty. The pipeline computes `low_confidence` with the file `review_threshold`. The viewer recomputes it live from its slider.
- Reason order: `low_confidence`, `empty_ocr`, `no_anchor`, `few_observations`, `anchor_variance`, `ocr_conflict`, `ambiguous_cabinet`.

## Documents

- `docs/devices/<device_type>/`: each file is a `manual`.
- `docs/projects/<project-slug>/drawings/`, `maintenance-reports/`, `inspection-reports/`: kind from the folder.
- URL: `/documents/<path below docs/>`.

## API (FastAPI, 127.0.0.1:8000)

FastAPI's own `/docs` page must be off (`docs_url=None`, `redoc_url=None`), because `/documents` serves the document folder.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/scan` | `manifest.json`. Pano paths become URLs: `/scan/panos/sweep-NN.jpg`. |
| GET | `/scan/{path}` | Static files from `data/scan/`. |
| GET | `/documents/{path}` | Static files from `docs/`. |
| POST | `/api/runs` | Body `{project, site?, review_threshold?, merge_radius?, cabinet_radius?}`. Starts the pipeline in a background thread. 202 `{run_id}`. 409 when a run is active. 400 when `project` is empty. 503 when the weights are missing. |
| GET | `/api/runs/{run_id}` | `{run_id, project, state: "running" | "done" | "failed", step, progress (0 to 1), message}`. |
| GET | `/api/tags/{project}` | The tag file, or 404. |
| PUT | `/api/tags/{project}` | Validate and save an edited tag file. Returns the saved file. 422 when invalid. |
| GET | `/api/projects` | `{projects: [project labels with a tag file]}`. |
| GET | `/api/raycast?sweep=sweep-NN&u=..&v=..` | `{anchor: {x, y, z} or null}`. The 3D point under pano pixel (u, v), from the depth grid (`box_anchor` with a small box). The tag editor uses it to place an anchor. |

Defaults: `review_threshold` 0.5, `merge_radius` 0.2, `cabinet_radius` 2.0. Start: `.venv/bin/uvicorn pipeline.api:app --port 8000`.

## Python interfaces

```python
# pipeline/detect.py (pipeline owner)
class Detector:
    def __init__(self, weights, device=None, conf=0.05, imgsz=1280): ...
    def __call__(self, images):  # list of BGR uint8 tiles
        """-> list (one per image) of list of ((x0, y0, x1, y1), score)"""

# pipeline/ocr.py (ocr owner)
class Ocr:
    def detect(self, images):  # BGR tiles
        """-> list (one per image) of list of (polygon float array (4, 2) in tile px, score)"""
    def recognize(self, crops):  # BGR crops
        """-> list of (text, score)"""
    def read(self, image):  # one BGR view
        """-> list of (text, score), the text lines of the view in reading order"""
    def labels(self, faces, boxes, pano_width, pano_height):  # pano text line boxes of one sweep
        """-> list of (block box, detection score, text, text score) for the cabinet labels"""
def box_view(faces, box, pano_width, pano_height, min_width=640):
    """Rectified, upscaled, full-resolution perspective crop centered on a pano box."""
def device_name(text_lines):  # list of (text, score) from a device crop
    """-> str, the name with the fixed plate print removed ("" when nothing is left)"""
def is_cabinet_label(text, score):
    """-> bool"""
```

`faces` is the output of `Scan(path).faces(index)`: a list of `(BGR image, R)`.

## Real test set

`eval/real-devices.json` holds the ground truth devices (center, normal, plate size, `target` true or false). The real tiles and crops are test only. Do not use them for training or tuning.

import io
import json
import logging
import os
import threading
import uuid
from functools import cache, lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import tagfile
from pipeline.anchor import box_anchor
from pipeline.documents import slug
from pipeline.run import MIN_CONFIDENCE, TILE_CONFIDENCE, run_pipeline

ROOT = Path(__file__).resolve().parent.parent
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
RAYCAST_BOX = 12.0
THUMB_SIZE = 320
log = logging.getLogger("pipeline.api")


def env_path(name, default):
    return ROOT / os.environ.get(name, default)


@cache
def _detector(weights, mtime):
    from pipeline.detect import Detector

    return Detector(weights, conf=TILE_CONFIDENCE)


def default_runner(**kwargs):
    weights = Path(kwargs["weights"])
    return run_pipeline(**kwargs, detector=_detector(str(weights), weights.stat().st_mtime))


def _r(v, n=1):
    return None if v is None else round(float(v), n)


def synth_image(root, split, image):
    stem = image.stem
    width, height = Image.open(image).size
    boxes = []
    label = root / "labels" / split / f"{stem}.txt"
    for line in label.read_text().splitlines() if label.is_file() else []:
        parts = line.split()
        if len(parts) != 5:
            continue
        cx, cy, w, h = (float(v) for v in parts[1:])
        boxes.append([_r((cx - w / 2) * width), _r((cy - h / 2) * height), _r((cx + w / 2) * width), _r((cy + h / 2) * height)])
    item = {"path": f"/synth/{root.name}/images/{split}/{image.name}", "thumb": f"/api/synth/{root.name}/thumbs/{split}/{image.name}", "name": stem, "split": split, "width": width, "height": height,
            "boxes": boxes}
    meta = root / "meta" / split / f"{stem}.json"
    if meta.is_file():
        m = json.loads(meta.read_text())
        camera = m.get("camera") or [None, None, None]
        item.update(dark=bool(m.get("dark")), fov_deg=m.get("fov_deg"), camera_z=_r(camera[2], 2), jpeg_quality=m.get("jpeg_quality"),
                    plates=[{"kind": p.get("kind"), "labeled": bool(p.get("labeled")), "box": [_r(v) for v in p["box"]] if p.get("box") else None,
                             "width_px": _r(p.get("width_px")), "distance_m": _r(p.get("distance_m"), 2),
                             "off_normal_deg": _r(p.get("off_normal_deg")), "visible": _r(p.get("visible"), 2),
                             "drop_reason": p.get("drop_reason")} for p in m.get("plates", [])])
    return item


def synth_images(root):
    return sorted((split, image) for split in ("train", "val") for image in (root / "images" / split).glob("*.jpg"))


@lru_cache(maxsize=8)
def synth_set(root, stamp):
    images = [synth_image(root, split, image) for split, image in synth_images(root)]
    profile = next((json.loads(m.read_text()).get("profile") for m in sorted((root / "meta").glob("*/*.json"))[:1]), None)
    return {"name": root.name, "profile": profile, "count": len(images), "images": images}


class RunRequest(BaseModel):
    project: str
    site: str | None = None
    review_threshold: float = Field(0.9, ge=0, le=1)
    merge_radius: float = Field(0.2, gt=0, allow_inf_nan=False)
    cabinet_radius: float = Field(2.0, gt=0, allow_inf_nan=False)
    min_confidence: float = Field(MIN_CONFIDENCE, ge=0, le=1)


def create_app(scan_dir=None, e57_path=None, weights=None, tags_dir=None, docs_dir=None, synth_dir=None, runner=default_runner):
    scan_dir = Path(scan_dir or env_path("REX_SCAN_DIR", "data/scan"))
    e57_path = Path(e57_path or env_path("REX_E57", "cloud_0.e57"))
    weights = Path(weights or env_path("REX_WEIGHTS", "models/rex615.pt"))
    tags_dir = Path(tags_dir or env_path("REX_TAGS_DIR", "data/tags"))
    docs_dir = Path(docs_dir or env_path("REX_DOCS_DIR", "docs"))
    synth_dir = Path(synth_dir or env_path("REX_SYNTH_DIR", "data/synth"))

    app = FastAPI(title="REX615 pipeline", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=4096)
    app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    runs, lock = {}, threading.Lock()

    def manifest():
        path = scan_dir / "manifest.json"
        if not path.is_file():
            raise HTTPException(404, "scan manifest not found")
        return json.loads(path.read_text())

    @lru_cache(maxsize=4)
    def range_grid(sid):
        with np.load(scan_dir / "depth" / f"{sid}.npz") as z:
            return z["range"]

    @app.get("/api/scan")
    def get_scan():
        data = manifest()
        for s in data["sweeps"]:
            s["pano"] = f"/scan/{s['pano']}"
        return data

    @app.post("/api/runs", status_code=202)
    def start_run(req: RunRequest):
        project = req.project.strip()
        if not project:
            raise HTTPException(400, "project is empty")
        if not weights.is_file():
            raise HTTPException(503, f"detector weights not found: {weights.name}")
        with lock:
            if any(r["state"] == "running" for r in runs.values()):
                raise HTTPException(409, "a run is active")
            run_id = uuid.uuid4().hex[:12]
            run = runs[run_id] = {"run_id": run_id, "project": project, "state": "running", "step": "queued", "progress": 0.0, "message": ""}

        def progress(step, fraction, message):
            run.update(step=step, progress=round(float(fraction), 3), message=message)

        def work():
            try:
                runner(
                    project=project, site=(req.site or "").strip() or project, scan_dir=scan_dir, e57_path=e57_path,
                    weights=weights, tags_dir=tags_dir, docs_dir=docs_dir, review_threshold=req.review_threshold,
                    merge_radius=req.merge_radius, cabinet_radius=req.cabinet_radius, min_confidence=req.min_confidence,
                    progress=progress,
                )
                run.update(state="done", step="done", progress=1.0)
            except Exception as e:
                log.exception("run %s failed", run_id)
                run.update(state="failed", message=f"{type(e).__name__}: {e}")

        threading.Thread(target=work, name=f"run-{run_id}", daemon=True).start()
        return {"run_id": run_id}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        if run_id not in runs:
            raise HTTPException(404, "unknown run")
        return dict(runs[run_id])

    @app.get("/api/tags/{project:path}")
    def get_tags(project: str):
        data = tagfile.load(tags_dir, project)
        if data is None:
            raise HTTPException(404, "no tag file for this project")
        return data

    @app.put("/api/tags/{project:path}")
    def put_tags(project: str, body: tagfile.TagFile):
        if slug(body.project) != slug(project):
            raise HTTPException(422, "project in the body does not match the path")
        return tagfile.save(tags_dir, body.model_dump(mode="json"))

    @app.get("/api/projects")
    def get_projects():
        projects = set()
        for path in tags_dir.glob("*.json"):
            try:
                projects.add(json.loads(path.read_text(encoding="utf-8"))["project"])
            except (ValueError, KeyError, TypeError):
                continue
        return {"projects": sorted(projects)}

    @app.get("/api/raycast")
    def raycast(sweep: str, u: float, v: float):
        data = manifest()
        W, H = data["pano_width"], data["pano_height"]
        s = next((s for s in data["sweeps"] if s["id"] == sweep), None)
        if s is None:
            raise HTTPException(404, "unknown sweep")
        if not (np.isfinite(u) and 0 <= v <= H):
            raise HTTPException(422, "u or v is out of range")
        box = (float(np.mod(u, W)) - RAYCAST_BOX / 2, v - RAYCAST_BOX / 2, RAYCAST_BOX, RAYCAST_BOX)
        anchor, _ = box_anchor(range_grid(sweep), np.array(s["rotation"]), np.array(s["position"]), box, W, H)
        return {"anchor": tagfile.point(anchor)}

    def synth_roots():
        return {p.name: p for p in sorted(synth_dir.iterdir()) if (p / "images").is_dir()} if synth_dir.is_dir() else {}

    def synth_stamp(root):
        return tuple((root / kind / split).stat().st_mtime_ns if (root / kind / split).is_dir() else 0
                     for kind in ("images", "labels", "meta") for split in ("train", "val"))

    @app.get("/api/synth")
    def list_synth():
        sets = []
        for root in synth_roots().values():
            data = synth_set(root, synth_stamp(root))
            splits = {s: sum(i["split"] == s for i in data["images"]) for s in ("train", "val")}
            sets.append({"name": data["name"], "profile": data["profile"], "count": data["count"], **splits})
        return {"sets": sets}

    @app.get("/api/synth/{name}")
    def get_synth(name: str):
        root = synth_roots().get(name)
        if root is None:
            raise HTTPException(404, "unknown synthetic set")
        return synth_set(root, synth_stamp(root))

    @app.get("/api/synth/{name}/thumbs/{split}/{file}")
    def get_synth_thumb(name: str, split: str, file: str):
        root = synth_roots().get(name)
        path = root / "images" / split / file if root and split in ("train", "val") and Path(file).name == file else None
        if path is None or path.suffix != ".jpg" or not path.is_file():
            raise HTTPException(404, "unknown image")
        with Image.open(path) as im:
            im.draft("RGB", (THUMB_SIZE, THUMB_SIZE))
            im = im.convert("RGB")
            im.thumbnail((THUMB_SIZE, THUMB_SIZE))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=80)
        return Response(buf.getvalue(), media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})

    @app.get("/models/rex615.onnx")
    def onnx_model():
        path = weights.with_suffix(".onnx")
        if not path.is_file():
            raise HTTPException(404, f"browser model not found: {path.name}")
        return FileResponse(path, media_type="application/octet-stream")

    app.mount("/scan", StaticFiles(directory=scan_dir, check_dir=False), name="scan")
    app.mount("/documents", StaticFiles(directory=docs_dir, check_dir=False), name="documents")
    app.mount("/synth", StaticFiles(directory=synth_dir, check_dir=False), name="synth")
    return app


app = create_app()

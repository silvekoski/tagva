import json
import logging
import os
import threading
import uuid
from functools import cache, lru_cache
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import tagfile
from pipeline.anchor import box_anchor
from pipeline.documents import slug
from pipeline.run import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
RAYCAST_BOX = 12.0
log = logging.getLogger("pipeline.api")


def env_path(name, default):
    return ROOT / os.environ.get(name, default)


@cache
def _detector(weights, mtime):
    from pipeline.detect import Detector

    return Detector(weights)


def default_runner(**kwargs):
    weights = Path(kwargs["weights"])
    return run_pipeline(**kwargs, detector=_detector(str(weights), weights.stat().st_mtime))


class RunRequest(BaseModel):
    project: str
    site: str | None = None
    review_threshold: float = Field(0.5, ge=0, le=1)
    merge_radius: float = Field(0.2, gt=0, allow_inf_nan=False)
    cabinet_radius: float = Field(2.0, gt=0, allow_inf_nan=False)


def create_app(scan_dir=None, e57_path=None, weights=None, tags_dir=None, docs_dir=None, runner=default_runner):
    scan_dir = Path(scan_dir or env_path("REX_SCAN_DIR", "data/scan"))
    e57_path = Path(e57_path or env_path("REX_E57", "cloud_0.e57"))
    weights = Path(weights or env_path("REX_WEIGHTS", "models/rex615.pt"))
    tags_dir = Path(tags_dir or env_path("REX_TAGS_DIR", "data/tags"))
    docs_dir = Path(docs_dir or env_path("REX_DOCS_DIR", "docs"))

    app = FastAPI(title="REX615 pipeline", docs_url=None, redoc_url=None, openapi_url=None)
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
                    merge_radius=req.merge_radius, cabinet_radius=req.cabinet_radius, progress=progress,
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

    app.mount("/scan", StaticFiles(directory=scan_dir, check_dir=False), name="scan")
    app.mount("/documents", StaticFiles(directory=docs_dir, check_dir=False), name="documents")
    return app


app = create_app()

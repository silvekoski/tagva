import json
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pipeline import tagfile
from pipeline.api import create_app
from pipeline.scan import GRID_COLS, GRID_ROWS
from pipeline.sphere import equirect_to_dirs

W, H = 8192, 4096
POSITION = [1.0, 2.0, 1.5]


def sample_tags(project="VEO DEMO"):
    device = {
        "name": "Q01", "device_type": "REX615",
        "boxes": [{"scan_position": "sweep-00", "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}],
        "anchor": {"x": 1.0, "y": 2.0, "z": 3.0}, "confidence": 0.9, "documents": [], "review": False, "review_reasons": [],
    }
    return tagfile.build(project, project, 0.5, 0.2, 2.0, "x.e57", [("H01", (1, 2, 1))], [(0, device)])


@pytest.fixture
def env(tmp_path):
    scan = tmp_path / "scan"
    (scan / "depth").mkdir(parents=True)
    (scan / "panos").mkdir()
    (scan / "panos" / "sweep-00.jpg").write_bytes(b"jpeg")
    np.savez_compressed(scan / "depth" / "sweep-00.npz", range=np.full((GRID_ROWS, GRID_COLS), 2.0, np.float16))
    manifest = {"source": "x.e57", "pano_width": W, "pano_height": H, "sweeps": [
        {"id": "sweep-00", "index": 0, "name": "Sweep 0", "position": POSITION, "rotation": np.eye(3).tolist(), "pano": "panos/sweep-00.jpg"}]}
    (scan / "manifest.json").write_text(json.dumps(manifest))
    docs = tmp_path / "docs" / "devices" / "REX615"
    docs.mkdir(parents=True)
    (docs / "m.pdf").write_bytes(b"pdf")
    weights = tmp_path / "w.pt"
    weights.write_bytes(b"w")
    gate = threading.Event()
    calls = []

    def runner(**kw):
        calls.append(kw)
        kw["progress"]("detect", 0.5, "half")
        gate.wait(5)
        if kw["project"] == "boom":
            raise RuntimeError("fake failure")
        tagfile.save(kw["tags_dir"], sample_tags(kw["project"]))

    app = create_app(scan, tmp_path / "x.e57", weights, tmp_path / "tags", tmp_path / "docs", runner=runner)
    return TestClient(app), gate, calls, weights


def wait_done(client, run_id):
    for _ in range(100):
        r = client.get(f"/api/runs/{run_id}").json()
        if r["state"] != "running":
            return r
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def test_scan_and_static(env):
    client, *_ = env
    data = client.get("/api/scan").json()
    assert data["sweeps"][0]["pano"] == "/scan/panos/sweep-00.jpg"
    assert client.get("/scan/panos/sweep-00.jpg").content == b"jpeg"
    assert client.get("/documents/devices/REX615/m.pdf").content == b"pdf"
    assert client.get("/documents/../w.pt").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_cors(env):
    client, *_ = env
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        r = client.options("/api/runs", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
        assert r.headers["access-control-allow-origin"] == origin
    r = client.get("/api/projects", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_run_lifecycle(env):
    client, gate, calls, weights = env
    assert client.post("/api/runs", json={"project": "  "}).status_code == 400
    r = client.post("/api/runs", json={"project": "VEO DEMO", "review_threshold": 0.7})
    assert r.status_code == 202
    run_id = r.json()["run_id"]
    time.sleep(0.05)
    state = client.get(f"/api/runs/{run_id}").json()
    assert state["state"] == "running" and state["step"] == "detect" and state["progress"] == 0.5 and state["project"] == "VEO DEMO"
    assert client.post("/api/runs", json={"project": "other"}).status_code == 409
    gate.set()
    assert wait_done(client, run_id)["state"] == "done"
    assert calls[0]["site"] == "VEO DEMO" and calls[0]["review_threshold"] == 0.7 and calls[0]["merge_radius"] == 0.2
    assert client.get("/api/tags/VEO DEMO").json()["project"] == "VEO DEMO"
    assert client.get("/api/projects").json() == {"projects": ["VEO DEMO"]}
    r = client.post("/api/runs", json={"project": "boom"})
    failed = wait_done(client, r.json()["run_id"])
    assert failed["state"] == "failed" and "fake failure" in failed["message"]
    assert client.get("/api/runs/nope").status_code == 404
    weights.unlink()
    assert client.post("/api/runs", json={"project": "VEO DEMO"}).status_code == 503


def test_tags_get_put(env):
    client, *_ = env
    assert client.get("/api/tags/VEO DEMO").status_code == 404
    data = sample_tags()
    data["tags"][0]["devices"][0]["review_reasons"] = ["ocr_conflict"]
    r = client.put("/api/tags/VEO DEMO", json=data)
    assert r.status_code == 200 and r.json()["tags"][0]["devices"][0]["review"] is True
    assert client.get("/api/tags/VEO DEMO").json() == r.json()
    assert client.put("/api/tags/OTHER", json=data).status_code == 422
    data["tags"][0]["devices"][0]["review_reasons"] = ["nope"]
    assert client.put("/api/tags/VEO DEMO", json=data).status_code == 422


def test_tags_project_with_slash(env):
    client, *_ = env
    data = sample_tags("VEO/2026 A")
    for path in ("/api/tags/VEO/2026 A", "/api/tags/VEO%2F2026%20A"):
        r = client.put(path, json=data)
        assert r.status_code == 200 and r.json()["project"] == "VEO/2026 A"
        assert client.get(path).json() == r.json()
    assert client.get("/api/tags/VEO/2026 B").status_code == 404
    assert client.put("/api/tags/VEO/2026 B", json=data).status_code == 422
    assert client.get("/api/projects").json() == {"projects": ["VEO/2026 A"]}


def test_raycast(env):
    client, *_ = env
    u, v = 3000.0, 1800.0
    r = client.get("/api/raycast", params={"sweep": "sweep-00", "u": u, "v": v}).json()
    expect = np.array(POSITION) + 2.0 * equirect_to_dirs(u, v, W, H)
    assert np.allclose([r["anchor"][k] for k in "xyz"], expect, atol=1e-3)
    assert client.get("/api/raycast", params={"sweep": "sweep-09", "u": u, "v": v}).status_code == 404
    assert client.get("/api/raycast", params={"sweep": "sweep-00", "u": u, "v": -5}).status_code == 422


def test_onnx_model_route(tmp_path):
    from fastapi.testclient import TestClient

    from pipeline.api import create_app

    weights = tmp_path / "rex615.pt"
    client = TestClient(create_app(scan_dir=tmp_path, weights=weights, tags_dir=tmp_path, docs_dir=tmp_path))
    assert client.get("/models/rex615.onnx").status_code == 404
    (tmp_path / "rex615.onnx").write_bytes(b"onnx")
    r = client.get("/models/rex615.onnx")
    assert r.status_code == 200 and r.content == b"onnx"

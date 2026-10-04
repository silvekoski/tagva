from pipeline.documents import lookup, slug


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_slug():
    assert slug("VEO DEMO/2026") == "VEO-DEMO-2026"
    assert slug("a.b_c-D9") == "a.b_c-D9"
    assert slug("Vaasa ä") == "Vaasa--"


def test_lookup(tmp_path):
    touch(tmp_path / "devices/REX615/rex615-manual.pdf")
    touch(tmp_path / "devices/REX615/.DS_Store")
    touch(tmp_path / "devices/REX615/rex615-manual.index.json")
    touch(tmp_path / "devices/REF615/ref615-manual.pdf")
    touch(tmp_path / "projects/VEO-DEMO/drawings/h03_single_line.pdf")
    touch(tmp_path / "projects/VEO-DEMO/maintenance-reports/2026-05-01.pdf")
    touch(tmp_path / "projects/VEO-DEMO/inspection-reports/2026-06-01.pdf")
    touch(tmp_path / "projects/OTHER/drawings/x.pdf")
    docs = lookup(tmp_path, "REX615", "VEO DEMO")
    assert docs == [
        {"title": "rex615 manual", "kind": "manual", "url": "/documents/devices/REX615/rex615-manual.pdf"},
        {"title": "h03 single line", "kind": "drawing", "url": "/documents/projects/VEO-DEMO/drawings/h03_single_line.pdf"},
        {"title": "2026 05 01", "kind": "maintenance_report", "url": "/documents/projects/VEO-DEMO/maintenance-reports/2026-05-01.pdf"},
        {"title": "2026 06 01", "kind": "inspection_report", "url": "/documents/projects/VEO-DEMO/inspection-reports/2026-06-01.pdf"},
    ]


def test_lookup_missing_folders_and_dot_project(tmp_path):
    touch(tmp_path / "projects/drawings/x.pdf")
    assert lookup(tmp_path, "REX615", "..") == []
    assert lookup(tmp_path / "missing", "REX615", "P") == []

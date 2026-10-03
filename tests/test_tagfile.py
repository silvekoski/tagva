import json
import re

import pytest
from pydantic import ValidationError

from pipeline import tagfile


def device(anchor, reasons=(), confidence=0.9, sweep="sweep-01"):
    return {
        "name": "",
        "device_type": "REX615",
        "boxes": [{"scan_position": sweep, "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0, "confidence": confidence, "ocr_text": ""}],
        "anchor": tagfile.point(anchor),
        "confidence": confidence,
        "documents": [{"title": "m", "kind": "manual", "url": "/documents/devices/REX615/m.pdf"}],
        "review": bool(reasons),
        "review_reasons": list(reasons),
    }


def sample():
    cabinets = [("H10 FEED", (0, 10, 1)), ("H2 FEED", (0, 2, 1)), ("OT1", (5, 0, 1))]
    devices = [
        (0, device((0, 10, 2))),
        (1, device((0, 2.2, 2))),
        (1, device((0, 1.8, 2))),
        (None, device((9, 9, 9), ["no_anchor"])),
        (None, device(None, ["no_anchor"])),
        (None, device((1, 1, 1))),
    ]
    return tagfile.build("VEO DEMO", "Site", 0.5, 0.2, 2.0, "cloud_0.e57", cabinets, devices)


def test_build_order_ids_and_unassigned():
    data = sample()
    assert [t["cabinet"] for t in data["tags"]] == ["H2 FEED", "H10 FEED", "OT1", "unassigned"]
    assert [t["id"] for t in data["tags"]] == ["tag-001", "tag-002", "tag-003", "tag-unassigned"]
    assert [d["device_id"] for t in data["tags"] for d in t["devices"]] == [f"dev-{i:03d}" for i in range(1, 7)]
    assert [d["anchor"]["y"] for d in data["tags"][0]["devices"]] == [1.8, 2.2]
    assert data["tags"][2]["devices"] == []
    assert data["tags"][3]["anchor"] == {"x": 5.0, "y": 5.0, "z": 5.0}
    assert data["tags"][3]["devices"][-1]["anchor"] is None
    assert data["tags"][0]["path"] == ["Site", "H2 FEED"]
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", data["generated_at"])
    tagfile.TagFile.model_validate(data)


def test_save_load_round_trip(tmp_path):
    saved = tagfile.save(tmp_path, sample())
    assert (tmp_path / "VEO-DEMO.json").is_file()
    assert tagfile.load(tmp_path, "VEO DEMO") == saved
    assert saved["scan"] == "cloud_0.e57"
    assert tagfile.load(tmp_path, "nothing") is None
    assert not list(tmp_path.glob("*.tmp"))


def test_validation_normalizes_review():
    data = sample()
    d = data["tags"][0]["devices"][0]
    d["review_reasons"] = ["ocr_conflict", "low_confidence"]
    d["review"] = False
    out = tagfile.TagFile.model_validate(data).model_dump(mode="json")
    d = out["tags"][0]["devices"][0]
    assert d["review_reasons"] == ["low_confidence", "ocr_conflict"] and d["review"] is True


@pytest.mark.parametrize("mutate", [
    lambda d: d["tags"][0]["devices"][0].update(review_reasons=["bad_reason"]),
    lambda d: d["tags"][0]["devices"][0].update(confidence=1.5),
    lambda d: d["tags"][0]["devices"][0].update(anchor={"x": float("nan"), "y": 0, "z": 0}),
    lambda d: d["tags"][0]["devices"][0]["documents"][0].update(kind="photo"),
    lambda d: d["tags"][1]["devices"][0].update(device_id="dev-001"),
    lambda d: d["tags"][1].update(id="tag-001"),
    lambda d: d["tags"][0]["devices"][0].pop("boxes"),
    lambda d: d.update(project=""),
    lambda d: d.update(merge_radius=0),
])
def test_validation_rejects(mutate):
    data = json.loads(json.dumps(sample()))
    mutate(data)
    with pytest.raises(ValidationError):
        tagfile.TagFile.model_validate(data)

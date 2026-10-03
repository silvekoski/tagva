import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pipeline.documents import slug
from pipeline.review import REASONS

Finite = Annotated[float, Field(allow_inf_nan=False)]
UNASSIGNED = "unassigned"


class Model(BaseModel):
    model_config = ConfigDict(extra="allow")


class Point(Model):
    x: Finite
    y: Finite
    z: Finite


class Box(Model):
    scan_position: str
    x: Finite
    y: Finite
    width: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    height: Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Document(Model):
    title: str
    kind: Literal["manual", "drawing", "maintenance_report", "inspection_report"]
    url: str


class Device(Model):
    device_id: Annotated[str, Field(min_length=1)]
    name: str
    device_type: str
    boxes: list[Box]
    anchor: Point | None
    confidence: Annotated[float, Field(ge=0, le=1)]
    documents: list[Document]
    review: bool
    review_reasons: list[Literal[REASONS]]

    @model_validator(mode="after")
    def _review(self):
        self.review_reasons = [r for r in REASONS if r in self.review_reasons]
        self.review = bool(self.review_reasons)
        return self


class Tag(Model):
    id: Annotated[str, Field(min_length=1)]
    cabinet: str
    anchor: Point | None
    path: list[str]
    devices: list[Device]


class TagFile(Model):
    project: Annotated[str, Field(min_length=1)]
    site: str
    review_threshold: Annotated[float, Field(ge=0, le=1)]
    merge_radius: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    cabinet_radius: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    tags: list[Tag]

    @model_validator(mode="after")
    def _unique_ids(self):
        tag_ids = [t.id for t in self.tags]
        device_ids = [d.device_id for t in self.tags for d in t.devices]
        if len(set(tag_ids)) != len(tag_ids) or len(set(device_ids)) != len(device_ids):
            raise ValueError("tag ids and device ids must be unique")
        return self


def point(a):
    return None if a is None else {k: round(float(v), 4) for k, v in zip("xyz", a)}


def _natural(text):
    return [int(p) if p.isdigit() else p.casefold() for p in re.split(r"(\d+)", text)]


def _anchor_key(a):
    return (1, 0.0, 0.0, 0.0) if a is None else (0, a["x"], a["y"], a["z"])


def _device_key(d):
    first = min(((b["scan_position"], b["x"], b["y"]) for b in d["boxes"]), default=("", 0.0, 0.0))
    return _anchor_key(d["anchor"]), first


def build(project, site, review_threshold, merge_radius, cabinet_radius, scan, cabinets, devices):
    """cabinets: list of (name, anchor xyz). devices: list of (cabinet index or None, device dict
    without device_id, anchor already a point dict). Assigns ids in a deterministic order."""
    members = {i: [] for i in range(len(cabinets))}
    unassigned = []
    for cabinet, device in devices:
        (unassigned if cabinet is None else members[cabinet]).append(device)
    order = sorted(range(len(cabinets)), key=lambda i: (_natural(cabinets[i][0]), _anchor_key(point(cabinets[i][1]))))
    groups = [(f"tag-{k:03d}", cabinets[i][0], point(cabinets[i][1]), members[i]) for k, i in enumerate(order, 1)]
    if unassigned:
        anchors = [d["anchor"] for d in unassigned if d["anchor"] is not None]
        mean = None if not anchors else [sum(a[k] for a in anchors) / len(anchors) for k in "xyz"]
        groups.append(("tag-unassigned", UNASSIGNED, point(mean), unassigned))
    tags, n = [], 0
    for tag_id, name, anchor, devs in groups:
        out = []
        for d in sorted(devs, key=_device_key):
            n += 1
            out.append({"device_id": f"dev-{n:03d}", **d})
        tags.append({
            "id": tag_id,
            "cabinet": name,
            "anchor": anchor,
            "path": [site, name],
            "devices": out,
        })
    return {
        "project": project,
        "site": site,
        "review_threshold": review_threshold,
        "merge_radius": merge_radius,
        "cabinet_radius": cabinet_radius,
        "scan": scan,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tags": tags,
    }


def tag_path(tags_dir, project):
    return Path(tags_dir) / f"{slug(project)}.json"


def save(tags_dir, data):
    data = TagFile.model_validate(data).model_dump(mode="json")
    path = tag_path(tags_dir, data["project"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return data


def load(tags_dir, project):
    path = tag_path(tags_dir, project)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

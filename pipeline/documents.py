import re
from pathlib import Path

INDEX_SUFFIX = ".index.json"
COVER_SUFFIX = ".cover.png"

PROJECT_KINDS = {
    "drawings": "drawing",
    "maintenance-reports": "maintenance_report",
    "inspection-reports": "inspection_report",
}


def slug(text):
    return re.sub(r"[^A-Za-z0-9._-]", "-", text)


def _entries(docs_dir, folder, kind):
    if not folder.is_dir():
        return []
    return [
        {
            "title": re.sub(r"[-_]+", " ", f.stem),
            "kind": kind,
            "url": "/documents/" + f.relative_to(docs_dir).as_posix(),
        }
        for f in sorted(folder.iterdir())
        if f.is_file() and not f.name.startswith(".") and not f.name.endswith((INDEX_SUFFIX, COVER_SUFFIX))
    ]


def lookup(docs_dir, device_type, project):
    docs_dir = Path(docs_dir)
    out = _entries(docs_dir, docs_dir / "devices" / slug(device_type), "manual")
    project_slug = slug(project)
    if project_slug.strip("."):
        for folder, kind in PROJECT_KINDS.items():
            out += _entries(docs_dir, docs_dir / "projects" / project_slug / folder, kind)
    return out

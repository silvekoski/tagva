import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

from pipeline.documents import INDEX_SUFFIX


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"\.{4,}", " ", text or "")).strip()


def outline(reader, text):
    out = []

    def walk(items, level):
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            page = reader.get_destination_page_number(item)
            if page is None or page < 0:
                continue
            title = clean(item.title)
            if title not in text[page] and page + 1 < len(text) and title in text[page + 1]:
                page += 1
            out.append({"title": title, "page": page + 1, "level": level})

    walk(reader.outline, 0)
    return out


def build(pdf):
    reader = PdfReader(pdf)
    labels = reader.page_labels
    mismatched = [i + 1 for i, label in enumerate(labels) if label != str(i + 1)]
    if mismatched:
        print(f"{pdf}: {len(mismatched)} printed page labels differ from the PDF page index, first {mismatched[0]}", file=sys.stderr)
    text = [clean(p.extract_text()) for p in reader.pages]
    return {"pages": len(text), "bytes": pdf.stat().st_size, "outline": outline(reader, text), "text": text}


def main(docs_dir="docs"):
    for pdf in sorted(Path(docs_dir, "devices").glob("*/*.pdf")):
        target = pdf.with_name(pdf.stem + INDEX_SUFFIX)
        target.write_text(json.dumps(build(pdf), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        print(target)


if __name__ == "__main__":
    main(*sys.argv[1:])

"""Fetch a fixed CPython source snapshot, clean RST and create traceable text units."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "starter"))
from src.ingestion import normalize_text
from src.models import DocumentPage

TAG = "v3.12.0"
BASE = f"https://raw.githubusercontent.com/python/cpython/{TAG}"
CHAPTERS = ["introduction", "controlflow", "datastructures", "modules", "inputoutput",
            "errors", "classes", "stdlib", "stdlib2", "venv"]


def clean_rst(text: str) -> str:
    # Keep prose and examples; remove navigation/targets/index markup.
    lines = []
    skipping = False
    for line in text.splitlines():
        if re.match(r"^\.\. (index|sectionauthor|include|toctree)::", line):
            skipping = True
            continue
        if skipping:
            if not line.strip() or line.startswith((" ", "\t")):
                continue
            skipping = False
        if re.match(r"^\.\. _.*:$", line) or re.match(r"^[=~^*\-]{3,}$", line.strip()):
            continue
        if re.match(r"^\.\. (versionadded|versionchanged|deprecated)::", line):
            line = re.sub(r"^\.\. (\w+)::", r"\1:", line)
        elif re.match(r"^\.\. (note|warning|tip)::", line):
            line = re.sub(r"^\.\. (\w+)::", r"\1:", line)
        elif re.match(r"^\.\. (code-block|highlight)::", line):
            continue
        line = re.sub(r":\w+:\x60([^\x60]+)\x60", lambda m: m.group(1).split(" <")[0].lstrip("~"), line)
        line = line.replace("\x60\x60", "")
        lines.append(line)
    return normalize_text("\n".join(lines))


def source_units(text: str, target: int = 2400, minimum: int = 1500) -> list[tuple[int, int]]:
    boundaries = [m.start() for m in re.finditer(r"\n\n", text)]
    units = []
    start = 0
    while len(text) - start >= target + minimum:
        choices = [p for p in boundaries if start + target <= p <= start + target + 800]
        end = choices[0] if choices else text.rfind(" ", start + minimum, start + target + 1)
        if end <= start:
            end = start + target
        units.append((start, end))
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    if start < len(text):
        if len(text) - start < minimum and units:
            previous_start, _ = units.pop()
            units.append((previous_start, len(text)))
        else:
            units.append((start, len(text)))
    return units


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    raw = ROOT / "data/raw"
    raw.mkdir(parents=True, exist_ok=True)
    if args.download:
        for chapter in CHAPTERS:
            data = urllib.request.urlopen(f"{BASE}/Doc/tutorial/{chapter}.rst", timeout=60).read()
            (raw / f"{chapter}.rst").write_bytes(data)
        (raw / "LICENSE-PYTHON.txt").write_bytes(urllib.request.urlopen(f"{BASE}/LICENSE", timeout=60).read())
    pages, entries = [], []
    accessed = datetime.now(timezone.utc).isoformat()
    for chapter in CHAPTERS:
        path = raw / f"{chapter}.rst"
        text = clean_rst(path.read_text(encoding="utf-8"))
        source = f"https://github.com/python/cpython/blob/{TAG}/Doc/tutorial/{chapter}.rst"
        units = source_units(text)
        page_entries = []
        for number, (start, end) in enumerate(units, 1):
            content = text[start:end]
            if len(content) < 1500:
                raise ValueError(f"Source unit too short: {chapter}/{number}")
            metadata = {"chapter": chapter, "language": "en", "version": "3.12.0",
                        "source_char_start": start, "source_char_end": end}
            pages.append(DocumentPage(f"python-{chapter}", source, number, content, metadata))
            page_entries.append({"page": number, "char_start": start, "char_end": end, "characters": len(content)})
        entries.append({"source_id": f"python-{chapter}", "title": f"Python Tutorial: {chapter}",
                        "source_path_or_url": source, "local_path": path.relative_to(ROOT).as_posix(),
                        "license_or_permission": "PSF License Version 2; examples also 0BSD; see data/raw/LICENSE-PYTHON.txt",
                        "accessed_at": accessed, "snapshot": TAG, "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "normalized_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "normalized_characters": len(text), "physical_pages": None, "pages": page_entries})
    if len(pages) < 30:
        raise ValueError("Corpus requires at least 30 units")
    (ROOT / "data/pages.jsonl").write_text("".join(json.dumps(asdict(p), ensure_ascii=False) + "\n" for p in pages), encoding="utf-8")
    manifest = {"format": "RST text source units, not PDF physical pages", "snapshot": TAG,
                "counting_rule": "Sequential non-overlapping units >=1500 normalized characters; target 2400, prefer paragraph boundary; retain final tail >=1500. No duplicated content.",
                "normalization": "NFC; remove RST targets/index/heading rulers; unwrap inline roles; retain paragraphs and code; whitespace normalized.",
                "page_count": len(pages), "errors": [], "documents": entries}
    (ROOT / "data/manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(pages)} units, {sum(len(p.text) for p in pages)} characters from {len(entries)} sources")


if __name__ == "__main__":
    main()

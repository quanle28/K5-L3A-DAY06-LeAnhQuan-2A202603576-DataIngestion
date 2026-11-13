"""Source ingestion with Unicode normalization and explicit error reporting."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from .models import DocumentPage

LOGGER = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00ad", "").replace("\u00a0", " ")
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    from pypdf import PdfReader
    pages = []
    for number, page in enumerate(PdfReader(path).pages, 1):
        try:
            text = normalize_text(page.extract_text() or "")
        except Exception:
            LOGGER.exception("PDF extraction failed: %s page %s", document_id, number)
            raise
        if not text:
            LOGGER.warning("Empty/scanned page: %s page %s; OCR not performed", document_id, number)
        pages.append(DocumentPage(document_id, source, number, text))
    return pages


def load_pages(path: Path) -> list[DocumentPage]:
    pages = [DocumentPage(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    keys = [(p.document_id, p.page) for p in pages]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate source page IDs")
    for page in pages:
        if page.text != normalize_text(page.text):
            raise ValueError(f"Non-normalized page: {page.document_id}/{page.page}")
    return pages

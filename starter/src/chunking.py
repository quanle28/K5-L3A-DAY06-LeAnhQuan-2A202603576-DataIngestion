"""Deterministic chunks; offsets refer to normalized source pages."""
from __future__ import annotations

import hashlib
import re
from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, start: int, end: int, method: str) -> Chunk:
    while start < end and page.text[start].isspace():
        start += 1
    while end > start and page.text[end - 1].isspace():
        end -= 1
    text = page.text[start:end]
    key = f"{page.document_id}:{page.page}:{method}:{start}:{end}:{text}"
    return Chunk(hashlib.sha256(key.encode()).hexdigest(), page.document_id,
                 page.source, page.page, text,
                 {**page.metadata, "char_start": start, "char_end": end, "chunking": method})


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    chunks = []
    for start in range(0, len(page.text), size - overlap):
        end = min(start + size, len(page.text))
        if page.text[start:end].strip():
            chunks.append(_chunk(page, start, end, f"fixed-{size}-{overlap}"))
        if end == len(page.text):
            break
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    chunks = []
    start, end = None, 0
    for match in re.finditer(r"\S[\s\S]*?(?=\n\n|\Z)", page.text):
        left, right = match.span()
        if start is not None and right - start > max_size:
            chunks.append(_chunk(page, start, end, f"paragraph-{max_size}"))
            start = None
        while right - left > max_size:
            window = page.text[left:left + max_size]
            sentences = list(re.finditer(r"[.!?]\s+", window))
            boundary = sentences[-1].start() + 1 if sentences else window.rfind(" ")
            if boundary < max_size // 2:
                boundary = max_size
            chunks.append(_chunk(page, left, left + boundary, f"paragraph-{max_size}"))
            left += boundary
            while left < right and page.text[left].isspace():
                left += 1
        if left < right:
            if start is None:
                start = left
            end = right
    if start is not None:
        chunks.append(_chunk(page, start, end, f"paragraph-{max_size}"))
    return chunks

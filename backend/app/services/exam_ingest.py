"""Build one exam raw_text from PDF pages and/or photo files at submit time."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import fitz

from app.services.page_text import page_text_is_sparse, read_sparse_page
from app.services.parsers.docx_parser import parse_docx

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MIXED_UPLOAD_MESSAGE = "请分开交"
DOC_UNSUPPORTED = "暂不支持 .doc，请另存为 .docx 或 PDF"


def extract_exam_text(
    paths: list[Path],
    *,
    read_image_text: Callable[[bytes], str],
) -> str:
    if not paths:
        return ""
    kinds = []
    for path in paths:
        suf = path.suffix.lower()
        if suf == ".doc":
            raise ValueError(DOC_UNSUPPORTED)
        if suf in IMAGE_SUFFIXES:
            kinds.append("image")
        elif suf == ".pdf":
            kinds.append("pdf")
        elif suf == ".docx":
            kinds.append("docx")
        else:
            raise ValueError(MIXED_UPLOAD_MESSAGE)
    if "image" in kinds and ("pdf" in kinds or "docx" in kinds):
        raise ValueError(MIXED_UPLOAD_MESSAGE)
    doc_count = sum(1 for k in kinds if k in ("pdf", "docx"))
    if doc_count > 1:
        # Multi-select stores every path but historically only the first doc was read.
        raise ValueError(MIXED_UPLOAD_MESSAGE)
    parts: list[str] = []
    if kinds[0] == "docx":
        return parse_docx(paths[0])
    if kinds[0] == "image":
        for path in paths:
            got = read_sparse_page(lambda p=path: read_image_text(p.read_bytes()))
            if got:
                parts.append(got)
        return "\n\n".join(parts)
    return _pdf_pages(paths[0], read_image_text)


def _pdf_pages(path: Path, read_image_text: Callable[[bytes], str]) -> str:
    doc = fitz.open(path)
    parts: list[str] = []
    try:
        for page in doc:
            layer = (page.get_text("text") or "").strip()
            if not page_text_is_sparse(layer):
                parts.append(layer)
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            png = pix.tobytes("png")
            got = read_sparse_page(lambda data=png: read_image_text(data))
            if got:
                parts.append(got)
    finally:
        doc.close()
    return "\n\n".join(parts)

"""PDF 按页截取文本（扫描页走与进拆题相同的 vision 补字路径）。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import fitz  # PyMuPDF

from app.services.page_text import page_text_is_sparse, read_sparse_page


def parse_pdf_page_range_text(
    path: Path,
    start_page_1based: int,
    end_page_1based: int,
    *,
    read_image_text: Callable[[bytes], str] | None = None,
) -> str:
    """抽取闭区间 [start_page_1based, end_page_1based] 页文本（1-based，与 PDF 页码一致）。
    文字层几乎为空时，若提供 read_image_text 则按页识图，避免拆页丢掉进拆题时的 OCR。"""
    doc = fitz.open(path.as_posix())
    try:
        n = doc.page_count
        lo = int(start_page_1based)
        hi = int(end_page_1based)
        if lo < 1 or hi < 1 or lo > hi or lo > n:
            raise ValueError(f"页码无效：文档共 {n} 页，请求 {lo}-{hi}")
        hi = min(hi, n)
        parts: list[str] = []
        for i in range(lo - 1, hi):
            page = doc.load_page(i)
            layer = (page.get_text("text") or "").strip()
            if not page_text_is_sparse(layer):
                parts.append(layer)
                continue
            if read_image_text is None:
                if layer:
                    parts.append(layer)
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            png = pix.tobytes("png")
            got = read_sparse_page(lambda data=png: read_image_text(data))
            if got:
                parts.append(got)
        return "\n\n".join(parts).strip()
    finally:
        doc.close()


def pdf_page_count(path: Path) -> int:
    doc = fitz.open(path.as_posix())
    try:
        return doc.page_count
    finally:
        doc.close()

"""PDF 按页截取纯文本（用于同文件多卷拆分；不重复导出内嵌图，避免与全量解析路径冲突）。"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def parse_pdf_page_range_text(path: Path, start_page_1based: int, end_page_1based: int) -> str:
    """抽取闭区间 [start_page_1based, end_page_1based] 页文本（1-based，与 PDF 页码一致）。"""
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
            parts.append(doc.load_page(i).get_text("text"))
        return "\n\n".join(parts).strip()
    finally:
        doc.close()


def pdf_page_count(path: Path) -> int:
    doc = fitz.open(path.as_posix())
    try:
        return doc.page_count
    finally:
        doc.close()

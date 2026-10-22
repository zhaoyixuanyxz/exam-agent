"""Color knowledge-point explanation PDF from an existing analysis."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fpdf import FPDF

from app.models.schemas import KnowledgeAnalysisResult
from app.services.fonts import resolve_kaiti_font

BLOCK_FILLS = ((214, 234, 248), (252, 229, 205), (232, 218, 239))

TIMEOUT_MESSAGE = "连接超时建议重试"


class KnowledgePdfTimeout(Exception):
    def __init__(self, stored: bool):
        self.stored = stored
        super().__init__(TIMEOUT_MESSAGE)


def store_knowledge_pdf(*, already_stored: bool, write_pdf: Callable[[], None]) -> str:
    if already_stored:
        return "skip"
    try:
        write_pdf()
    except KnowledgePdfTimeout:
        raise KnowledgePdfTimeout(stored=False) from None
    return "stored"


def knowledge_pdf_blocks(ka: KnowledgeAnalysisResult, alignment: dict) -> dict:
    g1 = alignment.get("grade_min", "")
    g2 = alignment.get("grade_max", "")
    sub = alignment.get("subject", "")
    title = f"{g1}～{g2} · {sub} · {ka.theme_title}"
    orders_by_key: dict[str, list[int]] = {}
    for mapping in ka.mappings:
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        orders_by_key.setdefault(key, []).append(int(mapping.question_order))
    points = []
    for point in ka.knowledge_points:
        points.append(
            {
                "name": point.name,
                "summary": point.summary,
                "orders": orders_by_key.get(point.key, []),
            }
        )
    return {"title": title, "points": points}


def _question_labels(orders: list[int]) -> str:
    return "、".join(f"第 {n} 题" for n in orders)


def render_knowledge_pdf(payload: dict, path: Path) -> None:
    font_path = resolve_kaiti_font()
    pdf = FPDF(format="A4")
    pdf.set_margins(16, 18, 16)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_font(family="KaiTi", fname=font_path.as_posix())
    pdf.add_page()

    width = pdf.epw
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("KaiTi", "", 16)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(width, 10, str(payload.get("title") or ""), align="L")
    pdf.ln(4)

    line_h = 8.0
    pad = 3.0
    gap = 4.0
    inner_w = width - 2 * pad
    pdf.set_font("KaiTi", "", 12)
    for index, point in enumerate(payload.get("points") or []):
        text = "\n".join(
            part
            for part in (
                str(point.get("name") or ""),
                str(point.get("summary") or ""),
                _question_labels(point.get("orders") or []),
            )
            if part
        )
        measured = pdf.multi_cell(
            inner_w,
            line_h,
            text,
            align="L",
            dry_run=True,
            output="LINES",
        )
        line_count = len(measured) if measured else 1
        block_h = line_count * line_h + 2 * pad
        if pdf.get_y() + block_h > pdf.page_break_trigger:
            pdf.add_page()
        x = pdf.l_margin
        y = pdf.get_y()
        pdf.set_fill_color(*BLOCK_FILLS[index % 3])
        pdf.rect(x, y, width, block_h, style="F")
        pdf.set_xy(x + pad, y + pad)
        pdf.multi_cell(inner_w, line_h, text, align="L")
        pdf.set_xy(pdf.l_margin, y + block_h + gap)

    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(path.as_posix())

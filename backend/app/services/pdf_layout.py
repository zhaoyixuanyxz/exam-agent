"""练习 PDF 版式：标题/题头/选项/插图留白等统一入口，减少 pdf_render 内重复与魔法数。"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fpdf import FPDF

# 与历史 pdf_render 保持一致（单源，供配图留白等共用）
LH_TITLE = 11.0
LH_BODY = 8.2
LH_OPTION = 7.8
INDENT_OPT = 6.0
GAP_AFTER_Q = 5.0
GAP_BEFORE_FIG = 3.0
GAP_AFTER_FIG = 2.0
LH_CAPTION = 7.0
MIN_FIG_SPACE_MM = 78.0


def layout_document_title(pdf: FPDF, w: float, title: str, *, title_suffix: str = "") -> None:
    """首页/文档主标题 + 下划线 + 段后空行。"""
    pdf.set_font("KaiTi", "", 15)
    pdf.set_text_color(35, 35, 35)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w, LH_TITLE, title + title_suffix, align="L")
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.2)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y + 1.5, pdf.w - pdf.r_margin, y + 1.5)
    pdf.ln(5)


def layout_question_heading(pdf: FPDF, w: float, order_index: int, qtype: str) -> None:
    """「第 n 题　【题型】」行。"""
    pdf.set_font("KaiTi", "", 11)
    pdf.set_text_color(20, 60, 120)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w, LH_BODY, f"第 {order_index} 题　【{qtype}】", align="L")
    pdf.ln(1)


def layout_answer_section_heading(pdf: FPDF, w: float) -> None:
    pdf.set_font("KaiTi", "", 10)
    pdf.set_text_color(0, 95, 55)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w, LH_OPTION, "【参考答案】", align="L")
    pdf.ln(0.5)


def ensure_room_for_figure(pdf: FPDF, min_space_mm: float = MIN_FIG_SPACE_MM) -> None:
    """插图前：底部空间不足则换页。"""
    if pdf.get_y() + min_space_mm > pdf.h - pdf.b_margin:
        pdf.add_page()


def layout_options_block(
    pdf: FPDF,
    w: float,
    options: list[str],
    *,
    format_option_line: Callable[[int, str], str],
) -> None:
    """多选/单选选项列表；format_option_line(j, opt) -> 已排版好的单行文本。"""
    pdf.ln(1)
    pdf.set_font("KaiTi", "", 10.5)
    pdf.set_text_color(45, 45, 45)
    inner_w = w - INDENT_OPT
    for j, opt in enumerate(options):
        line = format_option_line(j, opt)
        pdf.set_x(pdf.l_margin + INDENT_OPT)
        pdf.multi_cell(inner_w, LH_OPTION, line, align="L")
    pdf.set_text_color(30, 30, 30)


def spacing_after_question_block(pdf: FPDF) -> None:
    pdf.ln(GAP_AFTER_Q)

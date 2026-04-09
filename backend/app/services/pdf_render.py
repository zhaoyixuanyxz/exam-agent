"""练习 PDF：米白底、楷体、水印；题干/解析以文字直排为主，避免碎片公式图破坏版式。"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from fpdf import FPDF

from app.config import settings
from app.models.schemas import PracticeQuestion, PracticeSet, PracticeSvgSpec
from app.services.fonts import resolve_kaiti_font
from app.services.pdf_layout import (
    GAP_AFTER_FIG,
    GAP_AFTER_Q,
    GAP_BEFORE_FIG,
    INDENT_OPT,
    LH_BODY,
    LH_CAPTION,
    LH_OPTION,
    LH_TITLE,
    MIN_FIG_SPACE_MM,
    ensure_room_for_figure,
    layout_answer_section_heading,
    layout_document_title,
    layout_options_block,
    layout_question_heading,
    spacing_after_question_block,
)
from app.services.pdf_math_inline import mathtext_inner_to_png_bytes
from app.services.pdf_math_replacements import (
    latex_inner_to_printable,
    replace_extensible_arrows,
    replace_mhchem_ce_braces,
)
from app.services.practice_figure_diagnostics import (
    FigureEmbedRecord,
    append_figure_embed_record,
    log_figure_embed,
)
from app.services.practice_path_security import resolve_under_data_dir
from app.services.practice_svg_safe import sanitize_practice_svg

logger = logging.getLogger(__name__)

RICE = (250, 248, 245)
WATERMARK = "朱老师私密资料，仅供参考！！"

# 兼容旧代码与测试：别名指向 pdf_layout 单源常量
_LH_TITLE = LH_TITLE
_LH_BODY = LH_BODY
_LH_OPTION = LH_OPTION
_INDENT_OPT = INDENT_OPT
_GAP_AFTER_Q = GAP_AFTER_Q
_GAP_BEFORE_FIG = GAP_BEFORE_FIG
_GAP_AFTER_FIG = GAP_AFTER_FIG
_LH_CAPTION = LH_CAPTION
_MIN_FIG_SPACE_MM = MIN_FIG_SPACE_MM


def _latex_inner_to_printable(s: str) -> str:
    """把 $...$ 里的片段转成可楷体直排的近似写法；规则见 pdf_math_replacements。"""
    return latex_inner_to_printable(s)


def _normalize_malformed_latex_tokens(text: str) -> str:
    """题干/选项里常夹半拉 LaTeX（美元符不配对或 frac 在 $ 外），先整段修再展开 $...$。"""
    t = text
    t = re.sub(r"\^\{\\wedge\}\s*\\circ\b", "°", t)
    t = re.sub(r"\^\wedge\s*\\circ\b", "°", t)
    t = re.sub(r"\^\{\\wedge\}\s*circ\b", "°", t)
    t = re.sub(r"\^\wedge\s*circ\b", "°", t)
    t = re.sub(
        r"(?i)\bfrac\s*\$?\s*\\?sqrt\s*\{\s*\}\s*\$?\s*(\d)(\d)\b",
        r"√\1/\2",
        t,
    )
    t = re.sub(r"(?i)\bfrac\s+sqrt\s*\{\s*\}\s*(\d)(\d)\b", r"√\1/\2", t)
    return t


def _flatten_math_to_text(text: str) -> str:
    """将 $$...$$ 与 $...$ 全部展开为纯文本。"""

    def repl_block(m: re.Match[str]) -> str:
        return _latex_inner_to_printable(m.group(1))

    def repl_inline(m: re.Match[str]) -> str:
        return _latex_inner_to_printable(m.group(1))

    s = _normalize_malformed_latex_tokens(text)
    s = replace_extensible_arrows(s)
    s = replace_mhchem_ce_braces(s)
    s = re.sub(r"\$\$([^$]+)\$\$", repl_block, s, flags=re.DOTALL)
    s = re.sub(r"\$([^$]+)\$", repl_inline, s)
    return s


def _normalize_whitespace_lines(text: str) -> str:
    """合并多余空行，统一换行。"""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def _strip_one_option_label_prefix(raw: str, index: int) -> str:
    """去掉字符串开头的一层「A. / B. / 1. / (A)」类标记（单次）。"""
    t = raw.strip()
    letter = chr(65 + index) if index < 26 else None
    patterns: list[str] = []
    if letter:
        patterns.append(rf"^{re.escape(letter)}[.．、:：]\s*")
    patterns.extend(
        (
            r"^[A-Za-z][.．、:：]\s*",
            r"^\d+[.．、:：]\s*",
            r"^[（(][A-Za-z][)）]\s*",
        )
    )
    for pat in patterns:
        m = re.match(pat, t, re.IGNORECASE)
        if m:
            return t[m.end() :].strip()
    return t


def _strip_all_option_label_prefixes(raw: str, index: int) -> str:
    """模型可能写成「A. A. xxx」；只剥一层会得到「A. xxx」，印出来仍是「A. A.」。循环剥到剥不动。"""
    t = raw.strip()
    for _ in range(12):
        nxt = _strip_one_option_label_prefix(t, index)
        if nxt == t:
            break
        t = nxt
    return t


# 兼容旧测试名
def _strip_duplicate_option_label(raw: str, index: int) -> str:
    return _strip_one_option_label_prefix(raw, index)


_OPTION_LINE_BODY = re.compile(r"^\s*([A-Za-z]|\d+)[.．、:：]\s*(.+)$")


def _choice_line_body(line: str) -> str | None:
    m = _OPTION_LINE_BODY.match(line.strip())
    if not m:
        return None
    return m.group(2).strip()


def _normalize_choice_key(s: str) -> str:
    """比较题干末行与 options 是否同一组选项（忽略空白差异）。"""
    return re.sub(r"\s+", "", _flatten_math_to_text(s))


def _format_practice_option_line(j: int, opt: str) -> str:
    label = chr(65 + j) if j < 26 else str(j + 1)
    inner = _strip_all_option_label_prefixes(opt, j)
    line = _flatten_math_to_text(inner)
    if not line.strip():
        line = "（选项内容为空）"
    return f"{label}. {line}"


def _stem_strip_trailing_inline_options(stem: str, options: list[str]) -> str:
    """模型常把 A. B. C. D. 写在 stem 里，同时又填 options，PDF 会印两套。若末尾若干行与 options 一一对应则删掉。"""
    if not stem.strip() or not options:
        return stem
    lines = stem.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    k = len(options)
    if len(lines) < k:
        return stem
    tail = lines[-k:]
    tail_bodies: list[str] = []
    for ln in tail:
        body = _choice_line_body(ln)
        if body is None:
            return stem
        tail_bodies.append(body)
    opt_keys = [_normalize_choice_key(_strip_all_option_label_prefixes(options[j], j)) for j in range(k)]
    tail_keys = [_normalize_choice_key(b) for b in tail_bodies]
    if tail_keys == opt_keys:
        return "\n".join(lines[:-k]).rstrip()
    return stem


def _try_write_line_with_inline_math(
    pdf: RicePDF,
    line: str,
    w: float,
    font_size: int,
    line_height: float,
) -> bool:
    """含 $...$ 时尝试 mathtext 栅格内联；失败返回 False 由调用方走 Unicode 扁平化。"""
    parts = re.split(r"(\$[^$]+\$)", line)
    parts = [p for p in parts if p]
    if not parts or not any(p.startswith("$") for p in parts):
        return False

    pdf.set_font("KaiTi", "", font_size)
    y0 = pdf.get_y()
    x = pdf.l_margin
    x_max = pdf.w - pdf.r_margin

    for part in parts:
        if part.startswith("$") and part.endswith("$") and len(part) >= 3:
            inner = part[1:-1]
            png = mathtext_inner_to_png_bytes(inner, fontsize_pt=float(font_size))
            if not png:
                return False
            if x > pdf.l_margin and x + 8 > x_max:
                return False
            pdf.image(io.BytesIO(png), x=x, y=y0, h=line_height)
            x = pdf.get_x()
            continue
        frag = _flatten_math_to_text(part)
        if not frag:
            continue
        tw = pdf.get_string_width(frag)
        if x + tw > x_max + 1e-6 and x > pdf.l_margin:
            return False
        pdf.set_xy(x, y0)
        pdf.cell(tw, line_height, frag)
        x = pdf.get_x()

    pdf.set_y(y0 + line_height)
    return True


def _write_paragraphs(pdf: RicePDF, text: str, *, font_size: int, line_height: float) -> None:
    """按换行分段 multi_cell；可选 settings.practice_pdf_inline_mathtext 内联公式小图。"""
    pdf.set_font("KaiTi", "", font_size)
    pdf.set_text_color(30, 30, 30)
    w = pdf.epw
    placeholder = (
        "（本题题干缺少可显示文字，可能为题干为空或仅含无法展开的公式。请重新生成或编辑数据源。）"
    )

    if settings.practice_pdf_inline_mathtext:
        raw = _normalize_malformed_latex_tokens(text)
        norm = _normalize_whitespace_lines(raw)
        if not norm.strip():
            norm = placeholder
        for para in norm.split("\n"):
            if not para.strip():
                continue
            if "$" in para and _try_write_line_with_inline_math(
                pdf, para, w, font_size, line_height
            ):
                pdf.ln(1)
                continue
            flat = _flatten_math_to_text(para)
            if not (flat or "").strip():
                flat = "（…）"
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w, line_height, flat, align="L")
            pdf.ln(1)
        return

    body = _normalize_whitespace_lines(_flatten_math_to_text(text))
    if not body:
        body = placeholder
    for para in body.split("\n"):
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, line_height, para, align="L")
        pdf.ln(1)


class RicePDF(FPDF):
    def __init__(self, font_path: Path) -> None:
        super().__init__(format="A4")
        self.font_path = font_path
        self.set_margins(16, 20, 16)
        self.set_auto_page_break(auto=True, margin=22)
        self.add_font(family="KaiTi", fname=font_path.as_posix())

    def header(self) -> None:
        self.set_fill_color(*RICE)
        self.rect(0, 0, self.w, self.h, style="F")

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("KaiTi", "", 9)
        self.set_text_color(160, 160, 160)
        self.cell(0, 8, WATERMARK, align="R")


def _resolve_paper_image_path_for_embed(
    q: PracticeQuestion,
    order_index_to_paper_paths: dict[int, list[str]] | None,
) -> Path | None:
    if q.paper_image_ref and str(q.paper_image_ref).strip():
        p = resolve_under_data_dir(q.paper_image_ref)
        if p is not None and p.is_file():
            return p
    if (
        not q.use_paper_figure
        or q.source_question_order is None
        or not order_index_to_paper_paths
    ):
        return None
    for raw in order_index_to_paper_paths.get(q.source_question_order, []):
        p = resolve_under_data_dir(raw)
        if p is not None and p.is_file():
            return p
    return None


def _write_figure_caption_pdf(pdf: RicePDF, content_width: float, caption: str) -> None:
    cap = (caption or "").strip()
    if not cap:
        return
    pdf.set_font("KaiTi", "", 9)
    pdf.set_text_color(55, 55, 55)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(content_width, LH_CAPTION, cap, align="L")
    pdf.set_text_color(30, 30, 30)
    pdf.ln(1)


def _embed_svg_vector(
    pdf: RicePDF,
    content_width: float,
    svg_utf8: str,
    *,
    order_index: int,
) -> bool:
    try:
        pdf.ln(GAP_BEFORE_FIG)
        ensure_room_for_figure(pdf)
        pdf.image(io.BytesIO(svg_utf8.encode("utf-8")), x=pdf.l_margin, w=content_width)
        pdf.ln(GAP_AFTER_FIG)
        return True
    except Exception as e:
        logger.debug(
            "practice_pdf: svg vector embed failed (order_index=%s): %s",
            order_index,
            e,
            exc_info=True,
        )
        return False


def _embed_question_figure(
    pdf: RicePDF,
    content_width: float,
    q: PracticeQuestion,
    *,
    include_figures: bool = True,
    use_original_figures: bool = False,
    order_index_to_paper_paths: dict[int, list[str]] | None = None,
    figure_diagnostics: list[FigureEmbedRecord] | None = None,
) -> None:
    """题干与选项之间：优先嵌入原卷图，否则 matplotlib 示意图。"""
    from app.services.practice_figure_render import render_question_figure_with_diag

    def _emit(outcome: str, reason_code: str) -> None:
        log_figure_embed(
            logger,
            order_index=q.order_index,
            figure_kind=q.figure_kind,
            outcome=outcome,
            reason_code=reason_code,
        )
        append_figure_embed_record(
            figure_diagnostics,
            order_index=q.order_index,
            figure_kind=q.figure_kind,
            outcome=outcome,
            reason_code=reason_code,
        )

    if not include_figures:
        _emit("skipped_include_figures_false", "include_figures_false")
        return

    paper_ctx = ""
    if use_original_figures:
        p_path = _resolve_paper_image_path_for_embed(q, order_index_to_paper_paths)
        if p_path is not None:
            suf = p_path.suffix.lower()
            if suf in (".png", ".jpg", ".jpeg", ".gif"):
                try:
                    pdf.ln(GAP_BEFORE_FIG)
                    ensure_room_for_figure(pdf)
                    pdf.image(p_path.as_posix(), x=pdf.l_margin, w=content_width)
                    pdf.ln(GAP_AFTER_FIG)
                except Exception as e:
                    logger.debug(
                        "practice_pdf: paper image embed failed (order_index=%s)",
                        q.order_index,
                        exc_info=True,
                    )
                    paper_ctx = f"paper_raster_failed:{type(e).__name__}"
                else:
                    _emit("embedded_paper_raster", "ok")
                    return
            elif suf == ".svg":
                try:
                    raw = p_path.read_text(encoding="utf-8", errors="replace")
                    clean = sanitize_practice_svg(raw)
                    if clean is None:
                        paper_ctx = "paper_svg_sanitize_failed"
                    elif _embed_svg_vector(pdf, content_width, clean, order_index=q.order_index):
                        _emit("embedded_paper_svg", "ok")
                        return
                    else:
                        paper_ctx = "paper_svg_embed_failed"
                except Exception as e:
                    logger.debug(
                        "practice_pdf: paper svg read/embed (order_index=%s)",
                        q.order_index,
                        exc_info=True,
                    )
                    paper_ctx = f"paper_svg_io:{type(e).__name__}"
            else:
                paper_ctx = f"unsupported_paper_suffix:{suf}"
        else:
            paper_ctx = "paper_path_unresolved"

    if q.figure_kind == "none" or q.figure_spec is None:
        _emit("skipped_no_figure", paper_ctx or "no_figure_spec")
        return

    if q.figure_kind == "svg" and isinstance(q.figure_spec, PracticeSvgSpec):
        clean = sanitize_practice_svg(q.figure_spec.svg)
        if clean is None:
            _emit("inline_svg_sanitize_failed", paper_ctx or "sanitize_none")
            return
        if _embed_svg_vector(pdf, content_width, clean, order_index=q.order_index):
            _write_figure_caption_pdf(pdf, content_width, q.figure_spec.caption)
            _emit("embedded_inline_svg", paper_ctx or "ok")
            return
        _emit("svg_embed_failed", paper_ctx or "fpdf_svg_failed")
        return

    png, rcode = render_question_figure_with_diag(q)
    if not png:
        reason = rcode if not paper_ctx else f"{rcode}|{paper_ctx}"
        _emit("render_failed", reason)
        return

    pdf.ln(GAP_BEFORE_FIG)
    ensure_room_for_figure(pdf)

    pdf.image(io.BytesIO(png), x=pdf.l_margin, w=content_width)
    pdf.ln(GAP_AFTER_FIG)

    _write_figure_caption_pdf(pdf, content_width, q.figure_spec.caption)
    _emit("embedded_rendered_png", paper_ctx or "ok")


def render_practice_pdf(
    practice: PracticeSet,
    out_path: Path,
    *,
    title: str,
    include_answers: bool = False,
    include_figures: bool = True,
    use_original_figures: bool = False,
    order_index_to_paper_paths: dict[int, list[str]] | None = None,
    collect_figure_diagnostics: list[FigureEmbedRecord] | None = None,
) -> None:
    font_path = resolve_kaiti_font()
    pdf = RicePDF(font_path)
    pdf.add_page()
    w = pdf.epw
    layout_document_title(pdf, w, title)

    for q in practice.questions:
        layout_question_heading(pdf, w, q.order_index, q.qtype)
        pdf.set_text_color(30, 30, 30)
        stem_pdf = q.stem
        if q.options and q.qtype in ("单选", "多选"):
            stem_pdf = _stem_strip_trailing_inline_options(stem_pdf, q.options)
        _write_paragraphs(pdf, stem_pdf, font_size=11, line_height=LH_BODY)

        _embed_question_figure(
            pdf,
            w,
            q,
            include_figures=include_figures,
            use_original_figures=use_original_figures,
            order_index_to_paper_paths=order_index_to_paper_paths,
            figure_diagnostics=collect_figure_diagnostics,
        )

        if q.options:
            layout_options_block(
                pdf, w, q.options, format_option_line=_format_practice_option_line
            )

        spacing_after_question_block(pdf)

        if include_answers and q.answer_outline:
            layout_answer_section_heading(pdf, w)
            _write_paragraphs(pdf, q.answer_outline, font_size=10, line_height=LH_OPTION)
            pdf.set_text_color(30, 30, 30)
            pdf.set_font("KaiTi", "", 11)
            pdf.ln(2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(out_path.as_posix())


def render_answer_pdf(
    practice: PracticeSet,
    out_path: Path,
    *,
    title: str,
    include_figures: bool = True,
    use_original_figures: bool = False,
    order_index_to_paper_paths: dict[int, list[str]] | None = None,
    collect_figure_diagnostics: list[FigureEmbedRecord] | None = None,
) -> None:
    font_path = resolve_kaiti_font()
    pdf = RicePDF(font_path)
    pdf.add_page()
    w = pdf.epw
    layout_document_title(pdf, w, title, title_suffix=" — 参考答案")

    for q in practice.questions:
        layout_question_heading(pdf, w, q.order_index, q.qtype)
        _embed_question_figure(
            pdf,
            w,
            q,
            include_figures=include_figures,
            use_original_figures=use_original_figures,
            order_index_to_paper_paths=order_index_to_paper_paths,
            figure_diagnostics=collect_figure_diagnostics,
        )
        pdf.set_font("KaiTi", "", 10.5)
        pdf.set_text_color(0, 85, 45)
        _write_paragraphs(pdf, q.answer_outline or "（略）", font_size=10.5, line_height=LH_OPTION)
        pdf.set_text_color(30, 30, 30)
        spacing_after_question_block(pdf)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(out_path.as_posix())

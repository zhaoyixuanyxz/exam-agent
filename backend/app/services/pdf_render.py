"""练习 PDF：米白底、楷体、水印；题干/解析以文字直排为主，避免碎片公式图破坏版式。"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from fpdf import FPDF

from app.models.schemas import PracticeQuestion, PracticeSet, PracticeSvgSpec
from app.services.fonts import resolve_kaiti_font
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

# 中文试卷阅读：行距略大、选项缩进
_LH_TITLE = 11
_LH_BODY = 8.2
_LH_OPTION = 7.8
_INDENT_OPT = 6.0
_GAP_AFTER_Q = 5.0
# 题干与选项之间可选插图（不改变题干/选项所用行高）
_GAP_BEFORE_FIG = 3.0
_GAP_AFTER_FIG = 2.0
_LH_CAPTION = 7.0
_MIN_FIG_SPACE_MM = 78.0


def _latex_inner_to_printable(s: str) -> str:
    """把 $...$ 里的片段转成可楷体直排的近似写法（不再整段插图）。"""
    t = s.strip()
    # 模型常把角度写成 ^{\wedge}\circ 或 ^\wedge\circ，先规整为一度符号
    t = re.sub(r"\^\{\\wedge\}\s*\\circ\b", "°", t)
    t = re.sub(r"\^\wedge\s*\\circ\b", "°", t)
    t = re.sub(r"\^\{\\wedge\}\s*circ\b", "°", t)
    t = re.sub(r"\^\wedge\s*circ\b", "°", t)
    # 选项里烂掉的 \frac{\sqrt{a}}{b}：变成「frac √{} 22」一类
    t = re.sub(
        r"(?i)frac\s*\$?\s*\\?sqrt\s*\{\s*\}\s*\$?\s*(\d)(\d)\b",
        r"√\1/\2",
        t,
    )
    t = re.sub(r"(?i)\bfrac\s+sqrt\s*\{\s*\}\s*(\d)(\d)\b", r"√\1/\2", t)
    # 常见几何 / 运算（顺序：先长后短，避免误替换）
    repl = (
        (r"\\triangle", "△"),
        (r"\\angle", "∠"),
        (r"\\odot", "⊙"),
        (r"\\perp", "⊥"),
        (r"\\parallel", "∥"),
        (r"\\rightarrow", "→"),
        (r"\\Rightarrow", "⇒"),
        (r"\\leq", "≤"),
        (r"\\geq", "≥"),
        (r"\\neq", "≠"),
        (r"\\approx", "≈"),
        (r"\\cong", "≅"),
        (r"\\simeq", "≃"),
        (r"\\infty", "∞"),
        (r"\\cdot", "·"),
        (r"\\times", "×"),
        (r"\\div", "÷"),
        (r"\\pm", "±"),
        (r"\\pi", "π"),
        (r"\\alpha", "α"),
        (r"\\beta", "β"),
        (r"\\gamma", "γ"),
        (r"\\theta", "θ"),
        (r"\\Delta", "Δ"),
        (r"\\circ", "°"),
        (r"\\degree", "°"),
        (r"\\widehat", "⌢"),
        (r"\\overline", "—"),
        (r"\\sqrt", "√"),
        (r"\\sum", "∑"),
    )
    for pat, ch in repl:
        t = re.sub(pat, ch, t)
    # ^{circ} / ^\circ（LaTeX 里是反斜杠，正则须写成 \\circ）
    t = re.sub(r"\^\{\\circ\}", "°", t)
    t = re.sub(r"\^\\circ", "°", t)
    # 简单分式、根号（一层花括号）
    t = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", t)
    t = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", t)
    t = re.sub(r"\\text\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\left|\\right|\\,|\\;|\\:|\\!", " ", t)
    # 剩余 \word 去掉反斜杠前缀，避免满屏 "triangle"
    t = re.sub(r"\\([a-zA-Z]+)", lambda m: m.group(1), t)
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else " "


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


def _write_paragraphs(pdf: RicePDF, text: str, *, font_size: int, line_height: float) -> None:
    """按换行分段 multi_cell，整段可读。"""
    pdf.set_font("KaiTi", "", font_size)
    pdf.set_text_color(30, 30, 30)
    w = pdf.epw
    body = _normalize_whitespace_lines(_flatten_math_to_text(text))
    if not body:
        body = "（本题题干缺少可显示文字，可能为题干为空或仅含无法展开的公式。请重新生成或编辑数据源。）"
    # fpdf2 multi_cell 默认为两端对齐 J，中英混排时会把一行拉得很散；左对齐与日常试卷观感一致。
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
    pdf.multi_cell(content_width, _LH_CAPTION, cap, align="L")
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
        pdf.ln(_GAP_BEFORE_FIG)
        if pdf.get_y() + _MIN_FIG_SPACE_MM > pdf.h - pdf.b_margin:
            pdf.add_page()
        pdf.image(io.BytesIO(svg_utf8.encode("utf-8")), x=pdf.l_margin, w=content_width)
        pdf.ln(_GAP_AFTER_FIG)
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
                    pdf.ln(_GAP_BEFORE_FIG)
                    if pdf.get_y() + _MIN_FIG_SPACE_MM > pdf.h - pdf.b_margin:
                        pdf.add_page()
                    pdf.image(p_path.as_posix(), x=pdf.l_margin, w=content_width)
                    pdf.ln(_GAP_AFTER_FIG)
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

    pdf.ln(_GAP_BEFORE_FIG)
    if pdf.get_y() + _MIN_FIG_SPACE_MM > pdf.h - pdf.b_margin:
        pdf.add_page()

    pdf.image(io.BytesIO(png), x=pdf.l_margin, w=content_width)
    pdf.ln(_GAP_AFTER_FIG)

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
    pdf.set_font("KaiTi", "", 15)
    pdf.set_text_color(35, 35, 35)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w, _LH_TITLE, title, align="L")
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.2)
    pdf.line(pdf.l_margin, pdf.get_y() + 1.5, pdf.w - pdf.r_margin, pdf.get_y() + 1.5)
    pdf.ln(5)

    for q in practice.questions:
        pdf.set_font("KaiTi", "", 11)
        pdf.set_text_color(20, 60, 120)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, _LH_BODY, f"第 {q.order_index} 题　【{q.qtype}】", align="L")
        pdf.ln(1)
        pdf.set_text_color(30, 30, 30)
        stem_pdf = q.stem
        if q.options and q.qtype in ("单选", "多选"):
            stem_pdf = _stem_strip_trailing_inline_options(stem_pdf, q.options)
        _write_paragraphs(pdf, stem_pdf, font_size=11, line_height=_LH_BODY)

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
            pdf.ln(1)
            pdf.set_font("KaiTi", "", 10.5)
            pdf.set_text_color(45, 45, 45)
            for j, opt in enumerate(q.options):
                label = chr(65 + j) if j < 26 else str(j + 1)
                inner = _strip_all_option_label_prefixes(opt, j)
                line = _flatten_math_to_text(inner)
                if not line.strip():
                    line = "（选项内容为空）"
                pdf.set_x(pdf.l_margin + _INDENT_OPT)
                pdf.multi_cell(w - _INDENT_OPT, _LH_OPTION, f"{label}. {line}", align="L")
            pdf.set_text_color(30, 30, 30)

        pdf.ln(_GAP_AFTER_Q)

        if include_answers and q.answer_outline:
            pdf.set_font("KaiTi", "", 10)
            pdf.set_text_color(0, 95, 55)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(w, _LH_OPTION, "【参考答案】", align="L")
            pdf.ln(0.5)
            _write_paragraphs(pdf, q.answer_outline, font_size=10, line_height=_LH_OPTION)
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
    pdf.set_font("KaiTi", "", 15)
    pdf.set_text_color(35, 35, 35)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(w, _LH_TITLE, title + " — 参考答案", align="L")
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, pdf.get_y() + 1.5, pdf.w - pdf.r_margin, pdf.get_y() + 1.5)
    pdf.ln(5)

    for q in practice.questions:
        pdf.set_font("KaiTi", "", 11)
        pdf.set_text_color(20, 60, 120)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(w, _LH_BODY, f"第 {q.order_index} 题　【{q.qtype}】", align="L")
        pdf.ln(1)
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
        _write_paragraphs(pdf, q.answer_outline or "（略）", font_size=10.5, line_height=_LH_OPTION)
        pdf.set_text_color(30, 30, 30)
        pdf.ln(_GAP_AFTER_Q)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(out_path.as_posix())

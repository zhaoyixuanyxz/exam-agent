"""练习 PDF：米白底、楷体、水印；题干/解析以文字直排为主，避免碎片公式图破坏版式。"""

from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

from app.models.schemas import PracticeSet
from app.services.fonts import resolve_kaiti_font

RICE = (250, 248, 245)
WATERMARK = "朱老师私密资料，仅供参考！！"

# 中文试卷阅读：行距略大、选项缩进
_LH_TITLE = 11
_LH_BODY = 8.2
_LH_OPTION = 7.8
_INDENT_OPT = 6.0
_GAP_AFTER_Q = 5.0


def _latex_inner_to_printable(s: str) -> str:
    """把 $...$ 里的片段转成可楷体直排的近似写法（不再整段插图）。"""
    t = s.strip()
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


def _flatten_math_to_text(text: str) -> str:
    """将 $$...$$ 与 $...$ 全部展开为纯文本。"""

    def repl_block(m: re.Match[str]) -> str:
        return _latex_inner_to_printable(m.group(1))

    def repl_inline(m: re.Match[str]) -> str:
        return _latex_inner_to_printable(m.group(1))

    s = re.sub(r"\$\$([^$]+)\$\$", repl_block, text, flags=re.DOTALL)
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


def render_practice_pdf(
    practice: PracticeSet,
    out_path: Path,
    *,
    title: str,
    include_answers: bool = False,
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


def render_answer_pdf(practice: PracticeSet, out_path: Path, *, title: str) -> None:
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
        pdf.set_font("KaiTi", "", 10.5)
        pdf.set_text_color(0, 85, 45)
        _write_paragraphs(pdf, q.answer_outline or "（略）", font_size=10.5, line_height=_LH_OPTION)
        pdf.set_text_color(30, 30, 30)
        pdf.ln(_GAP_AFTER_Q)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(out_path.as_posix())

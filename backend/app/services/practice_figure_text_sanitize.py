"""配图内说明文字：去掉模型输出的 LaTeX/mhchem 残留，转成 matplotlib 普通文本可读的 Unicode。"""

from __future__ import annotations

import re

from app.services.pdf_math_replacements import latex_inner_to_printable, replace_extensible_arrows

# 数字下标（化学式 H2SO4 → H₂SO₄）
_DIGIT_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _formula_inner_to_unicode(inner: str) -> str:
    s = (inner or "").strip()
    if not s:
        return s
    return "".join(c.translate(_DIGIT_SUB) if c.isdigit() else c for c in s)


def _expand_underscore_subscripts(s: str) -> str:
    """HNO_3 → HNO₃（仅处理 _数字）。"""
    t = (s or "").strip()
    if not t:
        return t

    def repl(m: re.Match[str]) -> str:
        return "".join(chr(0x2080 + int(d)) for d in m.group(1))

    return re.sub(r"_(\d+)", repl, t)


def figure_matplotlib_plain_text(s: str) -> str:
    """
    将电解液说明、电极标注等中的 $\\ce{H2SO4}$、\\ce{...}、多余 $ 等转为直排可读文本。
    matplotlib 默认不用 mhchem，不能直接渲染 \\ce。
    """
    t = (s or "").strip()
    if not t:
        return t

    # JSON / 模型常多重转义 \\ce → \ce
    while "\\\\" in t:
        t = t.replace("\\\\", "\\")

    t = replace_extensible_arrows(t)

    def repl_ce(m: re.Match[str]) -> str:
        return _formula_inner_to_unicode(m.group(1))

    # $\ce{...}$、$ \ce { ... } $、\ce{...}
    t = re.sub(
        r"(?i)\$?\s*\\ce\s*\{\s*([^}]*?)\s*\}\s*\$?",
        repl_ce,
        t,
    )

    t = re.sub(
        r"(?i)\$?\\mathrm\s*\{([^}]*)\}\$?",
        lambda m: _expand_underscore_subscripts(m.group(1)),
        t,
    )
    t = re.sub(r"(?i)\$?\\text\s*\{([^}]*)\}\$?", r"\1", t)
    t = re.sub(r"(?i)\$?\\mathit\s*\{([^}]*)\}\$?", r"\1", t)

    # 剩余成对 $...$：走与 PDF 一致的符号替换（不含花括号剥离的复杂 LaTeX）
    def repl_inline(m: re.Match[str]) -> str:
        return latex_inner_to_printable(m.group(1))

    t = re.sub(r"\$([^$]+)\$", repl_inline, t)
    t = t.replace("$", "")
    t = re.sub(r"\\([a-zA-Z]{2,})", "", t)
    t = re.sub(r"\{|\}", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

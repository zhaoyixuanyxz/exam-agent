"""LaTeX 内层（$...$ / $$...$$）到可打印 Unicode 的有序替换表；新增符号只改此处。"""

from __future__ import annotations

import re

# 化学式 \ce{...} 内数字 → 下标（与配图逻辑一致）
_CE_DIGIT_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")

# 顺序敏感：长命令必须排在短命令前，避免 \subset 吃掉 \subseteq 等前缀。
ORDERED_LATEX_SYMBOL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    # —— 化学 / 反应 ——
    (r"\\rightleftharpoons", "⇌"),
    (r"\\leftrightharpoons", "⇌"),
    (r"\\Longrightarrow", "⟹"),
    (r"\\Longleftarrow", "⟸"),
    (r"\\Longleftrightarrow", "⇔"),
    (r"\\longleftrightarrow", "↔"),
    (r"\\longrightarrow", "→"),
    (r"\\longleftarrow", "←"),
    (r"\\longmapsto", "↦"),
    (r"\\Leftrightarrow", "⇔"),
    (r"\\leftrightarrow", "↔"),
    (r"\\Rightarrow", "⇒"),
    (r"\\Leftarrow", "⇐"),
    (r"\\rightarrow", "→"),
    (r"\\leftarrow", "←"),
    (r"\\mapsto", "↦"),
    (r"\\implies", "⟹"),
    (r"\\iff", "⇔"),
    (r"\\downarrow", "↓"),
    (r"\\Downarrow", "⇓"),
    (r"\\uparrow", "↑"),
    (r"\\Uparrow", "⇑"),
    (r"\\nearrow", "↗"),
    (r"\\searrow", "↘"),
    (r"\\nwarrow", "↖"),
    (r"\\swarrow", "↙"),
    (r"\\to\b", "→"),
    (r"\\gets\b", "←"),
    (r"\\geqslant", "≥"),
    (r"\\leqslant", "≤"),
    (r"\\geq", "≥"),
    (r"\\leq", "≤"),
    (r"\\ge\b", "≥"),
    (r"\\le\b", "≤"),
    (r"\\neq", "≠"),
    (r"\\ne\b", "≠"),
    (r"\\approx", "≈"),
    (r"\\approxeq", "≊"),
    (r"\\cong", "≅"),
    (r"\\simeq", "≃"),
    (r"\\backsimeq", "⋍"),
    (r"\\sim\b", "∼"),
    (r"\\propto", "∝"),
    (r"\\equiv", "≡"),
    (r"\\doteq", "≐"),
    (r"\\triangle", "△"),
    (r"\\angle", "∠"),
    (r"\\odot", "⊙"),
    (r"\\perp", "⊥"),
    (r"\\parallel", "∥"),
    (r"\\infty", "∞"),
    (r"\\cdot", "·"),
    (r"\\times", "×"),
    (r"\\div", "÷"),
    (r"\\pm", "±"),
    (r"\\mp", "∓"),
    (r"\\oplus", "⊕"),
    (r"\\ominus", "⊖"),
    (r"\\otimes", "⊗"),
    # —— 集合 / 逻辑 ——（subseteq 等先于 subset）
    (r"\\subsetneq", "⊊"),
    (r"\\supsetneq", "⊋"),
    (r"\\subseteq", "⊆"),
    (r"\\supseteq", "⊇"),
    (r"\\subsetneqq", "⫋"),
    (r"\\supsetneqq", "⫌"),
    (r"\\subset", "⊂"),
    (r"\\supset", "⊃"),
    (r"\\in\b", "∈"),
    (r"\\notin", "∉"),
    (r"\\ni\b", "∋"),
    (r"\\cup\b", "∪"),
    (r"\\cap\b", "∩"),
    (r"\\setminus", "∖"),
    (r"\\bigcup", "⋃"),
    (r"\\bigcap", "⋂"),
    (r"\\varnothing", "∅"),
    (r"\\emptyset", "∅"),
    (r"\\forall", "∀"),
    (r"\\exists", "∃"),
    (r"\\nexists", "∄"),
    (r"\\land\b", "∧"),
    (r"\\lor\b", "∨"),
    (r"\\lnot\b", "¬"),
    (r"\\neg\b", "¬"),
    (r"\\therefore", "∴"),
    (r"\\because", "∵"),
    # —— 微积分 / 物理 / 通用 ——
    (r"\\partial", "∂"),
    (r"\\nabla", "∇"),
    (r"\\hbar", "ℏ"),
    (r"\\ell", "ℓ"),
    (r"\\prime", "′"),
    (r"\\degree", "°"),
    (r"\\circ", "°"),
    (r"\\cdots", "⋯"),
    (r"\\ldots", "…"),
    (r"\\dots\b", "…"),
    (r"\\vdots", "⋮"),
    (r"\\ddots", "⋱"),
    (r"\\int\b", "∫"),
    (r"\\oint", "∮"),
    (r"\\iint", "∬"),
    (r"\\iiint", "∭"),
    (r"\\sum\b", "∑"),
    (r"\\prod\b", "∏"),
    (r"\\coprod", "∐"),
    (r"\\sqrt", "√"),
    (r"\\widehat", "⌢"),
    (r"\\overline", "—"),
    (r"\\underline", "＿"),
    # —— 初等函数名（避免剥成奇怪的英文命令碎片）——
    (r"\\lim\b", "lim"),
    (r"\\sin\b", "sin"),
    (r"\\cos\b", "cos"),
    (r"\\tan\b", "tan"),
    (r"\\cot\b", "cot"),
    (r"\\sec\b", "sec"),
    (r"\\csc\b", "csc"),
    (r"\\arcsin\b", "arcsin"),
    (r"\\arccos\b", "arccos"),
    (r"\\arctan\b", "arctan"),
    (r"\\ln\b", "ln"),
    (r"\\log\b", "log"),
    (r"\\exp\b", "exp"),
    (r"\\sinh\b", "sinh"),
    (r"\\cosh\b", "cosh"),
    (r"\\tanh\b", "tanh"),
    (r"\\max\b", "max"),
    (r"\\min\b", "min"),
    (r"\\sup\b", "sup"),
    (r"\\inf\b", "inf"),
    (r"\\det\b", "det"),
    (r"\\dim\b", "dim"),
    (r"\\ker\b", "ker"),
    (r"\\deg\b", "deg"),
    (r"\\hom\b", "hom"),
    (r"\\arg\b", "arg"),
    # —— 希腊字母（大写先于小写可避免部分前缀问题）——
    (r"\\Gamma", "Γ"),
    (r"\\Delta", "Δ"),
    (r"\\Theta", "Θ"),
    (r"\\Lambda", "Λ"),
    (r"\\Xi", "Ξ"),
    (r"\\Pi", "Π"),
    (r"\\Sigma", "Σ"),
    (r"\\Phi", "Φ"),
    (r"\\Psi", "Ψ"),
    (r"\\Omega", "Ω"),
    (r"\\alpha", "α"),
    (r"\\beta", "β"),
    (r"\\gamma", "γ"),
    (r"\\delta", "δ"),
    (r"\\epsilon", "ε"),
    (r"\\varepsilon", "ε"),
    (r"\\zeta", "ζ"),
    (r"\\eta", "η"),
    (r"\\theta", "θ"),
    (r"\\vartheta", "ϑ"),
    (r"\\iota", "ι"),
    (r"\\kappa", "κ"),
    (r"\\lambda", "λ"),
    (r"\\mu", "μ"),
    (r"\\nu", "ν"),
    (r"\\xi", "ξ"),
    (r"\\pi", "π"),
    (r"\\varpi", "ϖ"),
    (r"\\rho", "ρ"),
    (r"\\varrho", "ϱ"),
    (r"\\sigma", "σ"),
    (r"\\varsigma", "ς"),
    (r"\\tau", "τ"),
    (r"\\upsilon", "υ"),
    (r"\\phi", "φ"),
    (r"\\varphi", "φ"),
    (r"\\chi", "χ"),
    (r"\\psi", "ψ"),
    (r"\\omega", "ω"),
)

_MATHBB_PLANE: dict[str, str] = {
    "R": "ℝ",
    "N": "ℕ",
    "Z": "ℤ",
    "Q": "ℚ",
    "C": "ℂ",
    "P": "ℙ",
    "H": "ℍ",
}


def _ce_inner_to_unicode(inner: str) -> str:
    s = (inner or "").strip()
    if not s:
        return s
    return "".join(c.translate(_CE_DIGIT_SUB) if c.isdigit() else c for c in s)


def replace_mhchem_ce_braces(text: str) -> str:
    """
    mhchem \\ce{H2O}、$\\ce{H2O}$：数字转下标；先整段替换，避免漏网。
    """
    t = text

    def repl(m: re.Match[str]) -> str:
        return _ce_inner_to_unicode(m.group(1) or "")

    t = re.sub(r"(?i)\$\\ce\s*\{\s*([^}]*?)\s*\}\$", repl, t)
    t = re.sub(r"(?i)\\ce\s*\{\s*([^}]*?)\s*\}", repl, t)
    return t


def _clean_xarrow_label(inner: str) -> str:
    """箭头上的说明里常见一层 \\mathrm{}/\\text{}，避免嵌套花括号截断后残留 LaTeX。"""
    u = (inner or "").strip()
    u = re.sub(r"(?i)\\mathrm\s*\{([^{}]*)\}", r"\1", u)
    u = re.sub(r"(?i)\\text\s*\{([^{}]*)\}", r"\1", u)
    u = re.sub(r"(?i)\\mathit\s*\{([^{}]*)\}", r"\1", u)
    return u.strip()


def replace_extensible_arrows(text: str) -> str:
    """
    amsmath 可伸长箭头、\\overrightarrow 等：直排 PDF 无法解析时勿剥成英文命令名。
    """
    t = text
    while "\\\\x" in t:
        t = t.replace("\\\\x", "\\x")

    xpat = r"(?:\s*\[[^\]]*\])?\s*\{((?:[^{}]|\{[^{}]*\})*)\}"

    def repl_right(m: re.Match[str]) -> str:
        inner = _clean_xarrow_label(m.group(1) or "")
        return f"→（{inner}）" if inner else "→"

    def repl_left(m: re.Match[str]) -> str:
        inner = _clean_xarrow_label(m.group(1) or "")
        return f"←（{inner}）" if inner else "←"

    def repl_leftright(m: re.Match[str]) -> str:
        inner = _clean_xarrow_label(m.group(1) or "")
        return f"↔（{inner}）" if inner else "↔"

    def repl_mapsto(m: re.Match[str]) -> str:
        inner = _clean_xarrow_label(m.group(1) or "")
        return f"↦（{inner}）" if inner else "↦"

    t = re.sub(r"(?i)\\xlongrightarrow" + xpat, repl_right, t)
    t = re.sub(r"(?i)\\xrightarrow" + xpat, repl_right, t)
    t = re.sub(r"(?i)\\xlongleftarrow" + xpat, repl_left, t)
    t = re.sub(r"(?i)\\xleftarrow" + xpat, repl_left, t)
    t = re.sub(r"(?i)\\xleftrightarrow" + xpat, repl_leftright, t)
    t = re.sub(r"(?i)\\xLeftrightarrow" + xpat, repl_leftright, t)
    t = re.sub(r"(?i)\\xmapsto" + xpat, repl_mapsto, t)
    t = re.sub(r"(?i)\\xlongmapsto" + xpat, repl_mapsto, t)
    t = re.sub(r"(?i)\\overrightarrow" + xpat, repl_right, t)
    t = re.sub(r"(?i)\\overleftarrow" + xpat, repl_left, t)
    t = re.sub(r"(?i)\\underrightarrow" + xpat, repl_right, t)
    t = re.sub(r"(?i)\\underleftarrow" + xpat, repl_left, t)
    return t


def _unwrap_common_math_wrappers(t: str) -> str:
    """一层花括号型记号：去掉命令壳，保留内容。"""
    s = t
    s = re.sub(r"(?i)\\mathbb\s*\{\s*([A-Za-z])\s*\}", lambda m: _MATHBB_PLANE.get(m.group(1), m.group(1)), s)
    s = re.sub(r"(?i)\\mathcal\s*\{\s*([A-Za-z])\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\mathfrak\s*\{\s*([A-Za-z])\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\mathsf\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\mathbf\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\textbf\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\textit\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\vec\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\hat\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\bar\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\tilde\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\dot\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\ddot\s*\{\s*([^}]*)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\mathrm\s*\{\s*([^}]*?)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\text\s*\{\s*([^}]*?)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\mathit\s*\{\s*([^}]*?)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\textrm\s*\{\s*([^}]*?)\s*\}", r"\1", s)
    s = re.sub(r"(?i)\\textit\s*\{\s*([^}]*?)\s*\}", r"\1", s)
    return s


def latex_inner_to_printable(s: str) -> str:
    """把 $...$ 里的片段转成可楷体直排的近似写法。"""
    t = s.strip()
    t = replace_extensible_arrows(t)
    t = replace_mhchem_ce_braces(t)
    t = re.sub(r"\^\{\\wedge\}\s*\\circ\b", "°", t)
    t = re.sub(r"\^\wedge\s*\\circ\b", "°", t)
    t = re.sub(r"\^\{\\wedge\}\s*circ\b", "°", t)
    t = re.sub(r"\^\wedge\s*circ\b", "°", t)
    t = re.sub(
        r"(?i)frac\s*\$?\s*\\?sqrt\s*\{\s*\}\s*\$?\s*(\d)(\d)\b",
        r"√\1/\2",
        t,
    )
    t = re.sub(r"(?i)\bfrac\s+sqrt\s*\{\s*\}\s*(\d)(\d)\b", r"√\1/\2", t)
    for pat, ch in ORDERED_LATEX_SYMBOL_REPLACEMENTS:
        t = re.sub(pat, ch, t)
    t = re.sub(r"\^\{\\circ\}", "°", t)
    t = re.sub(r"\^\\circ", "°", t)
    t = re.sub(
        r"\\(?:dfrac|tfrac|frac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}",
        r"(\1)/(\2)",
        t,
    )
    t = re.sub(r"\\binom\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"C(\1,\2)", t)
    t = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"√(\1)", t)
    t = _unwrap_common_math_wrappers(t)
    t = re.sub(r"\\left|\\right|\\,|\\;|\\:|\\!", " ", t)
    # 未知命令：删除整段，避免「xrightarrow」类英文漏出；已知符号已全部替换或已展开。
    t = re.sub(r"\\([a-zA-Z]+)", "", t)
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else " "

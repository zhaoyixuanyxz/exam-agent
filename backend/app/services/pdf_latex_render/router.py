"""是否对当前公式内层尝试 LaTeX 子系统（保守启发式，可调配置）。"""

from __future__ import annotations

from app.config import settings


def _max_brace_depth(s: str) -> int:
    d = 0
    m = 0
    for c in s:
        if c == "{":
            d += 1
            m = max(m, d)
        elif c == "}" and d > 0:
            d -= 1
    return m


def should_render_with_latex(inner: str, *, display_block: bool = False) -> bool:
    """
    True：建议走 KaTeX/TeX 栅格；False：走 Unicode 扁平化或仅 mathtext。
    display_block：来自 $$...$$ 时 True，降低长度门槛。
    """
    t = (inner or "").strip()
    if not t:
        return False
    if len(t) > int(settings.practice_pdf_latex_max_inner_chars):
        return False
    if display_block:
        return True
    if r"\begin{" in t:
        return True
    if "&" in t and ("\\" in t or "\\\\" in t):
        return True
    if "\\\\" in t:
        return True
    if "\n" in t and "\\" in t:
        return True
    lim = int(settings.practice_pdf_latex_router_min_inner_len)
    if lim > 0 and len(t) >= lim:
        return True
    depth_cap = int(settings.practice_pdf_latex_router_max_brace_depth)
    if depth_cap > 0 and _max_brace_depth(t) >= depth_cap:
        return True
    return False

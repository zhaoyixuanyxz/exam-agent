"""练习 PDF：可选 LaTeX 公式栅格（KaTeX / TeX），与 Unicode 扁平化并存。"""

from __future__ import annotations

from .render import (
    FORMULA_CACHE_VERSION,
    FormulaRenderResult,
    render_formula_to_png,
    render_formula_to_png_result,
)
from .router import should_render_with_latex

__all__ = [
    "FORMULA_CACHE_VERSION",
    "FormulaRenderResult",
    "render_formula_to_png",
    "render_formula_to_png_result",
    "should_render_with_latex",
]

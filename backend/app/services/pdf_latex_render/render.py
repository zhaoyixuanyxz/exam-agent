"""LaTeX 公式子系统入口：缓存 + katex/tex + 结果元数据。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.config import settings

from .cache import cache_key, cache_png_path, read_png_if_exists, write_png_atomic
from .katex_playwright import render_katex_to_png_bytes
from .tex_render import render_tex_to_png_bytes

logger = logging.getLogger(__name__)

FORMULA_CACHE_VERSION = "v1"


@dataclass(frozen=True)
class FormulaRenderResult:
    png: bytes | None
    cache_hit: bool
    reason_code: str
    duration_ms: float | None
    renderer_used: str


def render_formula_to_png_result(
    inner: str,
    *,
    display_mode: bool = False,
) -> FormulaRenderResult:
    """
    按 settings.practice_pdf_latex_renderer 尝试栅格化；off 时立即返回。
    """
    renderer = (settings.practice_pdf_latex_renderer or "off").lower()
    if renderer not in ("katex", "tex"):
        return FormulaRenderResult(
            png=None,
            cache_hit=False,
            reason_code="renderer_off",
            duration_ms=None,
            renderer_used="off",
        )

    raw = (inner or "").strip()
    if not raw:
        return FormulaRenderResult(
            png=None,
            cache_hit=False,
            reason_code="empty_inner",
            duration_ms=None,
            renderer_used=renderer,
        )
    if len(raw) > int(settings.practice_pdf_latex_max_inner_chars):
        return FormulaRenderResult(
            png=None,
            cache_hit=False,
            reason_code="inner_too_long",
            duration_ms=None,
            renderer_used=renderer,
        )

    dpi = int(settings.practice_pdf_latex_dpi)
    key = cache_key(
        version=FORMULA_CACHE_VERSION,
        renderer=renderer,
        dpi=dpi,
        inner=raw,
        display_mode=display_mode,
    )
    cpath = cache_png_path(settings.practice_pdf_latex_cache_path, key)
    cached = read_png_if_exists(cpath)
    if cached is not None:
        return FormulaRenderResult(
            png=cached,
            cache_hit=True,
            reason_code="cache_hit",
            duration_ms=0.0,
            renderer_used=renderer,
        )

    timeout = float(settings.practice_pdf_latex_timeout_sec)
    t0 = time.perf_counter()
    png: bytes | None = None
    reason = "ok"
    if renderer == "katex":
        png = render_katex_to_png_bytes(raw, display_mode=display_mode, timeout_sec=timeout)
        if png is None:
            reason = "katex_failed"
    elif renderer == "tex":
        png = render_tex_to_png_bytes(raw, display_mode=display_mode, timeout_sec=timeout, dpi=dpi)
        if png is None:
            reason = "tex_failed"

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if png is not None:
        try:
            write_png_atomic(cpath, png)
        except OSError as e:
            logger.debug("pdf_latex_render: cache write failed: %s", e)

    return FormulaRenderResult(
        png=png,
        cache_hit=False,
        reason_code=reason,
        duration_ms=round(elapsed_ms, 2),
        renderer_used=renderer,
    )


def render_formula_to_png(inner: str, *, display_mode: bool = False) -> bytes | None:
    return render_formula_to_png_result(inner, display_mode=display_mode).png

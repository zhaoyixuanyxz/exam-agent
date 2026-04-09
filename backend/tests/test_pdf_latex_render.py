"""LaTeX 公式子系统：配置、分流、缓存键；KaTeX 集成为可选。"""

from __future__ import annotations

import os

import pytest

from app.config import settings
from app.services.pdf_latex_render import (
    render_formula_to_png,
    render_formula_to_png_result,
    should_render_with_latex,
)
from app.services.pdf_latex_render.cache import cache_key, cache_png_path
from app.services.pdf_latex_render.render import FORMULA_CACHE_VERSION


def test_render_formula_off_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "practice_pdf_latex_renderer", "off")
    assert render_formula_to_png(r"\frac{1}{2}", display_mode=False) is None
    r = render_formula_to_png_result(r"x^2", display_mode=False)
    assert r.png is None
    assert r.reason_code == "renderer_off"


def test_should_render_with_latex_begin_and_ampersand(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "practice_pdf_latex_max_inner_chars", 8000)
    monkeypatch.setattr(settings, "practice_pdf_latex_router_min_inner_len", 200)
    cases = r"\begin{cases} a \\ b \end{cases}"
    assert should_render_with_latex(cases, display_block=False) is True
    assert should_render_with_latex(r"a & b \\ c & d", display_block=False) is True


def test_should_render_display_block_always(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "practice_pdf_latex_max_inner_chars", 8000)
    assert should_render_with_latex("x", display_block=True) is True


def test_cache_key_stable() -> None:
    k1 = cache_key(
        version=FORMULA_CACHE_VERSION,
        renderer="katex",
        dpi=160,
        inner=r"\alpha",
        display_mode=False,
    )
    k2 = cache_key(
        version=FORMULA_CACHE_VERSION,
        renderer="katex",
        dpi=160,
        inner=r"\alpha",
        display_mode=False,
    )
    assert k1 == k2
    assert k1 != cache_key(
        version=FORMULA_CACHE_VERSION,
        renderer="katex",
        dpi=160,
        inner=r"\beta",
        display_mode=False,
    )


def test_cache_png_path(tmp_path) -> None:
    p = cache_png_path(tmp_path, "abc")
    assert p.name == "abc.png"


@pytest.mark.katex
def test_katex_playwright_produces_png() -> None:
    if os.environ.get("RUN_KATEX_INTEGRATION", "").lower() not in ("1", "true", "yes"):
        pytest.skip("set RUN_KATEX_INTEGRATION=1 and install playwright+chromium")
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright not installed")
    from app.services.pdf_latex_render.katex_playwright import render_katex_to_png_bytes

    png = render_katex_to_png_bytes(r"x^2+y^2=r^2", display_mode=False, timeout_sec=40.0)
    assert png is not None
    assert len(png) > 200

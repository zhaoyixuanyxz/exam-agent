"""Playwright + CDN KaTeX：将公式内层栅格为 PNG（需外网加载静态资源）。"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def render_katex_to_png_bytes(
    inner: str,
    *,
    display_mode: bool,
    timeout_sec: float,
) -> bytes | None:
    """失败返回 None（未安装 playwright、超时、CDN 不可达等）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("pdf_latex_render: playwright not installed")
        return None

    tex = (inner or "").strip()
    if not tex:
        return None

    css = settings.practice_pdf_latex_katex_css_url
    js = settings.practice_pdf_latex_katex_js_url
    tex_js = json.dumps(tex)
    disp = "true" if display_mode else "false"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<link rel="stylesheet" href="{css}"/>
<script src="{js}"></script>
</head>
<body style="margin:0;padding:10px;background:white;">
<div id="out"></div>
<script>
try {{
  katex.render({tex_js}, document.getElementById('out'), {{
    displayMode: {disp},
    throwOnError: false,
    trust: true,
    strict: false
  }});
}} catch (e) {{
  document.getElementById('out').textContent = String(e);
}}
</script>
</body></html>"""

    t0 = time.perf_counter()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                dpr = max(1.0, float(settings.practice_pdf_latex_dpi) / 96.0)
                page = browser.new_page(device_scale_factor=dpr)
                page.set_content(html, wait_until="load", timeout=int(timeout_sec * 1000))
                loc = page.locator("#out")
                loc.wait_for(state="visible", timeout=int(timeout_sec * 1000))
                box = loc.bounding_box()
                if not box or box["width"] < 1 or box["height"] < 1:
                    return None
                pad = 4.0
                clip = {
                    "x": max(0, box["x"] - pad),
                    "y": max(0, box["y"] - pad),
                    "width": box["width"] + 2 * pad,
                    "height": box["height"] + 2 * pad,
                }
                png = page.screenshot(type="png", clip=clip)
            finally:
                browser.close()
    except Exception as e:
        logger.debug("pdf_latex_render: katex playwright failed: %s", e, exc_info=True)
        return None

    elapsed = (time.perf_counter() - t0) * 1000.0
    if not png or len(png) < 80:
        return None
    logger.debug("pdf_latex_render: katex ok ms=%.1f bytes=%s", elapsed, len(png))
    return png

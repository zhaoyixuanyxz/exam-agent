"""可选：将短 mathtext 片段栅格为 PNG，供 fpdf 内联嵌入（与 Unicode 扁平化互补）。"""

from __future__ import annotations

import io
import logging
import re

logger = logging.getLogger(__name__)

# 过长的式子或含中文/换行则不走栅格，避免版面失控或 mathtext 失败
_MAX_INNER_CHARS = 56
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def mathtext_inner_to_png_bytes(
    inner: str,
    *,
    fontsize_pt: float = 11.0,
    dpi: int = 160,
) -> bytes | None:
    """将不含外层 $ 的 LaTeX 内层渲染为透明底 PNG；失败返回 None。"""
    s = (inner or "").strip()
    if not s or len(s) > _MAX_INNER_CHARS or "\n" in s or "$" in s:
        return None
    if _CJK_RE.search(s):
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig = plt.figure(figsize=(0.02, 0.02))
        fig.patch.set_alpha(0.0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            f"${s}$",
            fontsize=fontsize_pt,
            ha="center",
            va="center",
        )
        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.03,
            transparent=True,
        )
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 80 else None
    except Exception as e:
        logger.debug("pdf_math_inline: mathtext render failed: %s", e)
        return None


_INLINE_MATH_SEG = re.compile(r"\$([^$]+)\$")

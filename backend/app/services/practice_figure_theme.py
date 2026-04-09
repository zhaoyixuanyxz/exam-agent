"""练习配图统一图层与标签样式（matplotlib），避免导线/几何线穿过文字。"""

from __future__ import annotations

from typing import Any

# 由低到高：网格与填充最低，导线/线段，节点与符号，文字永远在最上
Z_GRID = 0
Z_FILL_PATCH = 0
Z_WIRE = 2
Z_GEOM_SEGMENT = 2
Z_SCATTER_POINT = 3
Z_SYMBOL_GEOM = 4
Z_ARROW_LOW = 3
Z_ARROW_HIGH = 6
Z_LABEL_TEXT = 10
Z_ANNOTATION = 11


def label_bbox_kwargs(*, pad: float = 0.22, alpha: float = 0.92) -> dict[str, Any]:
    """白底圆角框，略描边，减轻导线与标签重叠时的可读性问题。"""
    return {
        "boxstyle": f"round,pad={pad}",
        "facecolor": "white",
        "edgecolor": "#333333",
        "linewidth": 0.6,
        "alpha": alpha,
    }


def text_with_halo(
    ax: Any,
    x: float,
    y: float,
    s: str,
    *,
    fontsize: float,
    color: str,
    ha: str = "center",
    va: str = "center",
    weight: str | None = None,
    zorder: int | None = None,
    bbox_pad: float = 0.22,
    bbox_alpha: float = 0.92,
) -> None:
    """在数据坐标系下绘制带底框的文字，统一 zorder，避免被线段遮挡。"""
    if not (s or "").strip():
        return
    ax.text(
        x,
        y,
        s,
        ha=ha,
        va=va,
        fontsize=fontsize,
        color=color,
        weight=weight,
        bbox=label_bbox_kwargs(pad=bbox_pad, alpha=bbox_alpha),
        zorder=zorder if zorder is not None else Z_LABEL_TEXT,
    )

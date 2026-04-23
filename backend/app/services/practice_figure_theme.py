"""练习配图统一图层与标签样式（matplotlib），避免导线/几何线穿过文字。"""

from __future__ import annotations

from typing import Any

# --- 教材向视觉令牌（供 practice_figure_render 与 rcParams 对齐）---
AXIS_SPINE_LINEWIDTH = 0.95
TICK_MAJOR_LENGTH = 4.0
TICK_MAJOR_WIDTH = 0.85
GRID_LINEWIDTH = 0.55
GRID_ALPHA = 0.42
GRID_COLOR = "#b8b8b8"
TITLE_PAD_PT = 10
LEGEND_FRAME_EDGE = "#c8c8c8"
LEGEND_FRAME_LINEWIDTH = 0.55
LEGEND_CONTENT_FONTSIZE = 9

# --- Cartesian / bar / hist / pie / venn（统计类）---
CHART_SERIES_LW_NORMAL = 1.45
CHART_SERIES_LW_DENSE = 1.85
CHART_SCATTER_EDGE_LW = 1.05
CHART_ERROR_CAPSIZE = 2.2
CHART_BAR_EDGE_LW = 0.45
CHART_HIST_BAR_LW = 0.55
CHART_VENN_CIRCLE_LW = 1.65

# --- 示意几何 / 立几线框 / 光路界面等 ---
SCHEMATIC_GEOM_LW = 1.45
SCHEMATIC_FACE_EDGE_LW_SCALE = 0.6
SCHEMATIC_SECTION_EDGE_LW_SCALE = 1.15
SCHEMATIC_AUX_EDGE_LW_SCALE = 0.85

# --- 受力 / 场线 ---
FORCE_ARROW_LW = 1.55
FIELD_LINE_TRACE_LW = CHART_SERIES_LW_NORMAL
FIELD_LINE_ARROW_LW_FACTOR = 0.85

# --- 电路 ---
CIRCUIT_WIRE_LW = 1.6
CIRCUIT_RESISTOR_LW_FACTOR = 0.92
CIRCUIT_SYMBOL_LINEWIDTH = 1.05
CIRCUIT_JUNCTION_OUTLINE_LW = 1.05

# --- 时间轴 / 数轴 ---
TIMELINE_AXIS_LW = 1.55
TIMELINE_SERIES_LW = 1.15
TIMELINE_LABEL_STAGGER_PT = 10.0
NUMBER_LINE_AXIS_LW = 1.55
NUMBER_LINE_MARK_LW = 1.35
NUMBER_LINE_BAND_LW = 6.5
NUMBER_LINE_ENDPOINT_R_FACTOR = 0.012

# --- 几何标签与网格 ---
GEOM_GRID_ALPHA_SCALE = 0.62
LABEL_RELAX_MAX_ITERS = 88

# 技术线图端点/连接（示意几何、受力、场线等）
TECH_LINE_CAPSTYLE = "round"
TECH_LINE_JOINSTYLE = "round"

# 流程图 / 有向图：节点框线（FancyBboxPatch 等）
FLOW_ARROW_MUTATION_SCALE = 14
FLOW_NODE_PATCH_LW = 1.05
# 有向边与流程边（与旧 LW_FLOW_ARROW 1.25 对齐）
FLOW_EDGE_LINEWIDTH = 1.25
# 系谱连线、电化学示意细线、小符号描边等非 patch 主框
FLOW_AUX_STROKE_LW = 1.0

# 辅助线（虚线、法线）相对主线的对比
AUX_LINE_COLOR = "#5c5c5c"
AUX_LINE_WIDTH = 0.9

# --- 线型（matplotlib linestyle / dash tuple）---
LINE_STYLE_SOLID = "-"
LINE_STYLE_GRID_DASH = "--"
LINE_STYLE_AUX_DASH = "--"
LINE_STYLE_DOT = ":"
LINE_STYLE_DASHDOT_TUPLE = (0, (4, 4))

# 光路射线箭头：mutation_scale 相对 FLOW_ARROW_MUTATION_SCALE
OPTICS_RAY_MUTATION_SCALE_FACTOR = 0.78
OPTICS_RAY_ARROW_LW_FACTOR = 0.9


def chart_grid_alpha(*, textbook: bool) -> float:
    """直角坐标图网格透明度；教材向时略压低对比。"""
    return GRID_ALPHA * (0.82 if textbook else 1.0)


# 由低到高：网格与填充最低，导线/线段，节点与符号，文字永远在最上
Z_GRID = 0
Z_FILL_PATCH = 0
Z_WIRE = 2
Z_GEOM_SEGMENT = 2
Z_CIRCUIT_JUNCTION = 2.8
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

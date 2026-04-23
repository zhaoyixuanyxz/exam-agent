"""分块练习 PDF 配图：折线 / 柱状 / 饼图 / 几何草图 / 流程图（matplotlib Agg）。"""

from __future__ import annotations

import io
import logging
import math
import os
import re
from collections.abc import Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.path import Path as MplPath
from matplotlib.patches import (
    Arc,
    Circle,
    FancyArrowPatch,
    FancyBboxPatch,
    PathPatch,
    Polygon,
    Rectangle,
    Wedge,
)

from app.models.schemas import (
    PracticeBarSpec,
    PracticeCircuitSpec,
    PracticeCompositePanel,
    PracticeCompositePanelBar,
    PracticeCompositePanelCircuit,
    PracticeCompositePanelElectrochemicalCell,
    PracticeCompositePanelEnergyProfile,
    PracticeCompositePanelFieldLines,
    PracticeCompositePanelFlowchart,
    PracticeCompositePanelForceDiagram,
    PracticeCompositePanelGeometry,
    PracticeCompositePanelGroupedBar,
    PracticeCompositePanelHistogram,
    PracticeCompositePanelNumberLine,
    PracticeCompositePanelDirectedGraph,
    PracticeCompositePanelOpticsRay,
    PracticeCompositePanelPedigree,
    PracticeCompositePanelPie,
    PracticeCompositePanelPlot,
    PracticeCompositePanelProbabilityTree,
    PracticeCompositePanelSolidWireframe,
    PracticeCompositePanelSvg,
    PracticeCompositePanelTable,
    PracticeCompositePanelTimeline,
    PracticeCompositePanelUnitCircleTrig,
    PracticeCompositePanelVenn,
    PracticeCompositeSpec,
    PracticeElectrochemicalCellSpec,
    PracticeEnergyProfileSpec,
    PracticeFieldLinesSpec,
    PracticeFieldPresetLongStraightWire,
    PracticeFlowchartNode,
    PracticeFlowchartSpec,
    PracticeForceDiagramSpec,
    PracticeForceItem,
    PracticeGeometrySpec,
    PracticeGroupedBarSpec,
    PracticeHistogramSpec,
    PracticeNumberLineSpec,
    PracticeDirectedGraphEdge,
    PracticeDirectedGraphNode,
    PracticeDirectedGraphSpec,
    PracticeOpticsRaySpec,
    PracticePedigreeSpec,
    PracticePieSpec,
    PracticePlotSpec,
    PracticeProbabilityTreeSpec,
    PracticeQuestion,
    PracticeSolidWireframeSpec,
    PracticeTableSpec,
    PracticeTimelineSpec,
    PracticeUnitCircleTrigSpec,
    PracticeVennSpec,
)
from app.services.practice_circuit_display_labels import circuit_node_label_for_display
from app.services.practice_figure_text_sanitize import figure_matplotlib_plain_text
from app.services.practice_figure_field_presets import expand_field_line_presets
from app.services.practice_figure_theme import (
    AUX_LINE_COLOR,
    AUX_LINE_WIDTH,
    AXIS_SPINE_LINEWIDTH,
    CHART_BAR_EDGE_LW,
    CHART_ERROR_CAPSIZE,
    CHART_HIST_BAR_LW,
    CHART_SCATTER_EDGE_LW,
    CHART_SERIES_LW_DENSE,
    CHART_SERIES_LW_NORMAL,
    CHART_VENN_CIRCLE_LW,
    CIRCUIT_JUNCTION_OUTLINE_LW,
    CIRCUIT_RESISTOR_LW_FACTOR,
    CIRCUIT_SYMBOL_LINEWIDTH,
    CIRCUIT_WIRE_LW,
    FIELD_LINE_ARROW_LW_FACTOR,
    FIELD_LINE_TRACE_LW,
    FLOW_ARROW_MUTATION_SCALE,
    GRID_ALPHA,
    FLOW_AUX_STROKE_LW,
    FLOW_EDGE_LINEWIDTH,
    FLOW_NODE_PATCH_LW,
    FORCE_ARROW_LW,
    GEOM_GRID_ALPHA_SCALE,
    GRID_COLOR,
    GRID_LINEWIDTH,
    LABEL_RELAX_MAX_ITERS,
    LEGEND_CONTENT_FONTSIZE,
    LEGEND_FRAME_EDGE,
    LEGEND_FRAME_LINEWIDTH,
    LINE_STYLE_AUX_DASH,
    LINE_STYLE_DASHDOT_TUPLE,
    LINE_STYLE_DOT,
    LINE_STYLE_GRID_DASH,
    LINE_STYLE_SOLID,
    NUMBER_LINE_ENDPOINT_R_FACTOR,
    NUMBER_LINE_AXIS_LW,
    NUMBER_LINE_BAND_LW,
    NUMBER_LINE_MARK_LW,
    OPTICS_RAY_ARROW_LW_FACTOR,
    OPTICS_RAY_MUTATION_SCALE_FACTOR,
    SCHEMATIC_AUX_EDGE_LW_SCALE,
    SCHEMATIC_FACE_EDGE_LW_SCALE,
    SCHEMATIC_GEOM_LW,
    SCHEMATIC_SECTION_EDGE_LW_SCALE,
    TECH_LINE_CAPSTYLE,
    TECH_LINE_JOINSTYLE,
    TICK_MAJOR_LENGTH,
    TICK_MAJOR_WIDTH,
    TIMELINE_AXIS_LW,
    TIMELINE_LABEL_STAGGER_PT,
    TIMELINE_SERIES_LW,
    TITLE_PAD_PT,
    Z_ARROW_HIGH,
    Z_CIRCUIT_JUNCTION,
    Z_FILL_PATCH,
    Z_GEOM_SEGMENT,
    Z_GRID,
    Z_LABEL_TEXT,
    Z_SCATTER_POINT,
    Z_SYMBOL_GEOM,
    Z_WIRE,
    chart_grid_alpha,
    text_with_halo,
)
from app.services.practice_figure_primitives import (
    project_vertex_cabinet,
    project_vertex_isometric,
    project_vertex_oblique_pep,
    segment_arrow_tangent,
)
from app.services.practice_svg_safe import rasterize_svg_to_png

logger = logging.getLogger(__name__)

_FONT_CONFIGURED = False
_STYLE_RC_APPLIED = False


def _parse_figure_export_dpi() -> int:
    raw = (os.environ.get("FIGURE_EXPORT_DPI") or "").strip()
    if not raw:
        return 168
    try:
        d = int(float(raw))
        return max(72, min(600, d))
    except (TypeError, ValueError):
        return 168


# 印刷/彩印基线：savefig 与 composite 内 SVG 栅格化（rasterize_svg_to_png）共用同一 DPI。
# 可通过环境变量 FIGURE_EXPORT_DPI（72–600）提高导出分辨率。
_FIG_DPI = _parse_figure_export_dpi()

# 教材向强化：略压低网格对比、加大标题与轴间距等（与 _apply_figure_style_rc 配合）
_FIGURE_TEXTBOOK_STYLE = (os.environ.get("FIGURE_TEXTBOOK_STYLE") or "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# 占比低于此值的扇区合并为「其他」（经 clamp 上限后仍可能较多扇区）
_PIE_MERGE_FRACTION = 0.03
_MAX_BAR_TICK_CHARS = 14
_MAX_GEOM_LABEL_CHARS = 22
_MAX_FLOW_TEXT_MATH = 120
_GEOM_VIEW_MIN_RADIUS = 0.45

# 线宽别名：真值在 practice_figure_theme
LW_SERIES_NORMAL = CHART_SERIES_LW_NORMAL
LW_SERIES_DENSE = CHART_SERIES_LW_DENSE
LW_SCATTER_EDGE = CHART_SCATTER_EDGE_LW
LW_ERROR_CAP = CHART_ERROR_CAPSIZE
LW_BAR_EDGE = CHART_BAR_EDGE_LW
LW_GEOM = SCHEMATIC_GEOM_LW
LW_FORCE_ARROW = FORCE_ARROW_LW
LW_CIRCUIT_WIRE = CIRCUIT_WIRE_LW
LW_TIMELINE_AXIS = TIMELINE_AXIS_LW
LW_TIMELINE_SERIES = TIMELINE_SERIES_LW
LW_NUMBER_LINE_AXIS = NUMBER_LINE_AXIS_LW
LW_NUMBER_LINE_MARK = NUMBER_LINE_MARK_LW
LW_NUMBER_LINE_BAND = NUMBER_LINE_BAND_LW
LW_VENN = CHART_VENN_CIRCLE_LW
LW_HIST_BAR = CHART_HIST_BAR_LW

# 字号（pt）
FS_TITLE = 12
FS_AXIS = 11
FS_LEGEND = LEGEND_CONTENT_FONTSIZE
FS_SUBPLOT = 10
FS_PIE_LABEL = 10
FS_PIE_AUTO = 9
FS_SMALL = 8
FS_TABLE = 9
FS_VENN_MED = 10
FS_CIRCUIT_SYMBOL = 8

# 主系列色：色相差大、饱和度足够，避免浅 pastel 作主色
PRINT_SERIES_PALETTE: tuple[str, ...] = (
    "#0066CC",
    "#CC3300",
    "#228B22",
    "#7B1FA2",
    "#E65100",
    "#00838F",
    "#6A1B9A",
    "#C62828",
)

EDGE_NEUTRAL = "#2d2d2d"
TEXT_PRIMARY = "#1a1a1a"
TEXT_SECONDARY = "#333333"
ARROW_MUTED = "#3d3d3d"
FLOW_NODE_FILL = "#dce6f2"
FILL_BETWEEN_DEFAULT = "#4A90C2"
GEOM_FILL_DEFAULT = "#8eb4d8"
BAR_FILL_PRIMARY = PRINT_SERIES_PALETTE[0]
HIST_BAR_FILL = "#3182bd"
_GRID_ALPHA = 0.38

_GEOM_POLY_ALPHA_LO = 0.32
_GEOM_POLY_ALPHA_HI = 0.88
_GEOM_WEDGE_ALPHA = 0.52


def _clamp_alpha(a: float, lo: float, hi: float) -> float:
    try:
        x = float(a)
    except (TypeError, ValueError):
        return hi
    return max(lo, min(hi, x))


def _mpl_plain(s: str) -> str:
    """避免 matplotlib 将未声明的 $ 解析为 mathtext。"""
    if not s:
        return s
    return s.replace("\\", "\\\\").replace("$", r"\$")


def _is_wrapped_mathtext(s: str) -> bool:
    """整段为 $...$（如 $A$）。"""
    t = (s or "").strip()
    return len(t) >= 3 and t[0] == "$" and t[-1] == "$"


def _use_mathtext_effective(use_mathtext: bool, text: str) -> bool:
    """显式开启、或整段 $...$、或任意含 $（如 $20$ 米、边长 $x$ 与汉字混排）时按 mathtext 渲染。"""
    if use_mathtext:
        return True
    t = (text or "").strip()
    if _is_wrapped_mathtext(t):
        return True
    return "$" in t


def _mpl_label(text: str, *, use_mathtext: bool) -> str:
    t = (text or "").strip()
    if _use_mathtext_effective(use_mathtext, t):
        return t
    return _mpl_plain(t)


def _short_tick_label(text: str, max_len: int = _MAX_BAR_TICK_CHARS) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _text_visual_units(text: str) -> float:
    """粗估文字宽度：中文全角≈1，拉丁与数字≈0.56。"""
    u = 0.0
    for ch in text:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
            u += 1.0
        elif 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
            u += 1.0
        else:
            u += 0.56
    return max(u, 0.8)


def _label_half_extent(span: float, text: str, *, fontsize: float = FS_SUBPLOT) -> tuple[float, float]:
    """按数据坐标估算标签半宽/半高，用于避碰。"""
    units = _text_visual_units(text)
    fs_scale = max(0.82, min(1.35, fontsize / max(FS_SUBPLOT, 1)))
    half_w = max(0.03 * span, 0.0062 * span * units * fs_scale)
    half_h = max(0.024 * span, 0.0185 * span * fs_scale)
    return half_w, half_h


def _relax_label_positions(
    anchors: list[tuple[float, float]],
    texts: list[str],
    span: float,
    *,
    fontsize: float = FS_SUBPLOT,
    max_iters: int = LABEL_RELAX_MAX_ITERS,
    max_shift: float | None = None,
) -> list[tuple[float, float]]:
    """通用标签避碰：保持靠近锚点，同时迭代推开重叠框。"""
    n = len(anchors)
    if n <= 1:
        return anchors
    pos = [[float(x), float(y)] for x, y in anchors]
    halfs = [_label_half_extent(span, t, fontsize=fontsize) for t in texts]
    shift_cap = max_shift if max_shift is not None else max(0.58 * span, 0.26)
    margin = max(0.012 * span, 0.02)
    step = max(0.008 * span, 0.012)
    for _ in range(max_iters):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                x1, y1 = pos[i]
                x2, y2 = pos[j]
                w1, h1 = halfs[i]
                w2, h2 = halfs[j]
                ox = w1 + w2 + margin - abs(x1 - x2)
                oy = h1 + h2 + margin - abs(y1 - y2)
                if ox <= 0 or oy <= 0:
                    continue
                dx, dy = x2 - x1, y2 - y1
                d = math.hypot(dx, dy)
                if d < 1e-9:
                    ang = 0.61 * (i + 2 * j + 1)
                    dx, dy = math.cos(ang), math.sin(ang)
                    d = 1.0
                push = (max(ox, oy) * 0.42 + step) / d
                fx, fy = dx * push, dy * push
                pos[i][0] -= fx * 0.5
                pos[i][1] -= fy * 0.5
                pos[j][0] += fx * 0.5
                pos[j][1] += fy * 0.5
                moved = True
        for i in range(n):
            x0, y0 = anchors[i]
            dx, dy = pos[i][0] - x0, pos[i][1] - y0
            d = math.hypot(dx, dy)
            if d > shift_cap and d > 1e-9:
                pos[i][0] = x0 + dx * shift_cap / d
                pos[i][1] = y0 + dy * shift_cap / d
        if not moved:
            break
    return [(p[0], p[1]) for p in pos]


def _merge_small_pie_slices(
    labels: list[str],
    values: list[float],
    *,
    min_fraction: float = _PIE_MERGE_FRACTION,
) -> tuple[list[str], list[float]]:
    vals = [max(0.0, float(v)) for v in values]
    total = sum(vals)
    if total <= 0 or len(labels) != len(vals):
        return labels, vals
    if len(vals) <= 2:
        return labels, vals
    kept_lab: list[str] = []
    kept_val: list[float] = []
    other = 0.0
    for lab, v in zip(labels, vals):
        if v / total < min_fraction:
            other += v
        else:
            kept_lab.append(lab)
            kept_val.append(v)
    if other > 0:
        kept_lab.append("其他")
        kept_val.append(other)
    if not kept_lab:
        return labels, vals
    return kept_lab, kept_val


def _configure_matplotlib_font() -> None:
    global _FONT_CONFIGURED
    if _FONT_CONFIGURED:
        return
    _FONT_CONFIGURED = True
    try:
        from app.services.fonts import resolve_kaiti_font

        path = resolve_kaiti_font()
        font_manager.fontManager.addfont(path.as_posix())
        prop = font_manager.FontProperties(fname=path.as_posix())
        name = prop.get_name()
        plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans", "Arial"]
    except (FileNotFoundError, OSError, ValueError) as e:
        logger.debug("practice_figure_render: kaiti unavailable, %s", e)
        plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False
    _apply_figure_style_rc()


def _apply_figure_style_rc() -> None:
    """教材向 matplotlib 全局默认（仅初始化一次，与字体配置同生命周期）。"""
    global _STYLE_RC_APPLIED
    if _STYLE_RC_APPLIED:
        return
    _STYLE_RC_APPLIED = True
    rc: dict[str, object] = {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": EDGE_NEUTRAL,
        "axes.linewidth": AXIS_SPINE_LINEWIDTH,
        "axes.labelsize": FS_AXIS,
        "axes.titlesize": FS_TITLE,
        "axes.titlepad": TITLE_PAD_PT,
        "axes.grid": False,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": TICK_MAJOR_LENGTH,
        "ytick.major.size": TICK_MAJOR_LENGTH,
        "xtick.major.width": TICK_MAJOR_WIDTH,
        "ytick.major.width": TICK_MAJOR_WIDTH,
        "xtick.color": TEXT_PRIMARY,
        "ytick.color": TEXT_PRIMARY,
        "grid.color": GRID_COLOR,
        "grid.linestyle": "--",
        "grid.linewidth": GRID_LINEWIDTH,
        "grid.alpha": GRID_ALPHA,
        "legend.frameon": True,
        "legend.fancybox": True,
        "legend.framealpha": 0.92,
        "legend.edgecolor": LEGEND_FRAME_EDGE,
        "lines.solid_capstyle": TECH_LINE_CAPSTYLE,
        "lines.solid_joinstyle": TECH_LINE_JOINSTYLE,
    }
    if _FIGURE_TEXTBOOK_STYLE:
        rc["grid.alpha"] = GRID_ALPHA * 0.82
        rc["axes.titlepad"] = TITLE_PAD_PT + 2.0
    plt.rcParams.update(rc)


def _style_cartesian_chart_axes(
    ax,
    *,
    grid_x: bool = True,
    grid_y: bool = True,
) -> None:
    """带坐标轴的统计图：四边脊线 + 向外主刻度 + 浅灰虚线网格。"""
    ax.tick_params(
        axis="both",
        which="major",
        direction="out",
        length=TICK_MAJOR_LENGTH,
        width=TICK_MAJOR_WIDTH,
        labelsize=FS_AXIS,
        colors=TEXT_PRIMARY,
    )
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(EDGE_NEUTRAL)
        spine.set_linewidth(AXIS_SPINE_LINEWIDTH)
    ax.grid(False)
    g_alpha = chart_grid_alpha(textbook=_FIGURE_TEXTBOOK_STYLE)
    if grid_y:
        ax.grid(
            True,
            axis="y",
            linestyle=LINE_STYLE_GRID_DASH,
            color=GRID_COLOR,
            linewidth=GRID_LINEWIDTH,
            alpha=g_alpha,
            zorder=Z_GRID,
        )
    if grid_x:
        ax.grid(
            True,
            axis="x",
            linestyle=LINE_STYLE_GRID_DASH,
            color=GRID_COLOR,
            linewidth=GRID_LINEWIDTH,
            alpha=g_alpha,
            zorder=Z_GRID,
        )


def _legend_textbook(ax, handles, labels: list[str]) -> None:
    if not handles:
        return
    leg = ax.legend(
        handles,
        labels,
        loc="best",
        fontsize=LEGEND_CONTENT_FONTSIZE,
        framealpha=0.92,
        fancybox=True,
        edgecolor=LEGEND_FRAME_EDGE,
    )
    if leg is not None and leg.get_frame() is not None:
        leg.get_frame().set_linewidth(LEGEND_FRAME_LINEWIDTH)


def _draw_plot_series_on_ax(
    ax_target,
    slist: list,
    palette: tuple[str, ...],
    start_idx: int,
) -> None:
    if not slist:
        return
    max_pts = max(len(s.x) for s in slist)
    dense_line = max_pts >= 12
    for i, s in enumerate(slist):
        color = palette[(start_idx + i) % len(palette)]
        label = (s.label or "").strip() or f"series_{start_idx + i + 1}"
        has_err = s.y_err is not None and len(s.y_err) == len(s.x)
        if has_err:
            fmt = "o" if s.draw_as == "scatter" else "-"
            ax_target.errorbar(
                s.x,
                s.y,
                yerr=s.y_err,
                fmt=fmt,
                markersize=3.5,
                linewidth=LW_SERIES_NORMAL if s.draw_as != "scatter" else LW_SCATTER_EDGE,
                color=color,
                label=label,
                capsize=LW_ERROR_CAP,
                zorder=2,
            )
        elif s.draw_as == "scatter":
            ax_target.scatter(
                s.x,
                s.y,
                s=24,
                color=color,
                label=label,
                zorder=2,
                edgecolors=EDGE_NEUTRAL,
                linewidths=0.5,
            )
        elif dense_line:
            ax_target.plot(
                s.x, s.y, linewidth=LW_SERIES_DENSE, color=color, label=label, antialiased=True
            )
        else:
            ax_target.plot(
                s.x,
                s.y,
                marker="o",
                markersize=3.5,
                linewidth=LW_SERIES_NORMAL,
                color=color,
                label=label,
            )


def render_plot_to_png_bytes(spec: PracticePlotSpec) -> bytes | None:
    """
    将 PracticePlotSpec 渲染为 PNG 字节；失败返回 None（PDF 可跳过插图）。
    单点折线在 schema/parse 层已拦截；此处再防万一。
    """
    if not spec.series:
        return None
    for s in spec.series:
        if len(s.x) < 2 or len(s.y) < 2:
            logger.info("render_plot_to_png_bytes: skip series with fewer than 2 points")
            return None
    if spec.series_right:
        for s in spec.series_right:
            if len(s.x) < 2 or len(s.y) < 2:
                logger.info("render_plot_to_png_bytes: skip invalid series_right")
                return None
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        _draw_plot_series_on_ax(ax, list(spec.series), PRINT_SERIES_PALETTE, 0)

        use_log = (
            bool(spec.log_y)
            and not spec.series_right
            and all(all(yy > 0 for yy in s.y) for s in spec.series)
        )
        if use_log:
            ax.set_yscale("log")
        elif spec.log_y and not spec.series_right:
            logger.debug(
                "render_plot_to_png_bytes: log_y requested but non-positive y; using linear"
            )

        ax2 = None
        if spec.series_right:
            ax2 = ax.twinx()
            ax2.set_facecolor("white")
            _draw_plot_series_on_ax(
                ax2, list(spec.series_right), PRINT_SERIES_PALETTE, len(spec.series)
            )
            if spec.y_label_right.strip():
                ax2.set_ylabel(spec.y_label_right.strip(), fontsize=FS_AXIS)
            ax2.grid(False)

        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        if spec.x_label.strip():
            ax.set_xlabel(spec.x_label.strip(), fontsize=FS_AXIS)
        if spec.y_label.strip():
            ax.set_ylabel(spec.y_label.strip(), fontsize=FS_AXIS)
        _style_cartesian_chart_axes(ax, grid_x=True, grid_y=True)
        if ax2 is not None:
            ax2.tick_params(
                axis="y",
                which="major",
                direction="out",
                length=TICK_MAJOR_LENGTH,
                width=TICK_MAJOR_WIDTH,
                labelsize=FS_AXIS,
                colors=TEXT_PRIMARY,
            )
            ax2.spines["right"].set_visible(True)
            ax2.spines["right"].set_color(EDGE_NEUTRAL)
            ax2.spines["right"].set_linewidth(AXIS_SPINE_LINEWIDTH)

        for fb in spec.fill_between:
            if len(fb.x) < 2:
                continue
            try:
                col = (fb.color or "").strip() or FILL_BETWEEN_DEFAULT
                lbl = (fb.label or "").strip() or None
                ylo = list(fb.y_lower)
                yhi = list(fb.y_upper)
                if use_log and (any(v <= 0 for v in ylo) or any(v <= 0 for v in yhi)):
                    logger.debug(
                        "render_plot_to_png_bytes: skip fill_between under log_y (non-positive)"
                    )
                    continue
                ax.fill_between(
                    list(fb.x),
                    ylo,
                    yhi,
                    alpha=_clamp_alpha(float(fb.alpha), 0.22, 0.82),
                    color=col,
                    label=lbl,
                    linewidth=0,
                )
            except Exception as fe:
                logger.debug("render_plot_to_png_bytes: fill_between skip: %s", fe)

        if spec.show_legend:
            handles: list = []
            labels: list[str] = []
            for axis in [ax, ax2] if ax2 is not None else [ax]:
                h, lab = axis.get_legend_handles_labels()
                handles.extend(h)
                labels.extend(lab)
            if handles:
                _legend_textbook(ax, handles, labels)

        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_plot_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_bar_to_png_bytes(spec: PracticeBarSpec) -> bytes | None:
    """柱状图 PNG；失败返回 None。"""
    if not spec.categories or len(spec.categories) != len(spec.values):
        return None
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        x = range(len(spec.categories))
        colors = [PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)] for i in x]
        bars = ax.bar(
            x,
            spec.values,
            color=colors,
            edgecolor=EDGE_NEUTRAL,
            linewidth=LW_BAR_EDGE,
            zorder=2,
        )
        rot = 35 if len(spec.categories) > 5 else 0
        tick_labels = [_short_tick_label(c) for c in spec.categories]
        ax.set_xticks(list(x))
        ax.set_xticklabels(tick_labels, rotation=rot, ha="right")
        vals = [float(v) for v in spec.values]
        vmax = max(vals) if vals else 0.0
        ymin = min(vals + [0.0])
        y_span = max(vmax - ymin, abs(vmax), 1.0)
        y_off = 0.035 * y_span
        if spec.show_values:
            for rect, v in zip(bars, vals):
                xmid = float(rect.get_x() + rect.get_width() / 2.0)
                ytxt = float(v + (y_off if v >= 0 else -y_off))
                va = "bottom" if v >= 0 else "top"
                text_with_halo(
                    ax,
                    xmid,
                    ytxt,
                    _short_tick_label(f"{v:g}", 8),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    va=va,
                    bbox_pad=0.12,
                    zorder=Z_LABEL_TEXT,
                )
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        if spec.x_label.strip():
            ax.set_xlabel(spec.x_label.strip(), fontsize=FS_AXIS)
        if spec.y_label.strip():
            ax.set_ylabel(spec.y_label.strip(), fontsize=FS_AXIS)
        _style_cartesian_chart_axes(ax, grid_x=False, grid_y=True)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_bar_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_grouped_bar_to_png_bytes(spec: PracticeGroupedBarSpec) -> bytes | None:
    """分组柱状图 PNG；失败返回 None。"""
    if not spec.categories or not spec.series:
        return None
    n_cat = len(spec.categories)
    for s in spec.series:
        if len(s.values) != n_cat:
            return None
    _configure_matplotlib_font()
    try:
        n_series = len(spec.series)
        fig, ax = plt.subplots(figsize=(5.4, 3.5), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        x = range(n_cat)
        bar_w = 0.8 / max(1, n_series)
        all_vals: list[float] = []
        for i, s in enumerate(spec.series):
            offset = -0.4 + bar_w / 2 + i * bar_w
            xpos = [xi + offset for xi in x]
            label = (s.label or "").strip() or f"系列{i + 1}"
            bars = ax.bar(
                xpos,
                s.values,
                width=bar_w * 0.92,
                color=PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)],
                edgecolor=EDGE_NEUTRAL,
                linewidth=LW_BAR_EDGE,
                label=label,
                zorder=2,
            )
            all_vals.extend(float(v) for v in s.values)
            if spec.show_values:
                y_base = max(max(all_vals + [0.0]), 1.0)
                y_off = 0.024 * y_base
                for rect, v in zip(bars, s.values):
                    fv = float(v)
                    text_with_halo(
                        ax,
                        float(rect.get_x() + rect.get_width() / 2.0),
                        float(fv + (y_off if fv >= 0 else -y_off)),
                        _short_tick_label(f"{fv:g}", 8),
                        fontsize=FS_SMALL - 0.3,
                        color=TEXT_SECONDARY,
                        va="bottom" if fv >= 0 else "top",
                        bbox_pad=0.1,
                        zorder=Z_LABEL_TEXT,
                    )
        rot = 35 if n_cat > 5 else 0
        tick_labels = [_short_tick_label(c) for c in spec.categories]
        ax.set_xticks(list(x))
        ax.set_xticklabels(tick_labels, rotation=rot, ha="right")
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        if spec.x_label.strip():
            ax.set_xlabel(spec.x_label.strip(), fontsize=FS_AXIS)
        if spec.y_label.strip():
            ax.set_ylabel(spec.y_label.strip(), fontsize=FS_AXIS)
        _style_cartesian_chart_axes(ax, grid_x=False, grid_y=True)
        if spec.show_legend:
            h, lab = ax.get_legend_handles_labels()
            _legend_textbook(ax, h, lab)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_grouped_bar_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_pie_to_png_bytes(spec: PracticePieSpec) -> bytes | None:
    """饼图 PNG；数值在渲染层归一化，全非正时失败。"""
    if not spec.labels or len(spec.labels) != len(spec.values):
        return None
    vals = [float(v) for v in spec.values]
    total = sum(max(0.0, v) for v in vals)
    if total <= 0:
        return None
    mlab, mval = _merge_small_pie_slices(list(spec.labels), vals)
    use = [max(0.0, v) for v in mval]
    if sum(use) <= 0:
        return None
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.0, 3.6), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=TITLE_PAD_PT)
        pie_labels = [_short_tick_label(lb, max_len=12) for lb in mlab]
        nslice = len(use)
        pie_colors = [PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)] for i in range(nslice)]
        digits = int(spec.percent_digits)
        if nslice > 6:
            digits = min(digits, 0)

        def _autopct(pct: float) -> str:
            if pct < 0.5:
                return ""
            return f"{pct:.{digits}f}%"

        _wedges, _texts, autotexts = ax.pie(
            use,
            labels=pie_labels,
            autopct=_autopct,
            startangle=90,
            colors=pie_colors,
            textprops={"fontsize": FS_PIE_LABEL},
            wedgeprops={"linewidth": LW_BAR_EDGE, "edgecolor": EDGE_NEUTRAL},
        )
        for t in autotexts:
            t.set_fontsize(FS_PIE_AUTO)
        ax.axis("equal")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_pie_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _geom_center(
    center_id: str,
    cx: float | None,
    cy: float | None,
    id_to_xy: dict[str, tuple[float, float]],
) -> tuple[float, float] | None:
    cid = (center_id or "").strip()
    if cid and cid in id_to_xy:
        return id_to_xy[cid]
    if cx is not None and cy is not None and math.isfinite(cx) and math.isfinite(cy):
        return (float(cx), float(cy))
    return None


def _geom_edge_color(s: str) -> str:
    t = (s or "").strip()
    return t if t else EDGE_NEUTRAL


def _geom_fill_color(s: str) -> str:
    t = (s or "").strip()
    return t if t else GEOM_FILL_DEFAULT


def render_geometry_to_png_bytes(spec: PracticeGeometrySpec) -> bytes | None:
    """平面几何：点、线段、圆、弧、多边形、坐标标签。"""
    id_to_xy: dict[str, tuple[float, float]] = {}
    for i, p in enumerate(spec.points):
        x, y = float(p.x), float(p.y)
        if not (math.isfinite(x) and math.isfinite(y)):
            logger.debug("render_geometry_to_png_bytes: skip non-finite point index=%s", i)
            continue
        pid = (p.id or "").strip() or f"_p{i}"
        if pid in id_to_xy:
            pid = f"_p{i}_{pid}"
        id_to_xy[pid] = (x, y)

    xs: list[float] = []
    ys: list[float] = []
    for _k, (x, y) in id_to_xy.items():
        xs.append(x)
        ys.append(y)
    for lb in spec.labels:
        if not (lb.text or "").strip():
            continue
        lx, ly = float(lb.x), float(lb.y)
        if not (math.isfinite(lx) and math.isfinite(ly)):
            logger.debug("render_geometry_to_png_bytes: skip non-finite label position")
            continue
        xs.append(lx)
        ys.append(ly)

    has_seg = False
    for seg in spec.segments:
        a = (seg.a or "").strip()
        b = (seg.b or "").strip()
        if a in id_to_xy and b in id_to_xy:
            has_seg = True
            xa, ya = id_to_xy[a]
            xb, yb = id_to_xy[b]
            xs.extend([xa, xb])
            ys.extend([ya, yb])

    for c in spec.circles:
        cen = _geom_center(c.center_id, c.cx, c.cy, id_to_xy)
        if cen is None or not math.isfinite(c.r) or c.r <= 0:
            continue
        cx, cy = cen
        r = float(c.r)
        xs.extend([cx - r, cx + r])
        ys.extend([cy - r, cy + r])

    for poly in spec.polygons:
        verts: list[tuple[float, float]] = []
        for vid in poly.vertex_ids:
            k = (vid or "").strip()
            if k not in id_to_xy:
                verts = []
                break
            verts.append(id_to_xy[k])
        for vx, vy in verts:
            xs.append(vx)
            ys.append(vy)

    for a in spec.arcs:
        cen = _geom_center(a.center_id, a.cx, a.cy, id_to_xy)
        if cen is None or not math.isfinite(a.r) or a.r <= 0:
            continue
        cx, cy = cen
        r = float(a.r)
        xs.extend([cx - r, cx + r])
        ys.extend([cy - r, cy + r])

    has_pts = len(id_to_xy) > 0
    has_drawable_label = any(
        (lb.text or "").strip() and math.isfinite(float(lb.x)) and math.isfinite(float(lb.y))
        for lb in spec.labels
    )
    has_circles = any(
        _geom_center(c.center_id, c.cx, c.cy, id_to_xy) is not None and c.r > 0
        for c in spec.circles
    )
    has_poly = False
    for poly in spec.polygons:
        if len(poly.vertex_ids) >= 3 and all(
            (vid or "").strip() in id_to_xy for vid in poly.vertex_ids
        ):
            has_poly = True
            break
    has_arcs = any(
        _geom_center(a.center_id, a.cx, a.cy, id_to_xy) is not None and a.r > 0 for a in spec.arcs
    )

    if (
        not has_pts
        and not has_drawable_label
        and not has_seg
        and not has_circles
        and not has_poly
        and not has_arcs
    ):
        return None

    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.2, 3.8), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        for poly in spec.polygons:
            verts: list[tuple[float, float]] = []
            for vid in poly.vertex_ids:
                k = (vid or "").strip()
                if k not in id_to_xy:
                    verts = []
                    break
                verts.append(id_to_xy[k])
            if len(verts) < 3:
                continue
            arr = np.array(verts)
            ec = _geom_edge_color(poly.edge_color)
            if poly.fill:
                fc = _geom_fill_color(poly.fill_color)
                pa = _clamp_alpha(float(poly.alpha), _GEOM_POLY_ALPHA_LO, _GEOM_POLY_ALPHA_HI)
                patch = Polygon(
                    arr,
                    closed=True,
                    facecolor=fc,
                    edgecolor=ec,
                    linewidth=LW_GEOM,
                    alpha=pa,
                    zorder=Z_FILL_PATCH,
                )
            else:
                patch = Polygon(
                    arr,
                    closed=True,
                    facecolor="none",
                    edgecolor=ec,
                    linewidth=LW_GEOM,
                    zorder=Z_FILL_PATCH,
                )
            ax.add_patch(patch)

        for c in spec.circles:
            cen = _geom_center(c.center_id, c.cx, c.cy, id_to_xy)
            if cen is None:
                continue
            cx, cy = cen
            r = float(c.r)
            if not math.isfinite(r) or r <= 0:
                continue
            ec = _geom_edge_color(c.edge_color)
            if c.fill:
                fc = _geom_fill_color(c.fill_color)
                patch = Circle(
                    (cx, cy), r, facecolor=fc, edgecolor=ec, linewidth=LW_GEOM, zorder=Z_FILL_PATCH
                )
            else:
                patch = Circle(
                    (cx, cy),
                    r,
                    facecolor="none",
                    edgecolor=ec,
                    linewidth=LW_GEOM,
                    zorder=Z_FILL_PATCH,
                )
            ax.add_patch(patch)

        for ar in spec.arcs:
            cen = _geom_center(ar.center_id, ar.cx, ar.cy, id_to_xy)
            if cen is None:
                continue
            cx, cy = cen
            r = float(ar.r)
            if not math.isfinite(r) or r <= 0:
                continue
            t1, t2 = float(ar.theta1_deg), float(ar.theta2_deg)
            ec = _geom_edge_color(ar.edge_color)
            if ar.fill:
                fc = _geom_fill_color(ar.fill_color)
                w = Wedge(
                    (cx, cy),
                    r,
                    t1,
                    t2,
                    facecolor=fc,
                    edgecolor=ec,
                    linewidth=LW_GEOM,
                    alpha=_GEOM_WEDGE_ALPHA,
                    zorder=Z_FILL_PATCH,
                )
                ax.add_patch(w)
            else:
                arc = Arc(
                    (cx, cy),
                    2 * r,
                    2 * r,
                    theta1=t1,
                    theta2=t2,
                    edgecolor=ec,
                    linewidth=LW_GEOM,
                    zorder=Z_FILL_PATCH,
                )
                ax.add_patch(arc)

        for seg in spec.segments:
            a = (seg.a or "").strip()
            b = (seg.b or "").strip()
            if a not in id_to_xy or b not in id_to_xy:
                logger.debug(
                    "render_geometry_to_png_bytes: skip segment %s-%s (missing point id)",
                    a,
                    b,
                )
                continue
            x0, y0 = id_to_xy[a]
            x1, y1 = id_to_xy[b]
            role = (seg.role or "main").strip().lower()
            seg_style = (seg.style or "solid").strip().lower()
            if role in {"auxiliary", "hidden"} and seg_style == "solid":
                seg_style = "dashed"
            if role in {"ray", "extension"} and seg_style == "solid":
                seg_style = "dotted"
            ls = LINE_STYLE_SOLID
            if seg_style == "dashed":
                ls = LINE_STYLE_AUX_DASH
            elif seg_style == "dotted":
                ls = LINE_STYLE_DOT
            col = (seg.color or "").strip() or (AUX_LINE_COLOR if role in {"auxiliary", "hidden"} else EDGE_NEUTRAL)
            lw = LW_GEOM * (0.85 if role in {"auxiliary", "hidden"} else 1.0)
            ax.plot(
                [x0, x1],
                [y0, y1],
                color=col,
                linewidth=lw,
                linestyle=ls,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=Z_GEOM_SEGMENT,
            )

        for am in spec.angle_markers:
            a = (am.a or "").strip()
            b = (am.b or "").strip()
            c = (am.c or "").strip()
            if a not in id_to_xy or b not in id_to_xy or c not in id_to_xy:
                continue
            ax0, ay0 = id_to_xy[a]
            bx0, by0 = id_to_xy[b]
            cx0, cy0 = id_to_xy[c]
            v1x, v1y = ax0 - bx0, ay0 - by0
            v2x, v2y = cx0 - bx0, cy0 - by0
            n1 = math.hypot(v1x, v1y)
            n2 = math.hypot(v2x, v2y)
            if n1 < 1e-9 or n2 < 1e-9:
                continue
            u1x, u1y = v1x / n1, v1y / n1
            u2x, u2y = v2x / n2, v2y / n2
            rr = max(0.045 * max(max(xs) - min(xs), max(ys) - min(ys), 1.0), 0.12)
            if am.right_angle:
                p1 = (bx0 + u1x * rr, by0 + u1y * rr)
                p2 = (p1[0] + u2x * rr, p1[1] + u2y * rr)
                p3 = (bx0 + u2x * rr, by0 + u2y * rr)
                ax.plot(
                    [p1[0], p2[0], p3[0]],
                    [p1[1], p2[1], p3[1]],
                    color=TEXT_SECONDARY,
                    linewidth=max(0.95, FLOW_AUX_STROKE_LW),
                    zorder=Z_SYMBOL_GEOM,
                )
            else:
                t1 = math.degrees(math.atan2(u1y, u1x))
                t2 = math.degrees(math.atan2(u2y, u2x))
                arc = Arc(
                    (bx0, by0),
                    2 * rr,
                    2 * rr,
                    theta1=t1,
                    theta2=t2,
                    edgecolor=TEXT_SECONDARY,
                    linewidth=max(0.95, FLOW_AUX_STROKE_LW),
                    zorder=Z_SYMBOL_GEOM,
                )
                ax.add_patch(arc)
            lab = (am.label or "").strip()
            if lab:
                bisx, bisy = u1x + u2x, u1y + u2y
                nb = math.hypot(bisx, bisy)
                if nb < 1e-9:
                    bisx, bisy = -u1y, u1x
                    nb = math.hypot(bisx, bisy)
                bisx, bisy = bisx / nb, bisy / nb
                text_with_halo(
                    ax,
                    bx0 + bisx * rr * 1.42,
                    by0 + bisy * rr * 1.42,
                    _short_tick_label(_mpl_plain(lab), 10),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    bbox_pad=0.1,
                    zorder=Z_LABEL_TEXT,
                )

        if has_pts:
            px_fill: list[float] = []
            py_fill: list[float] = []
            px_hollow: list[float] = []
            py_hollow: list[float] = []
            for p in spec.points:
                pid = (p.id or "").strip()
                if pid not in id_to_xy:
                    continue
                style = (p.style or "auto").strip().lower()
                if style == "none":
                    continue
                xpt, ypt = id_to_xy[pid]
                if style == "hollow":
                    px_hollow.append(xpt)
                    py_hollow.append(ypt)
                elif style == "filled":
                    px_fill.append(xpt)
                    py_fill.append(ypt)
                else:
                    # auto：有连接线时用 hollow，孤立点用 filled
                    if has_seg:
                        px_hollow.append(xpt)
                        py_hollow.append(ypt)
                    else:
                        px_fill.append(xpt)
                        py_fill.append(ypt)
            if px_hollow:
                ax.scatter(
                    px_hollow,
                    py_hollow,
                    s=36,
                    facecolors="white",
                    edgecolors=EDGE_NEUTRAL,
                    linewidths=0.95,
                    zorder=Z_SCATTER_POINT,
                )
            if px_fill:
                ax.scatter(
                    px_fill,
                    py_fill,
                    s=36,
                    facecolors=TEXT_PRIMARY,
                    edgecolors=EDGE_NEUTRAL,
                    linewidths=0.7,
                    zorder=Z_SCATTER_POINT,
                )
            px = px_fill + px_hollow
            py = py_fill + py_hollow
            ax.scatter(
                px,
                py,
                s=7,
                color=TEXT_PRIMARY,
                linewidths=0.0,
                zorder=Z_SCATTER_POINT + 0.1,
            )

        geom_label_entries: list[tuple[float, float, str, str, float]] = []
        for lb in spec.labels:
            t = (lb.text or "").strip()
            if not t:
                continue
            lx, ly = float(lb.x), float(lb.y)
            if not (math.isfinite(lx) and math.isfinite(ly)):
                continue
            disp = _mpl_label(t, use_mathtext=lb.use_mathtext)
            if not _use_mathtext_effective(lb.use_mathtext, t):
                disp = _short_tick_label(disp, max_len=_MAX_GEOM_LABEL_CHARS)
            fs = FS_SUBPLOT - 0.2 if len(disp) <= 10 else FS_SUBPLOT - 0.5
            geom_label_entries.append((lx, ly, disp, t, fs))

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)

        if xs and ys:
            x_lo, x_hi = min(xs), max(xs)
            y_lo, y_hi = min(ys), max(ys)
            dx = x_hi - x_lo
            dy = y_hi - y_lo
            pad = max(0.15 * (dx or 1.0), 0.15 * (dy or 1.0), 0.2)
            cx_ = (x_lo + x_hi) / 2.0
            cy_ = (y_lo + y_hi) / 2.0
            half_data = max(dx / 2.0 + pad, dy / 2.0 + pad, _GEOM_VIEW_MIN_RADIUS)
            ax.set_xlim(cx_ - half_data, cx_ + half_data)
            ax.set_ylim(cy_ - half_data, cy_ + half_data)
        ax.set_aspect("equal", adjustable="datalim")
        show_grid = bool(spec.show_grid) and has_seg and (len(spec.segments) >= 2 or has_circles or has_poly)
        if show_grid:
            ax.grid(
                True,
                linestyle=LINE_STYLE_DOT,
                color=GRID_COLOR,
                linewidth=GRID_LINEWIDTH,
                alpha=chart_grid_alpha(textbook=_FIGURE_TEXTBOOK_STYLE) * GEOM_GRID_ALPHA_SCALE,
                zorder=Z_GRID,
            )
        fig.tight_layout()

        if geom_label_entries and xs and ys:
            geo_span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
            anchors = [(e[0], e[1]) for e in geom_label_entries]
            texts = [e[2] for e in geom_label_entries]
            fs_for_relax = max(e[4] for e in geom_label_entries)
            relaxed = _relax_label_positions(
                anchors,
                texts,
                geo_span,
                fontsize=fs_for_relax,
                max_iters=96,
                max_shift=max(0.36 * geo_span, 0.26),
            )
        else:
            relaxed = [(e[0], e[1]) for e in geom_label_entries]

        for (lx, ly), (_ax, _ay, disp, t, fs) in zip(relaxed, geom_label_entries):
            try:
                text_with_halo(
                    ax,
                    lx,
                    ly,
                    disp,
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    bbox_pad=0.18,
                )
            except Exception:
                text_with_halo(
                    ax,
                    lx,
                    ly,
                    _short_tick_label(_mpl_plain(t), max_len=_MAX_GEOM_LABEL_CHARS),
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    bbox_pad=0.18,
                )

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_geometry_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _normalize_flowchart_body_text(raw: str) -> str:
    """把 JSON/字符串里常见的字面 \\n 转为真换行。"""
    if not raw:
        return raw
    s = raw.replace("\r\n", "\n")
    while "\\\\n" in s:
        s = s.replace("\\\\n", "\n")
    s = s.replace("\\n", "\n")
    return s


_FLOW_SUBSCRIPT_TRANS = str.maketrans(
    "₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹",
    "01234567890123456789",
)


def _flowchart_sanitize_formula_boxes(s: str) -> str:
    """修复常见「□」占位（多为下标在字体中缺失）及残缺化学式。"""
    if not s:
        return s
    t = s.replace("\ufffd", "□")
    for ch in ("\u25a1", "\u2610", "\u25ab"):
        t = t.replace(ch, "□")
    if "□" not in t:
        return t
    fixes = (
        (r"Na\s*□\s*SO\s*□", "Na2SO4"),
        (r"Na\s*□\s*CO\s*□", "Na2CO3"),
        (r"Na\s*□\s*CO\s*3", "Na2CO3"),
        (r"Na\s*2\s*CO\s*□", "Na2CO3"),
        (r"K\s*□\s*CO\s*□", "K2CO3"),
        (r"MgCl\s*□", "MgCl2"),
        (r"CaCl\s*□", "CaCl2"),
        (r"BaCl\s*□", "BaCl2"),
        (r"FeCl\s*□", "FeCl3"),
        (r"AlCl\s*□", "AlCl3"),
        (r"CuSO\s*□", "CuSO4"),
        (r"AgNO\s*□", "AgNO3"),
        (r"H\s*2\s*SO\s*□", "H2SO4"),
        (r"H\s*□\s*SO\s*□", "H2SO4"),
        (r"H\s*□\s*SO\s*4", "H2SO4"),
        (r"Na\s*□\s*SO\s*4", "Na2SO4"),
        (r"Na\s*□\s*SO\s*□", "Na2SO4"),
        (r"SO\s*□\s*4", "SO4"),
        (r"CO\s*□\s*3", "CO3"),
    )
    for pat, rep in fixes:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)
    # 残余 □ 多为单个缺失下标：Cl□ → Cl2（粗盐语境常见二氯化物）
    t = re.sub(
        r"(?<![A-Za-z])([MgCaBaZnCuFe])Cl\s*□",
        r"\1Cl2",
        t,
        flags=re.IGNORECASE,
    )
    t = t.replace("□", "")
    return t


def _flowchart_plain_body_normalize(s: str) -> str:
    """
    非 mathtext 流程图正文：Unicode 上下标转 ASCII 数字，避免缺字显示为□；
    再修补常见化学式占位。输出一律用 ASCII 数字下标风格（Na2CO3），保证默认字体可显示。
    """
    if not s:
        return s
    t = s.translate(_FLOW_SUBSCRIPT_TRANS)
    t = _flowchart_sanitize_formula_boxes(t)
    ascii_formulas = (
        ("Na2CO3", "Na2CO3"),
        ("NaHCO3", "NaHCO3"),
        ("BaCl2", "BaCl2"),
        ("CaCl2", "CaCl2"),
        ("MgCl2", "MgCl2"),
        ("Na2SO4", "Na2SO4"),
        ("MgSO4", "MgSO4"),
        ("CaSO4", "CaSO4"),
        ("K2SO4", "K2SO4"),
        ("AlCl3", "AlCl3"),
        ("FeCl3", "FeCl3"),
        ("FeCl2", "FeCl2"),
        ("H2SO4", "H2SO4"),
        ("HNO3", "HNO3"),
        ("CuSO4", "CuSO4"),
        ("AgNO3", "AgNO3"),
        ("CO2", "CO2"),
        ("SO2", "SO2"),
        ("H2O", "H2O"),
        ("NH3", "NH3"),
        ("CH4", "CH4"),
        ("Fe2O3", "Fe2O3"),
        ("Al2O3", "Al2O3"),
        ("MnO2", "MnO2"),
        ("KMnO4", "KMnO4"),
        ("KClO3", "KClO3"),
    )
    for src, dst in ascii_formulas:
        t = t.replace(src, dst)
        lo = src.lower()
        if lo != src:
            t = t.replace(lo, dst)
    return t


def _flowchart_display_lines(
    raw: str,
    *,
    use_mathtext: bool,
    fallback_id: str,
) -> tuple[str, list[str], int]:
    """
    返回 (传给 ax.text 的字符串（含 \\n）, 行列表, fontsize 微调)。
    """
    t = _normalize_flowchart_body_text(raw) or fallback_id
    t = t[:_MAX_FLOW_TEXT_MATH]
    if use_mathtext:
        single = t.replace("\n", " ").strip()
        return single, [single], 0
    t = _flowchart_plain_body_normalize(t)
    parts = [ln.strip() for ln in t.split("\n")]
    lines = [p for p in parts if p] or [t.strip() or fallback_id]
    trimmed = [_short_tick_label(L, max_len=56) for L in lines]
    joined = "\n".join(trimmed)
    fs_delta = 0
    if len(trimmed) >= 3:
        fs_delta -= 1
    if max(len(x) for x in trimmed) > 18:
        fs_delta -= 1
    return joined, trimmed, fs_delta


def _flowchart_text_width_units(s: str) -> float:
    """估算一行在等宽坐标下的「视觉宽度」：中文约 1，拉丁/数字约 0.55。"""
    u = 0.0
    for ch in s:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
            u += 1.0
        elif 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
            u += 1.0
        else:
            u += 0.55
    return max(u, 0.6)


def _flowchart_node_box_dims(lines: list[str]) -> tuple[float, float]:
    """根据行数与最长行估算框宽高（数据坐标）；中文占宽大于 len，避免挤出框外。"""
    if not lines:
        return 1.08, 0.56
    max_u = max(_flowchart_text_width_units(L) for L in lines)
    n = len(lines)
    w = max(1.05, min(10.8, 0.192 * max_u + 0.95))
    h = max(0.54, min(3.85, 0.32 * n + 0.38))
    return w, h


def _render_flowchart_layered_to_png_bytes(
    spec: PracticeFlowchartSpec,
    nodes: list[PracticeFlowchartNode],
) -> bytes | None:
    """自上而下分层；含环时返回 None。"""
    ids = [(n.id or "").strip() for n in nodes]
    id_set = set(ids)
    adj: dict[str, list[str]] = {i: [] for i in ids}
    indeg = {i: 0 for i in ids}
    for e in spec.edges:
        s, t = (e.source or "").strip(), (e.target or "").strip()
        if s in id_set and t in id_set and s != t:
            adj[s].append(t)
            indeg[t] += 1
    q = [i for i in ids if indeg[i] == 0]
    topo: list[str] = []
    indeg_w = dict(indeg)
    while q:
        u = q.pop(0)
        topo.append(u)
        for v in adj[u]:
            indeg_w[v] -= 1
            if indeg_w[v] == 0:
                q.append(v)
    if len(topo) != len(ids):
        return None
    rank = {i: 0 for i in ids}
    for u in topo:
        ru = rank[u]
        for v in adj[u]:
            rank[v] = max(rank[v], ru + 1)
    layers: dict[int, list[str]] = {}
    max_r = 0
    for nid in ids:
        r = rank[nid]
        max_r = max(max_r, r)
        layers.setdefault(r, []).append(nid)
    for r in layers:
        layers[r].sort()

    node_attr: dict[str, tuple[float, float, str, bool, str, int, str]] = {}
    for nid in ids:
        node = next((x for x in nodes if (x.id or "").strip() == nid), None)
        raw = (node.text if node else "") or nid
        um = bool(node and node.use_mathtext)
        joined, lines, fs_delta = _flowchart_display_lines(
            raw, use_mathtext=um, fallback_id=nid
        )
        if um:
            txt_disp = _mpl_label(joined, use_mathtext=True)
            if not _use_mathtext_effective(um, joined):
                txt_disp = _short_tick_label(
                    txt_disp.replace("\n", " "), max_len=26
                )
            w, h = _flowchart_node_box_dims([txt_disp])
        else:
            txt_disp = joined
            w, h = _flowchart_node_box_dims(lines)
        node_attr[nid] = (w, h, raw, um, txt_disp, fs_delta, (node.shape if node else "process"))

    pos: dict[str, tuple[float, float]] = {}
    node_boxes: dict[str, tuple[float, float, float, float]] = {}
    y_step = 1.12
    gap = 0.34
    for r in range(max_r + 1):
        row = layers.get(r, [])
        if not row:
            continue
        total_w = sum(node_attr[nid][0] for nid in row) + gap * max(0, len(row) - 1)
        x_left = -total_w / 2.0
        cy = -r * y_step
        x_cur = x_left
        for nid in row:
            w, h, _, _, _, _, _ = node_attr[nid]
            cx = x_cur + w / 2.0
            pos[nid] = (cx, cy)
            node_boxes[nid] = (cx, cy, w, h)
            x_cur += w + gap

    _configure_matplotlib_font()
    try:
        fig_w = min(8.4, 4.2 + 0.55 * max((a[0] for a in node_attr.values()), default=1.0))
        fig_h = 3.0 + 0.48 * (max_r + 1)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_aspect("equal", adjustable="datalim")

        max_half_w = 0.0
        for nid, (cx, cy) in pos.items():
            w, h, raw, um, txt_disp, fs_delta, shape = node_attr[nid]
            max_half_w = max(max_half_w, w / 2.0)
            if shape == "decision":
                ax.add_patch(
                    Polygon(
                        [
                            (cx, cy + h / 2),
                            (cx + w / 2, cy),
                            (cx, cy - h / 2),
                            (cx - w / 2, cy),
                        ],
                        closed=True,
                        facecolor=FLOW_NODE_FILL,
                        edgecolor=EDGE_NEUTRAL,
                        linewidth=FLOW_NODE_PATCH_LW,
                        zorder=2,
                    )
                )
            elif shape == "data":
                skew = 0.14 * w
                ax.add_patch(
                    Polygon(
                        [
                            (cx - w / 2 + skew, cy + h / 2),
                            (cx + w / 2, cy + h / 2),
                            (cx + w / 2 - skew, cy - h / 2),
                            (cx - w / 2, cy - h / 2),
                        ],
                        closed=True,
                        facecolor=FLOW_NODE_FILL,
                        edgecolor=EDGE_NEUTRAL,
                        linewidth=FLOW_NODE_PATCH_LW,
                        zorder=2,
                    )
                )
            else:
                rounding = 0.13 if shape == "start_end" else 0.06
                rect = FancyBboxPatch(
                    (cx - w / 2, cy - h / 2),
                    w,
                    h,
                    boxstyle=f"round,pad=0.04,rounding_size={rounding}",
                    linewidth=FLOW_NODE_PATCH_LW,
                    edgecolor=EDGE_NEUTRAL,
                    facecolor=FLOW_NODE_FILL,
                    zorder=2,
                )
                ax.add_patch(rect)
            fs = max(7, FS_SUBPLOT + fs_delta)
            try:
                ax.text(
                    cx,
                    cy,
                    txt_disp,
                    ha="center",
                    va="center",
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )
            except Exception:
                raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
                txt_fb = _mpl_label(raw_c, use_mathtext=um)
                if not _use_mathtext_effective(um, raw_c):
                    txt_fb = _short_tick_label(txt_fb.replace("\n", " "), max_len=26)
                ax.text(
                    cx,
                    cy,
                    txt_fb,
                    ha="center",
                    va="center",
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )

        for edge in spec.edges:
            s = (edge.source or "").strip()
            t = (edge.target or "").strip()
            if s not in pos or t not in pos:
                continue
            if s == t:
                cx, cy, w, bh = node_boxes[s]
                ax.annotate(
                    "",
                    xy=(cx + w * 0.38, cy + bh * 0.52),
                    xytext=(cx - w * 0.38, cy + bh * 0.52),
                    arrowprops={
                        "arrowstyle": "-|>",
                        "connectionstyle": "arc3,rad=-0.45",
                        "color": ARROW_MUTED,
                        "lw": FLOW_EDGE_LINEWIDTH,
                        "mutation_scale": FLOW_ARROW_MUTATION_SCALE,
                    },
                    zorder=4,
                )
                continue
            x1, y1 = pos[s]
            x2, y2 = pos[t]
            _, _, _, hs = node_boxes[s]
            _, _, _, ht = node_boxes[t]
            shrink_y = 0.2 + 0.018 * max(hs, ht)
            if rank.get(s, 0) < rank.get(t, 0):
                xa, ya = x1, y1 - hs / 2 - shrink_y
                xb, yb = x2, y2 + ht / 2 + shrink_y
            else:
                xa, ya = x1, y1 + hs / 2 + shrink_y
                xb, yb = x2, y2 - ht / 2 - shrink_y
            dx, dy = xb - xa, yb - ya
            dist = math.hypot(dx, dy)
            if dist < 1e-6:
                continue
            ux, uy = dx / dist, dy / dist
            xa2, ya2 = xa + ux * 0.12, ya + uy * 0.12
            xb2, yb2 = xb - ux * 0.12, yb - uy * 0.12
            arr = FancyArrowPatch(
                (xa2, ya2),
                (xb2, yb2),
                arrowstyle="-|>",
                mutation_scale=FLOW_ARROW_MUTATION_SCALE,
                linewidth=FLOW_EDGE_LINEWIDTH,
                color=ARROW_MUTED,
                zorder=1,
            )
            ax.add_patch(arr)
            el = (edge.label or "").strip()
            if el:
                text_with_halo(
                    ax,
                    (xa2 + xb2) / 2 - uy * 0.08,
                    (ya2 + yb2) / 2 + ux * 0.08,
                    _short_tick_label(_mpl_plain(el), 12),
                    fontsize=FS_SMALL - 1,
                    color=TEXT_SECONDARY,
                    bbox_pad=0.1,
                    zorder=5,
                )

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)
        margin_x = max(0.8, max_half_w + 0.5)
        margin_y = 0.75
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        max_h = max((b[3] for b in node_boxes.values()), default=0.42)
        ax.set_xlim(min(xs) - margin_x, max(xs) + margin_x)
        ax.set_ylim(min(ys) - margin_y, max(ys) + margin_y + max_h)
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("_render_flowchart_layered_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_flowchart_to_png_bytes(spec: PracticeFlowchartSpec) -> bytes | None:
    """流程图：layered 自上而下；否则圆周排布。"""
    raw_nodes = [n for n in spec.nodes if (n.id or "").strip()]
    if not raw_nodes:
        return None

    nodes: list[PracticeFlowchartNode] = []
    seen_ids: set[str] = set()
    for n in raw_nodes:
        nid = (n.id or "").strip()
        if nid in seen_ids:
            logger.debug(
                "render_flowchart_to_png_bytes: skip duplicate node id=%s",
                nid,
            )
            continue
        seen_ids.add(nid)
        nodes.append(n)

    if not nodes:
        return None

    if spec.layout == "layered":
        layered_png = _render_flowchart_layered_to_png_bytes(spec, nodes)
        if layered_png is not None:
            return layered_png
        logger.info("render_flowchart_to_png_bytes: layered failed or cyclic, using circular")

    _configure_matplotlib_font()
    try:
        n = len(nodes)
        node_attr_c: dict[str, tuple[float, float, str, bool, str, int, str]] = {}
        for node in nodes:
            nid = (node.id or "").strip()
            raw = (node.text if node else "") or nid
            um = bool(node and node.use_mathtext)
            joined, lines, fs_delta = _flowchart_display_lines(
                raw, use_mathtext=um, fallback_id=nid
            )
            if um:
                txt_disp = _mpl_label(joined, use_mathtext=True)
                if not _use_mathtext_effective(um, joined):
                    txt_disp = _short_tick_label(
                        txt_disp.replace("\n", " "), max_len=26
                    )
                w, h = _flowchart_node_box_dims([txt_disp])
            else:
                txt_disp = joined
                w, h = _flowchart_node_box_dims(lines)
            node_attr_c[nid] = (w, h, raw, um, txt_disp, fs_delta, (node.shape if node else "process"))

        max_box_r = max(
            (0.5 * math.hypot(w, h) for w, h, _, _, _, _, _ in node_attr_c.values()),
            default=0.35,
        )
        R = max(1.42, 0.48 * math.sqrt(float(n)) + 0.92 + 0.35 * max_box_r)
        pos: dict[str, tuple[float, float]] = {}
        for i, node in enumerate(nodes):
            nid = (node.id or "").strip()
            theta = 2 * math.pi * i / n - math.pi / 2
            pos[nid] = (R * math.cos(theta), R * math.sin(theta))

        fig_w = min(8.2, 5.2 + 0.22 * max_box_r)
        fig, ax = plt.subplots(figsize=(fig_w, 4.2), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_aspect("equal", adjustable="datalim")

        node_boxes: dict[str, tuple[float, float, float, float]] = {}
        max_half_w = 0.0
        for nid, (cx, cy) in pos.items():
            w, h, raw, um, txt_disp, fs_delta, shape = node_attr_c[nid]
            max_half_w = max(max_half_w, w / 2.0)
            node_boxes[nid] = (cx, cy, w, h)
            if shape == "decision":
                ax.add_patch(
                    Polygon(
                        [
                            (cx, cy + h / 2),
                            (cx + w / 2, cy),
                            (cx, cy - h / 2),
                            (cx - w / 2, cy),
                        ],
                        closed=True,
                        facecolor=FLOW_NODE_FILL,
                        edgecolor=EDGE_NEUTRAL,
                        linewidth=FLOW_NODE_PATCH_LW,
                        zorder=2,
                    )
                )
            elif shape == "data":
                skew = 0.14 * w
                ax.add_patch(
                    Polygon(
                        [
                            (cx - w / 2 + skew, cy + h / 2),
                            (cx + w / 2, cy + h / 2),
                            (cx + w / 2 - skew, cy - h / 2),
                            (cx - w / 2, cy - h / 2),
                        ],
                        closed=True,
                        facecolor=FLOW_NODE_FILL,
                        edgecolor=EDGE_NEUTRAL,
                        linewidth=FLOW_NODE_PATCH_LW,
                        zorder=2,
                    )
                )
            else:
                rounding = 0.13 if shape == "start_end" else 0.06
                rect = FancyBboxPatch(
                    (cx - w / 2, cy - h / 2),
                    w,
                    h,
                    boxstyle=f"round,pad=0.04,rounding_size={rounding}",
                    linewidth=FLOW_NODE_PATCH_LW,
                    edgecolor=EDGE_NEUTRAL,
                    facecolor=FLOW_NODE_FILL,
                    zorder=2,
                )
                ax.add_patch(rect)
            fs = max(7, FS_SUBPLOT + fs_delta)
            try:
                ax.text(
                    cx,
                    cy,
                    txt_disp,
                    ha="center",
                    va="center",
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )
            except Exception:
                raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
                txt_fb = _mpl_label(raw_c, use_mathtext=um)
                if not _use_mathtext_effective(um, raw_c):
                    txt_fb = _short_tick_label(txt_fb.replace("\n", " "), max_len=26)
                ax.text(
                    cx,
                    cy,
                    txt_fb,
                    ha="center",
                    va="center",
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )

        for edge in spec.edges:
            s = (edge.source or "").strip()
            t = (edge.target or "").strip()
            if s not in pos or t not in pos:
                logger.debug(
                    "render_flowchart_to_png_bytes: skip edge %s -> %s (unknown node)",
                    s,
                    t,
                )
                continue
            x1, y1 = pos[s]
            x2, y2 = pos[t]
            dx = x2 - x1
            dy = y2 - y1
            dist = math.hypot(dx, dy)
            if s == t:
                cx, cy, w, bh = node_boxes[s]
                rad_arc = max(0.38, min(0.85, 0.22 + 0.04 * n))
                ax.annotate(
                    "",
                    xy=(cx + w * 0.38, cy + bh * 0.52),
                    xytext=(cx - w * 0.38, cy + bh * 0.52),
                    arrowprops={
                        "arrowstyle": "-|>",
                        "connectionstyle": f"arc3,rad=-{rad_arc}",
                        "color": ARROW_MUTED,
                        "lw": FLOW_EDGE_LINEWIDTH,
                        "mutation_scale": FLOW_ARROW_MUTATION_SCALE,
                    },
                    zorder=4,
                )
                continue
            if dist < 1e-6:
                continue
            ux, uy = dx / dist, dy / dist
            ws, hs = node_boxes[s][2], node_boxes[s][3]
            wt, ht = node_boxes[t][2], node_boxes[t][3]

            def _circ_pad(wb: float, hb: float) -> float:
                return 0.5 * math.hypot(wb, hb) + 0.1

            shrink_s = _circ_pad(ws, hs)
            shrink_t = _circ_pad(wt, ht)
            xa, ya = x1 + ux * shrink_s, y1 + uy * shrink_s
            xb, yb = x2 - ux * shrink_t, y2 - uy * shrink_t
            arr = FancyArrowPatch(
                (xa, ya),
                (xb, yb),
                arrowstyle="-|>",
                mutation_scale=FLOW_ARROW_MUTATION_SCALE,
                linewidth=FLOW_EDGE_LINEWIDTH,
                color=ARROW_MUTED,
                zorder=1,
            )
            ax.add_patch(arr)
            el = (edge.label or "").strip()
            if el:
                text_with_halo(
                    ax,
                    (xa + xb) / 2 - uy * 0.09,
                    (ya + yb) / 2 + ux * 0.09,
                    _short_tick_label(_mpl_plain(el), 12),
                    fontsize=FS_SMALL - 1,
                    color=TEXT_SECONDARY,
                    bbox_pad=0.1,
                    zorder=5,
                )

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)

        margin = max(0.55, max_half_w + 0.42)
        lim = max(2.05, R + margin + 0.25 * max_box_r)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.axis("off")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_flowchart_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_force_diagram_to_png_bytes(spec: PracticeForceDiagramSpec) -> bytes | None:
    if not spec.forces:
        return None
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(4.9, 3.6), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        forces_render = list(spec.forces)
        show_object = spec.object_style == "block" or bool(spec.object_dot)
        ox, oy = float(spec.object_x), float(spec.object_y)
        if spec.normalize_force_lengths and forces_render:
            if show_object:
                pivot = (ox, oy)
            else:
                n = len(forces_render)
                pivot = (
                    sum(float(f.x0) for f in forces_render) / n,
                    sum(float(f.y0) for f in forces_render) / n,
                )
            lengths = [
                math.hypot(float(f.x1) - float(f.x0), float(f.y1) - float(f.y0))
                for f in forces_render
            ]
            lref = max((L for L in lengths if L > 1e-9), default=1.0)
            nf: list[PracticeForceItem] = []
            for f in forces_render:
                dx = float(f.x1) - float(f.x0)
                dy = float(f.y1) - float(f.y0)
                lg = math.hypot(dx, dy)
                if lg < 1e-9:
                    nf.append(f)
                    continue
                ux, uy = dx / lg, dy / lg
                px, py = pivot
                nf.append(
                    f.model_copy(
                        update={
                            "x0": px,
                            "y0": py,
                            "x1": px + ux * lref,
                            "y1": py + uy * lref,
                        }
                    )
                )
            forces_render = nf

        xs: list[float] = []
        ys: list[float] = []
        for f in forces_render:
            xs.extend([f.x0, f.x1])
            ys.extend([f.y0, f.y1])
        if show_object:
            xs.extend([ox])
            ys.extend([oy])
            if spec.object_style == "block":
                hw, hh = 0.28, 0.22
                ax.add_patch(
                    Rectangle(
                        (ox - hw, oy - hh),
                        2 * hw,
                        2 * hh,
                        facecolor="#e8e8e8",
                        edgecolor=EDGE_NEUTRAL,
                        linewidth=0.95,
                        zorder=1,
                    )
                )
            else:
                ax.scatter(
                    [ox],
                    [oy],
                    s=78,
                    c="#d8d8d8",
                    edgecolors=EDGE_NEUTRAL,
                    linewidths=0.95,
                    zorder=1,
                )

        if spec.show_axes_hint and xs and ys:
            cx = (min(xs) + max(xs)) / 2.0
            cy = (min(ys) + max(ys)) / 2.0
            span_x = max(0.8, (max(xs) - min(xs)) * 1.25 + 0.6)
            span_y = max(0.8, (max(ys) - min(ys)) * 1.25 + 0.6)
            ah_alpha = min(0.88, chart_grid_alpha(textbook=_FIGURE_TEXTBOOK_STYLE) * 1.35)
            ax.axhline(
                cy,
                color=GRID_COLOR,
                linewidth=GRID_LINEWIDTH,
                linestyle=LINE_STYLE_DOT,
                alpha=ah_alpha,
                zorder=Z_GRID,
            )
            ax.axvline(
                cx,
                color=GRID_COLOR,
                linewidth=GRID_LINEWIDTH,
                linestyle=LINE_STYLE_DOT,
                alpha=ah_alpha,
                zorder=Z_GRID,
            )
            xs.extend([cx - span_x, cx + span_x])
            ys.extend([cy - span_y, cy + span_y])

        force_label_entries: list[tuple[float, float, str, str, float]] = []
        for i, f in enumerate(forces_render):
            col = (f.color or "").strip() or PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)]
            z = max(1, min(5, int(f.zorder)))
            x0, y0 = float(f.x0), float(f.y0)
            x1, y1 = float(f.x1), float(f.y1)
            arr = FancyArrowPatch(
                (x0, y0),
                (x1, y1),
                arrowstyle="-|>",
                mutation_scale=FLOW_ARROW_MUTATION_SCALE,
                linewidth=LW_FORCE_ARROW,
                color=col,
                zorder=min(z, Z_ARROW_HIGH),
            )
            ax.add_patch(arr)
            lb = (f.label or "").strip()
            if lb:
                mx = (x0 + x1) / 2.0
                my = (y0 + y1) / 2.0
                dx, dy = x1 - x0, y1 - y0
                lg = math.hypot(dx, dy)
                if lg > 1e-9:
                    px, py = -dy / lg, dx / lg
                else:
                    px, py = 0.0, 1.0
                off = (
                    float(f.label_offset)
                    if f.label_offset is not None
                    else max(0.055 * max((max(xs) - min(xs)), (max(ys) - min(ys)), 1.0), 0.08)
                )
                mx += px * off
                my += py * off
                disp = _mpl_label(lb, use_mathtext=f.use_mathtext)
                if not _use_mathtext_effective(f.use_mathtext, lb):
                    disp = _short_tick_label(disp, 14)
                force_label_entries.append((mx, my, disp, lb, FS_LEGEND))

        if force_label_entries and xs and ys:
            span_lbl = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
            anchors = [(mx, my) for mx, my, *_ in force_label_entries]
            texts = [disp for _mx, _my, disp, _lb, _fs in force_label_entries]
            relaxed = _relax_label_positions(
                anchors,
                texts,
                span_lbl,
                fontsize=FS_LEGEND,
                max_iters=82,
                max_shift=max(0.26 * span_lbl, 0.22),
            )
        else:
            relaxed = [(mx, my) for mx, my, *_ in force_label_entries]

        for (mx, my), (_ax, _ay, disp, lb, fs) in zip(relaxed, force_label_entries):
            try:
                text_with_halo(
                    ax,
                    mx,
                    my,
                    disp,
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    bbox_pad=0.16,
                )
            except Exception:
                text_with_halo(
                    ax,
                    mx,
                    my,
                    _short_tick_label(_mpl_plain(lb), 14),
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    bbox_pad=0.16,
                )

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        if xs and ys:
            pad = max(0.2 * (max(xs) - min(xs) or 1), 0.2 * (max(ys) - min(ys) or 1), 0.35)
            ax.set_xlim(min(xs) - pad, max(xs) + pad)
            ax.set_ylim(min(ys) - pad, max(ys) + pad)
        ax.set_aspect("equal", adjustable="datalim")
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_force_diagram_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _circuit_node_degrees(
    valid_edges,
    id_to_xy: dict[str, tuple[float, float]],
) -> dict[str, int]:
    deg = {nid: 0 for nid in id_to_xy}
    for e in valid_edges:
        s = (e.source or "").strip()
        t = (e.target or "").strip()
        if s in deg:
            deg[s] += 1
        if t in deg:
            deg[t] += 1
    return deg


def _circuit_layout_expand_uniform(
    spec: PracticeCircuitSpec,
    id_to_xy: dict[str, tuple[float, float]],
) -> tuple[dict[str, tuple[float, float]], Callable[[float, float], tuple[float, float]]]:
    """
    若节点与导线折点在数据坐标上过于拥挤，则绕包围盒中心均匀放大。
    不改变拓扑，仅提高符号与导线间距，便于教材式阅读。
    """
    if len(id_to_xy) < 2:

        def _noop(x: float, y: float) -> tuple[float, float]:
            return (x, y)

        return id_to_xy, _noop

    xs = [xy[0] for xy in id_to_xy.values()]
    ys = [xy[1] for xy in id_to_xy.values()]
    bx_lo, bx_hi = min(xs), max(xs)
    by_lo, by_hi = min(ys), max(ys)
    for e in spec.edges:
        s = (e.source or "").strip()
        t = (e.target or "").strip()
        if s not in id_to_xy or t not in id_to_xy:
            continue
        for v in e.via:
            vx, vy = float(v.x), float(v.y)
            bx_lo = min(bx_lo, vx)
            bx_hi = max(bx_hi, vx)
            by_lo = min(by_lo, vy)
            by_hi = max(by_hi, vy)

    span_x = max(bx_hi - bx_lo, 1e-6)
    span_y = max(by_hi - by_lo, 1e-6)
    span = max(span_x, span_y)
    cx = 0.5 * (bx_lo + bx_hi)
    cy = 0.5 * (by_lo + by_hi)
    n = len(id_to_xy)
    target_min = max(3.55, 2.38 + 0.27 * math.sqrt(float(n)))
    scale = max(1.0, target_min / span)
    if scale <= 1.0001:

        def _noop2(x: float, y: float) -> tuple[float, float]:
            return (x, y)

        return id_to_xy, _noop2

    def _tf(x: float, y: float) -> tuple[float, float]:
        return (cx + (x - cx) * scale, cy + (y - cy) * scale)

    out = {nid: _tf(x, y) for nid, (x, y) in id_to_xy.items()}
    return out, _tf


def _circuit_draw_resistor_iec(
    ax,
    mx: float,
    my: float,
    ux: float,
    uy: float,
    px: float,
    py: float,
    g: float,
) -> None:
    """带引脚的 IEC 电阻主体，避免仅在线上叠加锯齿。"""
    lw = CIRCUIT_WIRE_LW * max(CIRCUIT_RESISTOR_LW_FACTOR, 1.02)
    half_body = 0.11 * g
    half_h = 0.05 * g
    lead_outer = 0.18 * g
    _circuit_draw_wire_segment(
        ax,
        mx - ux * lead_outer,
        my - uy * lead_outer,
        mx - ux * half_body,
        my - uy * half_body,
        lw=lw,
    )
    _circuit_draw_wire_segment(
        ax,
        mx + ux * half_body,
        my + uy * half_body,
        mx + ux * lead_outer,
        my + uy * lead_outer,
        lw=lw,
    )
    _circuit_draw_rotated_box(
        ax,
        mx,
        my,
        ux,
        uy,
        half_len=half_body,
        half_h=half_h,
        facecolor="white",
        edgecolor=TEXT_PRIMARY,
        linewidth=max(CIRCUIT_SYMBOL_LINEWIDTH, lw * 0.9),
        zorder=Z_SYMBOL_GEOM,
    )
    for frac in (-0.46, 0.0, 0.46):
        cx = mx + ux * (frac * half_body * 1.35)
        cy = my + uy * (frac * half_body * 1.35)
        _circuit_draw_wire_segment(
            ax,
            cx - px * half_h * 0.6,
            cy - py * half_h * 0.6,
            cx + px * half_h * 0.6,
            cy + py * half_h * 0.6,
            lw=max(0.78, lw * 0.6),
        )


def _circuit_draw_wire_segment(
    ax,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    lw: float = LW_CIRCUIT_WIRE,
) -> None:
    ax.plot(
        [x0, x1],
        [y0, y1],
        color=TEXT_PRIMARY,
        linewidth=lw,
        solid_capstyle=TECH_LINE_CAPSTYLE,
        solid_joinstyle=TECH_LINE_JOINSTYLE,
        zorder=Z_WIRE,
    )


def _circuit_plot_wire_polyline(ax, pts: list[tuple[float, float]], *, lw: float = LW_CIRCUIT_WIRE) -> None:
    if len(pts) < 2:
        return
    ax.plot(
        [p[0] for p in pts],
        [p[1] for p in pts],
        color=TEXT_PRIMARY,
        linewidth=lw,
        solid_capstyle=TECH_LINE_CAPSTYLE,
        solid_joinstyle=TECH_LINE_JOINSTYLE,
        zorder=Z_WIRE,
    )


def _circuit_draw_rotated_box(
    ax,
    mx: float,
    my: float,
    ux: float,
    uy: float,
    *,
    half_len: float,
    half_h: float,
    facecolor: str,
    edgecolor: str,
    linewidth: float,
    zorder: float,
) -> None:
    px, py = -uy, ux
    corners = [
        (mx - ux * half_len - px * half_h, my - uy * half_len - py * half_h),
        (mx + ux * half_len - px * half_h, my + uy * half_len - py * half_h),
        (mx + ux * half_len + px * half_h, my + uy * half_len + py * half_h),
        (mx - ux * half_len + px * half_h, my - uy * half_len + py * half_h),
    ]
    ax.add_patch(
        Polygon(
            corners,
            closed=True,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            zorder=zorder,
        )
    )


def _circuit_symbol_span(el: str, g: float, *, switch_state: str = "default") -> float:
    el = (el or "wire").strip().lower()
    if el == "wire":
        return 0.0
    spans = {
        "resistor": 0.40 * g,
        "cell": 0.24 * g,
        "battery": 0.34 * g,
        "capacitor": 0.22 * g,
        "lamp": 0.24 * g,
        "switch": (0.30 if switch_state == "open" else 0.24) * g,
        "rheostat": 0.40 * g,
        "fuse": 0.24 * g,
        "diode": 0.24 * g,
        "ammeter": 0.28 * g,
        "voltmeter": 0.28 * g,
        "generic": 0.20 * g,
    }
    return spans.get(el, 0.20 * g)


def _circuit_pick_symbol_segment(
    pts: list[tuple[float, float]],
) -> tuple[int, float, float, float, float, float, float, float, float, float] | None:
    best_i = -1
    best_len = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len > best_len:
            best_i = i
            best_len = seg_len
    if best_i < 0 or best_len < 1e-9:
        return None
    x0, y0 = pts[best_i]
    x1, y1 = pts[best_i + 1]
    ux = (x1 - x0) / best_len
    uy = (y1 - y0) / best_len
    mx = (x0 + x1) / 2.0
    my = (y0 + y1) / 2.0
    return best_i, x0, y0, x1, y1, mx, my, ux, uy, best_len


def _circuit_node_label_xy(
    x: float,
    y: float,
    cx: float,
    cy: float,
    span: float,
    idx: int,
    *,
    label_text: str = "",
) -> tuple[float, float]:
    """沿图心径向外推节点标签，并交替侧向偏移；长中文再外移一点。"""
    dx, dy = x - cx, y - cy
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        ux, uy = 0.0, -1.0
    else:
        ux, uy = dx / dist, dy / dist
    eff = 0.0
    for c in label_text:
        if "\u4e00" <= c <= "\u9fff":
            eff += 1.35
        else:
            eff += 1.0
    eff = max(eff, float(len(label_text)))
    scale = 1.0 + 0.028 * max(0.0, eff - 2.5)
    base = max(0.092 * span, 0.15) * min(scale, 1.52)
    px, py = -uy, ux
    side = (0.038 * span) * (1.0 if (idx % 2) == 0 else -1.0)
    ring = (idx % 6) * 0.012 * span
    return (
        x + ux * (base + ring) + px * side,
        y + uy * (base + ring) + py * side,
    )


def _circuit_label_data_half_extents(
    span: float, text: str, *, compact: bool = False
) -> tuple[float, float]:
    """标签在数据坐标下近似半宽/半高，用于碰撞分离（略偏大，减少假阴性重叠）。"""
    if compact:
        half_w = max(0.036 * span, 0.062)
        half_h = max(0.034 * span, 0.06)
        return half_w, half_h
    eff = 0.0
    for c in text:
        if "\u4e00" <= c <= "\u9fff":
            eff += 2.15
        else:
            eff += 1.18
    eff = max(eff, float(len(text)) * 1.0)
    half_w = max(0.044 * span, 0.0082 * span * eff)
    half_h = max(0.038 * span, 0.052 * span * 0.58)
    return half_w, half_h


def _circuit_node_dot_radius(nid: str, deg: dict[str, int], span: float) -> float:
    d = deg.get(nid, 0)
    if d >= 3:
        return max(0.014 * span, 0.055)
    return max(0.009 * span, 0.042)


def _circuit_relax_annotation_layout(
    positions: list[list[float]],
    half_sizes: list[tuple[float, float]],
    anchors0: list[tuple[float, float]],
    span: float,
    *,
    id_to_xy: dict[str, tuple[float, float]],
    deg: dict[str, int],
    meter_centers: list[tuple[float, float]],
    g: float,
    max_iters: int = 168,
) -> None:
    """
    节点标签 + 电表文字统一做动态避碰：标签-标签分离、标签-结点圆分离、
    标签-电表圆分离，并限制相对初始位置的漂移，避免跑飞。
    """
    n = len(positions)
    if n < 1:
        return
    margin = 0.041 * span
    step = 0.02 * span
    max_shift = max(0.88 * span, 0.48)
    meter_r = max(0.082 * g, 0.036 * span)
    node_items = list(id_to_xy.items())

    for _ in range(max_iters):
        for i in range(n):
            for j in range(i + 1, n):
                x1, y1 = positions[i][0], positions[i][1]
                x2, y2 = positions[j][0], positions[j][1]
                w1, h1 = half_sizes[i]
                w2, h2 = half_sizes[j]
                overlap_x = w1 + w2 + margin - abs(x1 - x2)
                overlap_y = h1 + h2 + margin - abs(y1 - y2)
                if overlap_x <= 0 or overlap_y <= 0:
                    continue
                dx, dy = x2 - x1, y2 - y1
                d = math.hypot(dx, dy)
                if d < 1e-9:
                    ang = 0.73 * (i + 2 * j + 1)
                    dx, dy = math.cos(ang), math.sin(ang)
                    d = 1.0
                push = (max(overlap_x, overlap_y) * 0.5 + step) / d
                fx, fy = dx * push, dy * push
                positions[i][0] -= fx * 0.5
                positions[i][1] -= fy * 0.5
                positions[j][0] += fx * 0.5
                positions[j][1] += fy * 0.5

        for i in range(n):
            lx, ly = positions[i][0], positions[i][1]
            hw, hh = half_sizes[i]
            lab_r = math.hypot(hw, hh) * 0.95
            for nid, (nx, ny) in node_items:
                dx, dy = lx - nx, ly - ny
                dist = math.hypot(dx, dy)
                if dist < 1e-9:
                    dx, dy = 1.0, 0.0
                    dist = 1.0
                need = _circuit_node_dot_radius(nid, deg, span) + lab_r + 0.028 * span
                if dist < need:
                    push = (need - dist) * 0.4
                    positions[i][0] += push * dx / dist
                    positions[i][1] += push * dy / dist

            for mx, my in meter_centers:
                dx, dy = lx - mx, ly - my
                dist = math.hypot(dx, dy)
                if dist < 1e-9:
                    continue
                need = meter_r + lab_r + 0.022 * span
                if dist < need:
                    push = (need - dist) * 0.38
                    positions[i][0] += push * dx / dist
                    positions[i][1] += push * dy / dist

        for i in range(n):
            x0, y0 = anchors0[i]
            dx = positions[i][0] - x0
            dy = positions[i][1] - y0
            dd = math.hypot(dx, dy)
            if dd > max_shift and dd > 1e-9:
                positions[i][0] = x0 + dx * max_shift / dd
                positions[i][1] = y0 + dy * max_shift / dd


def _circuit_edge_polyline(
    spec: PracticeCircuitSpec,
    e,
    id_to_xy: dict[str, tuple[float, float]],
    *,
    via_transform: Callable[[float, float], tuple[float, float]] | None = None,
) -> list[tuple[float, float]] | None:
    s = (e.source or "").strip()
    t = (e.target or "").strip()
    if s not in id_to_xy or t not in id_to_xy:
        return None
    pts: list[tuple[float, float]] = [id_to_xy[s]]
    for v in e.via:
        vx, vy = float(v.x), float(v.y)
        if via_transform is not None:
            vx, vy = via_transform(vx, vy)
        pts.append((vx, vy))
    pts.append(id_to_xy[t])
    return pts


def _circuit_draw_symbol(
    ax,
    el: str,
    mx: float,
    my: float,
    ux: float,
    uy: float,
    g: float,
    *,
    switch_state: str = "default",
    slider_position: float | None = None,
    dual_meter_layout: bool = False,
    meter_labels: list[tuple[float, float, str, float, float]] | None = None,
) -> None:
    px, py = -uy, ux
    el = (el or "wire").strip().lower()
    if el == "wire":
        return
    if el == "resistor":
        _circuit_draw_resistor_iec(ax, mx, my, ux, uy, px, py, g)
        return
    if el == "cell":
        lead_outer = 0.14 * g
        plate_gap = 0.04 * g
        long_e = 0.098 * g
        short_e = 0.054 * g
        mx1, my1 = mx - ux * plate_gap, my - uy * plate_gap
        mx2, my2 = mx + ux * plate_gap, my + uy * plate_gap
        lw_cell = max(CIRCUIT_SYMBOL_LINEWIDTH, LW_CIRCUIT_WIRE * 0.95)
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx1,
            my1,
            lw=lw_cell,
        )
        _circuit_draw_wire_segment(
            ax,
            mx2,
            my2,
            mx + ux * lead_outer,
            my + uy * lead_outer,
            lw=lw_cell,
        )
        ax.plot(
            [mx1 - px * long_e, mx1 + px * long_e],
            [my1 - py * long_e, my1 + py * long_e],
            color=TEXT_PRIMARY,
            lw=lw_cell,
            solid_capstyle=TECH_LINE_CAPSTYLE,
            solid_joinstyle=TECH_LINE_JOINSTYLE,
            zorder=Z_SYMBOL_GEOM,
        )
        ax.plot(
            [mx2 - px * short_e, mx2 + px * short_e],
            [my2 - py * short_e, my2 + py * short_e],
            color=TEXT_PRIMARY,
            lw=lw_cell,
            solid_capstyle=TECH_LINE_CAPSTYLE,
            solid_joinstyle=TECH_LINE_JOINSTYLE,
            zorder=Z_SYMBOL_GEOM,
        )
        return
    if el == "battery":
        lead_outer = 0.20 * g
        plate_pos = (-0.09 * g, -0.03 * g, 0.03 * g, 0.09 * g)
        plate_half = (0.055 * g, 0.10 * g, 0.055 * g, 0.10 * g)
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx + ux * plate_pos[0],
            my + uy * plate_pos[0],
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * plate_pos[-1],
            my + uy * plate_pos[-1],
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        for along, half in zip(plate_pos, plate_half, strict=False):
            cx = mx + ux * along
            cy = my + uy * along
            ax.plot(
                [cx - px * half, cx + px * half],
                [cy - py * half, cy + py * half],
                color=TEXT_PRIMARY,
                lw=max(CIRCUIT_SYMBOL_LINEWIDTH, 1.0),
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=Z_SYMBOL_GEOM,
            )
        return
    if el == "lamp":
        radius = 0.082 * g
        lead_outer = 0.18 * g
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx - ux * radius,
            my - uy * radius,
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * radius,
            my + uy * radius,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        ax.add_patch(
            Circle(
                (mx, my),
                radius,
                facecolor="white",
                edgecolor=TEXT_PRIMARY,
                linewidth=CIRCUIT_SYMBOL_LINEWIDTH,
                zorder=Z_SYMBOL_GEOM,
            )
        )
        _circuit_draw_wire_segment(
            ax,
            mx - ux * radius * 0.5 - px * radius * 0.5,
            my - uy * radius * 0.5 - py * radius * 0.5,
            mx + ux * radius * 0.5 + px * radius * 0.5,
            my + uy * radius * 0.5 + py * radius * 0.5,
            lw=max(0.75, CIRCUIT_SYMBOL_LINEWIDTH * 0.9),
        )
        _circuit_draw_wire_segment(
            ax,
            mx - ux * radius * 0.5 + px * radius * 0.5,
            my - uy * radius * 0.5 + py * radius * 0.5,
            mx + ux * radius * 0.5 - px * radius * 0.5,
            my + uy * radius * 0.5 - py * radius * 0.5,
            lw=max(0.75, CIRCUIT_SYMBOL_LINEWIDTH * 0.9),
        )
        return
    if el == "switch":
        lead_outer = 0.17 * g
        contact_off = 0.072 * g
        contact_r = max(0.011 * g, 0.018)
        lx, ly = mx - ux * contact_off, my - uy * contact_off
        rx, ry = mx + ux * contact_off, my + uy * contact_off
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            lx,
            ly,
        )
        _circuit_draw_wire_segment(
            ax,
            rx,
            ry,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        for cx, cy in ((lx, ly), (rx, ry)):
            ax.add_patch(
                Circle(
                    (cx, cy),
                    contact_r,
                    facecolor="white",
                    edgecolor=TEXT_PRIMARY,
                    linewidth=max(0.9, CIRCUIT_SYMBOL_LINEWIDTH * 0.9),
                    zorder=Z_SYMBOL_GEOM,
                )
            )
        state = (switch_state or "default").strip().lower()
        if state == "closed":
            _circuit_draw_wire_segment(
                ax,
                lx + ux * contact_r * 0.2,
                ly + uy * contact_r * 0.2,
                rx - ux * contact_r * 0.2,
                ry - uy * contact_r * 0.2,
                lw=max(1.0, CIRCUIT_SYMBOL_LINEWIDTH),
            )
            _circuit_draw_wire_segment(
                ax,
                mx - px * 0.045 * g,
                my - py * 0.045 * g,
                mx + px * 0.045 * g,
                my + py * 0.045 * g,
                lw=max(0.75, CIRCUIT_SYMBOL_LINEWIDTH * 0.72),
            )
        else:
            _circuit_draw_wire_segment(
                ax,
                lx,
                ly,
                rx - ux * contact_r * 1.2 + px * 0.055 * g,
                ry - uy * contact_r * 1.2 + py * 0.055 * g,
                lw=max(0.95, CIRCUIT_SYMBOL_LINEWIDTH),
            )
        return
    if el == "rheostat":
        _circuit_draw_resistor_iec(ax, mx, my, ux, uy, px, py, g)
        t = 0.62 if slider_position is None else min(1.0, max(0.0, float(slider_position)))
        along = (t - 0.5) * 0.22 * g
        tip_x = mx + ux * along
        tip_y = my + uy * along
        start_x = tip_x - px * 0.12 * g - ux * 0.08 * g
        start_y = tip_y - py * 0.12 * g - uy * 0.08 * g
        ax.add_patch(
            FancyArrowPatch(
                (start_x, start_y),
                (tip_x, tip_y),
                arrowstyle="-|>",
                mutation_scale=11,
                linewidth=max(0.9, CIRCUIT_SYMBOL_LINEWIDTH * 0.9),
                color=TEXT_PRIMARY,
                zorder=Z_SYMBOL_GEOM + 0.2,
            )
        )
        return
    if el == "fuse":
        lead_outer = 0.17 * g
        half_body = 0.07 * g
        half_h = 0.032 * g
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx - ux * half_body,
            my - uy * half_body,
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * half_body,
            my + uy * half_body,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        _circuit_draw_rotated_box(
            ax,
            mx,
            my,
            ux,
            uy,
            half_len=half_body,
            half_h=half_h,
            facecolor="white",
            edgecolor=TEXT_PRIMARY,
            linewidth=max(0.9, CIRCUIT_SYMBOL_LINEWIDTH),
            zorder=Z_SYMBOL_GEOM,
        )
        _circuit_draw_wire_segment(
            ax,
            mx - ux * half_body * 0.72,
            my - uy * half_body * 0.72,
            mx + ux * half_body * 0.72,
            my + uy * half_body * 0.72,
            lw=max(0.75, CIRCUIT_SYMBOL_LINEWIDTH * 0.75),
        )
        return
    if el == "diode":
        lead_outer = 0.17 * g
        tri_back = 0.075 * g
        tri_half_h = 0.055 * g
        bar_off = 0.04 * g
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx - ux * tri_back,
            my - uy * tri_back,
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * bar_off,
            my + uy * bar_off,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        tri_pts = [
            (mx - ux * tri_back - px * tri_half_h, my - uy * tri_back - py * tri_half_h),
            (mx - ux * tri_back + px * tri_half_h, my - uy * tri_back + py * tri_half_h),
            (mx + ux * bar_off * 0.55, my + uy * bar_off * 0.55),
        ]
        ax.add_patch(
            Polygon(
                tri_pts,
                closed=True,
                facecolor="white",
                edgecolor=TEXT_PRIMARY,
                linewidth=max(0.9, CIRCUIT_SYMBOL_LINEWIDTH),
                zorder=Z_SYMBOL_GEOM,
            )
        )
        ax.plot(
            [mx + ux * bar_off - px * tri_half_h, mx + ux * bar_off + px * tri_half_h],
            [my + uy * bar_off - py * tri_half_h, my + uy * bar_off + py * tri_half_h],
            color=TEXT_PRIMARY,
            lw=max(1.0, CIRCUIT_SYMBOL_LINEWIDTH),
            solid_capstyle=TECH_LINE_CAPSTYLE,
            solid_joinstyle=TECH_LINE_JOINSTYLE,
            zorder=Z_SYMBOL_GEOM,
        )
        return
    if el == "ammeter":
        radius = (0.088 if dual_meter_layout else 0.083) * g
        lead_outer = 0.18 * g
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx - ux * radius,
            my - uy * radius,
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * radius,
            my + uy * radius,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        ax.add_patch(
            Circle(
                (mx, my),
                radius,
                facecolor="white",
                edgecolor=TEXT_PRIMARY,
                linewidth=max(CIRCUIT_SYMBOL_LINEWIDTH, 1.1),
                zorder=Z_SYMBOL_GEOM,
            )
        )
        ax.add_patch(
            Arc(
                (mx, my + radius * 0.02),
                radius * 1.15,
                radius * 0.92,
                theta1=200,
                theta2=340,
                edgecolor=TEXT_PRIMARY,
                linewidth=0.7,
                zorder=Z_SYMBOL_GEOM + 0.1,
            )
        )
        _circuit_draw_wire_segment(
            ax,
            mx - radius * 0.05,
            my - radius * 0.05,
            mx + radius * 0.26,
            my + radius * 0.22,
            lw=0.8,
        )
        ax.add_patch(
            Circle(
                (mx, my),
                radius * 0.82,
                fill=False,
                edgecolor=TEXT_PRIMARY,
                linewidth=0.75,
                zorder=Z_SYMBOL_GEOM + 0.1,
            )
        )
        ax.text(
            mx,
            my,
            "A",
            ha="center",
            va="center",
            fontsize=FS_CIRCUIT_SYMBOL + 0.6,
            color=TEXT_PRIMARY,
            weight="bold",
            zorder=Z_LABEL_TEXT,
        )
        return
    if el == "voltmeter":
        radius = (0.088 if dual_meter_layout else 0.083) * g
        lead_outer = 0.18 * g
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx - ux * radius,
            my - uy * radius,
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * radius,
            my + uy * radius,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        ax.add_patch(
            Circle(
                (mx, my),
                radius,
                facecolor="white",
                edgecolor=TEXT_PRIMARY,
                linewidth=max(CIRCUIT_SYMBOL_LINEWIDTH, 1.1),
                zorder=Z_SYMBOL_GEOM,
            )
        )
        ax.add_patch(
            Arc(
                (mx, my + radius * 0.02),
                radius * 1.15,
                radius * 0.92,
                theta1=200,
                theta2=340,
                edgecolor=TEXT_PRIMARY,
                linewidth=0.7,
                zorder=Z_SYMBOL_GEOM + 0.1,
            )
        )
        _circuit_draw_wire_segment(
            ax,
            mx + radius * 0.04,
            my - radius * 0.06,
            mx - radius * 0.24,
            my + radius * 0.20,
            lw=0.8,
        )
        ax.add_patch(
            Circle(
                (mx, my),
                radius * 0.82,
                fill=False,
                edgecolor=TEXT_PRIMARY,
                linewidth=0.75,
                zorder=Z_SYMBOL_GEOM + 0.1,
            )
        )
        ax.text(
            mx,
            my,
            "V",
            ha="center",
            va="center",
            fontsize=FS_CIRCUIT_SYMBOL + 0.6,
            color=TEXT_PRIMARY,
            weight="bold",
            zorder=Z_LABEL_TEXT,
        )
        return
    if el == "capacitor":
        lead_outer = 0.15 * g
        gap = 0.042 * g
        half = 0.068 * g
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx - ux * gap,
            my - uy * gap,
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * gap,
            my + uy * gap,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        for sgn in (-1.0, 1.0):
            cx = mx + ux * gap * sgn
            cy = my + uy * gap * sgn
            ax.plot(
                [cx - px * half, cx + px * half],
                [cy - py * half, cy + py * half],
                color=TEXT_PRIMARY,
                lw=CIRCUIT_WIRE_LW,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=Z_SYMBOL_GEOM,
            )
        return
    if el == "generic":
        lead_outer = 0.16 * g
        half_body = 0.07 * g
        _circuit_draw_wire_segment(
            ax,
            mx - ux * lead_outer,
            my - uy * lead_outer,
            mx - ux * half_body,
            my - uy * half_body,
        )
        _circuit_draw_wire_segment(
            ax,
            mx + ux * half_body,
            my + uy * half_body,
            mx + ux * lead_outer,
            my + uy * lead_outer,
        )
        _circuit_draw_rotated_box(
            ax,
            mx,
            my,
            ux,
            uy,
            half_len=half_body,
            half_h=0.05 * g,
            facecolor="white",
            edgecolor=EDGE_NEUTRAL,
            linewidth=CIRCUIT_SYMBOL_LINEWIDTH,
            zorder=Z_SYMBOL_GEOM,
        )
        return
    ax.add_patch(
        Rectangle(
            (mx - 0.06 * g, my - 0.05 * g),
            0.12 * g,
            0.1 * g,
            facecolor="#e2e2e2",
            edgecolor=EDGE_NEUTRAL,
            linewidth=CIRCUIT_SYMBOL_LINEWIDTH,
            zorder=Z_SYMBOL_GEOM,
        )
    )


def render_circuit_simple_to_png_bytes(spec: PracticeCircuitSpec) -> bytes | None:
    id_to_xy: dict[str, tuple[float, float]] = {}
    for n in spec.nodes:
        nid = (n.id or "").strip()
        if not nid:
            continue
        id_to_xy[nid] = (float(n.x), float(n.y))
    if len(id_to_xy) < 2:
        return None
    id_to_xy, via_transform = _circuit_layout_expand_uniform(spec, id_to_xy)
    valid_edges = [e for e in spec.edges if _circuit_edge_polyline(spec, e, id_to_xy, via_transform=via_transform)]
    if not valid_edges:
        return None
    dual_meter_layout = sum(
        1 for e in valid_edges if (e.element or "").strip().lower() in {"ammeter", "voltmeter"}
    ) >= 2

    _configure_matplotlib_font()
    try:
        n_nodes = len(id_to_xy)
        xs0 = [xy[0] for xy in id_to_xy.values()]
        ys0 = [xy[1] for xy in id_to_xy.values()]
        span_pre = max(max(xs0) - min(xs0), max(ys0) - min(ys0), 1e-6)
        fig_w = min(10.8, 4.65 + 0.26 * span_pre + 0.042 * float(n_nodes))
        fig_h = min(7.85, 3.35 + 0.23 * span_pre + 0.052 * float(n_nodes))
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        xs = [xy[0] for xy in id_to_xy.values()]
        ys = [xy[1] for xy in id_to_xy.values()]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)

        # 范围纳入全部导线折点，避免仅按节点包盒时边、电表被裁切
        bx_lo, bx_hi = min(xs), max(xs)
        by_lo, by_hi = min(ys), max(ys)
        for e in valid_edges:
            pts = _circuit_edge_polyline(spec, e, id_to_xy, via_transform=via_transform)
            if not pts:
                continue
            for px, py in pts:
                bx_lo = min(bx_lo, px)
                bx_hi = max(bx_hi, px)
                by_lo = min(by_lo, py)
                by_hi = max(by_hi, py)
        span_x = max(bx_hi - bx_lo, 1e-6)
        span_y = max(by_hi - by_lo, 1e-6)
        span = max(span_x, span_y, span)
        g = span * 0.35
        deg = _circuit_node_degrees(valid_edges, id_to_xy)
        component_label_map = {
            "resistor": "R",
            "cell": "E",
            "battery": "B",
            "capacitor": "C",
            "switch": "K",
            "rheostat": "R~",
            "fuse": "FU",
            "diode": "D",
            "lamp": "L",
        }

        meter_labels: list[tuple[float, float, str, float, float]] = []
        component_labels: list[tuple[float, float, str]] = []
        for e in valid_edges:
            pts = _circuit_edge_polyline(spec, e, id_to_xy, via_transform=via_transform)
            if not pts or len(pts) < 2:
                continue
            el = (e.element or "wire").strip().lower()
            picked = _circuit_pick_symbol_segment(pts)
            if picked is None or el == "wire":
                _circuit_plot_wire_polyline(ax, pts)
                continue
            i0, _x0, _y0, _x1, _y1, mx, my, ux, uy, seg_len = picked
            gap = min(_circuit_symbol_span(el, g, switch_state=e.switch_state), seg_len * 0.72)
            if gap <= 1e-6:
                _circuit_plot_wire_polyline(ax, pts)
                continue
            gap_half = gap / 2.0
            gap_start = (mx - ux * gap_half, my - uy * gap_half)
            gap_end = (mx + ux * gap_half, my + uy * gap_half)
            before = pts[: i0 + 1] + [gap_start]
            after = [gap_end] + pts[i0 + 1 :]
            _circuit_plot_wire_polyline(ax, before)
            _circuit_plot_wire_polyline(ax, after)
            _circuit_draw_symbol(
                ax,
                el,
                mx,
                my,
                ux,
                uy,
                g,
                switch_state=e.switch_state,
                slider_position=e.slider_position,
                dual_meter_layout=dual_meter_layout,
                meter_labels=meter_labels,
            )
            user_tag = (e.label or "").strip()
            tag = _short_tick_label(user_tag, 10) if user_tag else component_label_map.get(el)
            if tag:
                px, py = -uy, ux
                component_labels.append(
                    (
                        mx + px * max(0.17 * g, 0.095),
                        my + py * max(0.17 * g, 0.095),
                        tag,
                    )
                )

        for nid, (x, y) in id_to_xy.items():
            d = deg.get(nid, 0)
            if d >= 3:
                rj = max(0.014 * span, 0.055)
                ax.add_patch(
                    Circle(
                        (x, y),
                        rj,
                        facecolor=TEXT_PRIMARY,
                        edgecolor=TEXT_PRIMARY,
                        linewidth=0,
                        zorder=Z_CIRCUIT_JUNCTION,
                    )
                )
            else:
                rn = max(0.009 * span, 0.042)
                ax.add_patch(
                    Circle(
                        (x, y),
                        rn,
                        facecolor="white",
                        edgecolor=TEXT_PRIMARY,
                        linewidth=CIRCUIT_JUNCTION_OUTLINE_LW,
                        zorder=Z_SCATTER_POINT,
                    )
                )

        meter_off = max(0.112 * g, 0.128 * span)
        cx_m = sum(xs) / max(len(xs), 1)
        cy_m = sum(ys) / max(len(ys), 1)
        sorted_nodes = sorted(id_to_xy.items(), key=lambda kv: kv[0])
        labels_text = [
            _short_tick_label(circuit_node_label_for_display(nid), max_len=12)
            for nid, _ in sorted_nodes
        ]
        meter_centers = [(float(mx), float(my)) for mx, my, *_ in meter_labels]

        all_pos: list[list[float]] = []
        all_half: list[tuple[float, float]] = []
        anchors0: list[tuple[float, float]] = []

        for mx, my, ch, mux, muy in meter_labels:
            px_m, py_m = -muy, mux
            lx = mx + px_m * meter_off
            ly = my + py_m * meter_off
            all_pos.append([lx, ly])
            all_half.append(_circuit_label_data_half_extents(span, ch, compact=True))
            anchors0.append((lx, ly))
        for lx, ly, ch in component_labels:
            all_pos.append([lx, ly])
            all_half.append(_circuit_label_data_half_extents(span, ch, compact=True))
            anchors0.append((lx, ly))

        for i, (_, (x, y)) in enumerate(sorted_nodes):
            lx, ly = _circuit_node_label_xy(
                x,
                y,
                cx_m,
                cy_m,
                span,
                i,
                label_text=labels_text[i],
            )
            all_pos.append([lx, ly])
            all_half.append(
                _circuit_label_data_half_extents(span, labels_text[i], compact=False)
            )
            anchors0.append((float(lx), float(ly)))

        _circuit_relax_annotation_layout(
            all_pos,
            all_half,
            anchors0,
            span,
            id_to_xy=id_to_xy,
            deg=deg,
            meter_centers=meter_centers,
            g=g,
        )

        nm = len(meter_labels)
        for mi, (_mx, _my, ch, _mux, _muy) in enumerate(meter_labels):
            lx, ly = all_pos[mi][0], all_pos[mi][1]
            text_with_halo(
                ax,
                lx,
                ly,
                ch,
                fontsize=FS_CIRCUIT_SYMBOL + 1.5,
                color=TEXT_PRIMARY,
                weight="bold",
                bbox_pad=0.14,
                zorder=Z_LABEL_TEXT,
            )
        nc = len(component_labels)
        for ci, (_lx, _ly, ch) in enumerate(component_labels):
            lx, ly = all_pos[nm + ci][0], all_pos[nm + ci][1]
            text_with_halo(
                ax,
                lx,
                ly,
                ch,
                fontsize=FS_CIRCUIT_SYMBOL - 0.2,
                color=TEXT_SECONDARY,
                weight="bold",
                bbox_pad=0.1,
                zorder=Z_LABEL_TEXT,
            )
        for i, (_nid, (_nx, _ny)) in enumerate(sorted_nodes):
            idx = nm + nc + i
            lx, ly = all_pos[idx][0], all_pos[idx][1]
            disp_nid = labels_text[i]
            pad = 0.12 if len(disp_nid) <= 2 else 0.16
            text_with_halo(
                ax,
                lx,
                ly,
                disp_nid,
                ha="center",
                va="center",
                fontsize=FS_CIRCUIT_SYMBOL + 0.5,
                color=TEXT_SECONDARY,
                weight="bold",
                bbox_pad=pad,
                zorder=Z_LABEL_TEXT,
            )

        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        # 数据坐标留白：比例 + 下限，并额外为节点下方标签留高
        pad_xy = max(0.27 * span + 0.52, 0.62 * max(1.0, span / 3.0))
        pad_bottom = pad_xy + max(0.15 * span, 0.34)
        pad_top = pad_xy + max(0.10 * span, 0.28)
        ax.set_xlim(bx_lo - pad_xy, bx_hi + pad_xy)
        ax.set_ylim(by_lo - pad_bottom, by_hi + pad_top)
        # box：在等比例下调整轴框而非收缩数据范围，减少「挤爆」裁切
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        fig.tight_layout(pad=1.38)
        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=_FIG_DPI,
            bbox_inches="tight",
            pad_inches=0.46,
            facecolor="white",
        )
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_circuit_simple_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _project_solid_vertex(spec: PracticeSolidWireframeSpec, vx: float, vy: float, vz: float) -> tuple[float, float]:
    if spec.projection == "cabinet":
        return project_vertex_cabinet(vx, vy, vz)
    if spec.projection == "oblique":
        return project_vertex_oblique_pep(vx, vy, vz)
    return project_vertex_isometric(vx, vy, vz)


def render_solid_wireframe_to_png_bytes(spec: PracticeSolidWireframeSpec) -> bytes | None:
    if len(spec.vertices) < 2 or not spec.edges:
        return None
    id_to_v3 = {v.id: (float(v.x), float(v.y), float(v.z)) for v in spec.vertices}
    id_to_2d: dict[str, tuple[float, float]] = {}
    for vid, t in id_to_v3.items():
        id_to_2d[vid] = _project_solid_vertex(spec, t[0], t[1], t[2])

    def face_depth(vids: list[str]) -> float:
        s = 0.0
        for vid in vids:
            if vid in id_to_v3:
                s += id_to_v3[vid][2]
        return s / max(1, len(vids))

    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.2, 4.2), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        faces_sorted = sorted(spec.faces, key=lambda f: face_depth(f.vertex_ids), reverse=True)
        for f in faces_sorted:
            xs = []
            ys = []
            for vid in f.vertex_ids:
                if vid in id_to_2d:
                    xs.append(id_to_2d[vid][0])
                    ys.append(id_to_2d[vid][1])
            if len(xs) < 3:
                continue
            fc = (f.fill_color or "").strip() or GEOM_FILL_DEFAULT
            ec = (f.edge_color or "").strip() or EDGE_NEUTRAL
            poly = Polygon(
                list(zip(xs, ys)),
                closed=True,
                facecolor=fc,
                edgecolor=ec,
                linewidth=LW_GEOM * SCHEMATIC_FACE_EDGE_LW_SCALE,
                alpha=_clamp_alpha(f.alpha, _GEOM_POLY_ALPHA_LO, _GEOM_POLY_ALPHA_HI),
                zorder=1,
            )
            ax.add_patch(poly)

        sec_sorted = sorted(spec.section_faces, key=lambda f: face_depth(f.vertex_ids), reverse=True)
        for f in sec_sorted:
            xs = []
            ys = []
            for vid in f.vertex_ids:
                if vid in id_to_2d:
                    xs.append(id_to_2d[vid][0])
                    ys.append(id_to_2d[vid][1])
            if len(xs) < 3:
                continue
            fc = (f.fill_color or "").strip() or GEOM_FILL_DEFAULT
            ec = (f.edge_color or "").strip() or TEXT_PRIMARY
            poly = Polygon(
                list(zip(xs, ys)),
                closed=True,
                facecolor=fc,
                edgecolor=ec,
                linewidth=LW_GEOM * SCHEMATIC_SECTION_EDGE_LW_SCALE,
                alpha=_clamp_alpha(max(f.alpha, 0.45), _GEOM_POLY_ALPHA_LO, _GEOM_POLY_ALPHA_HI),
                zorder=2,
            )
            ax.add_patch(poly)

        def _edge_depth(aid: str, bid: str) -> float:
            za = id_to_v3.get(aid, (0.0, 0.0, 0.0))[2]
            zb = id_to_v3.get(bid, (0.0, 0.0, 0.0))[2]
            return (za + zb) / 2.0

        edges_sorted = sorted(
            spec.edges,
            key=lambda e: _edge_depth((e.a or "").strip(), (e.b or "").strip()),
            reverse=True,
        )
        if edges_sorted:
            dvals = [
                _edge_depth((e.a or "").strip(), (e.b or "").strip())
                for e in edges_sorted
            ]
            d_lo, d_hi = min(dvals), max(dvals)
        else:
            d_lo, d_hi = 0.0, 1.0
        d_span = max(d_hi - d_lo, 1e-6)

        for e in edges_sorted:
            a = (e.a or "").strip()
            b = (e.b or "").strip()
            if a not in id_to_2d or b not in id_to_2d:
                continue
            x0, y0 = id_to_2d[a]
            x1, y1 = id_to_2d[b]
            d_norm = (_edge_depth(a, b) - d_lo) / d_span
            alpha = 0.6 + 0.35 * (1.0 - d_norm)
            estyle = (e.style or "solid").strip().lower()
            ls = LINE_STYLE_SOLID
            if estyle in {"dashed", "hidden"}:
                ls = LINE_STYLE_AUX_DASH
            if estyle == "hidden":
                alpha *= 0.62
            ax.plot(
                [x0, x1],
                [y0, y1],
                color=EDGE_NEUTRAL,
                linewidth=LW_GEOM,
                alpha=alpha,
                linestyle=ls,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=3,
            )
            elab = (e.label or "").strip()
            if elab:
                text_with_halo(
                    ax,
                    (x0 + x1) / 2,
                    (y0 + y1) / 2 + 0.06,
                    _mpl_plain(_short_tick_label(elab, 10)),
                    fontsize=FS_SMALL - 1,
                    color=TEXT_SECONDARY,
                    bbox_pad=0.1,
                    zorder=4,
                )

        for ae in spec.auxiliary_edges:
            a = (ae.a or "").strip()
            b = (ae.b or "").strip()
            if a not in id_to_2d or b not in id_to_2d:
                continue
            x0, y0 = id_to_2d[a]
            x1, y1 = id_to_2d[b]
            ls = LINE_STYLE_SOLID if ae.style == "solid" else LINE_STYLE_AUX_DASH
            ax.plot(
                [x0, x1],
                [y0, y1],
                color=PRINT_SERIES_PALETTE[2],
                linewidth=LW_GEOM * SCHEMATIC_AUX_EDGE_LW_SCALE,
                linestyle=ls,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=3,
            )
            lab = (ae.label or "").strip()
            if lab:
                text_with_halo(
                    ax,
                    (x0 + x1) / 2,
                    (y0 + y1) / 2 + 0.08,
                    _mpl_plain(_short_tick_label(lab, 12)),
                    fontsize=FS_SMALL - 1,
                    color=TEXT_SECONDARY,
                    ha="center",
                    va="center",
                    bbox_pad=0.12,
                    zorder=4,
                )

        for lb in spec.labels:
            t = (lb.text or "").strip()
            if not t:
                continue
            disp = _mpl_label(t, use_mathtext=lb.use_mathtext)
            try:
                text_with_halo(
                    ax,
                    float(lb.x),
                    float(lb.y),
                    disp,
                    fontsize=FS_AXIS,
                    color=TEXT_PRIMARY,
                    ha="center",
                    va="center",
                    bbox_pad=0.14,
                    zorder=4,
                )
            except Exception:
                text_with_halo(
                    ax,
                    float(lb.x),
                    float(lb.y),
                    _mpl_plain(t)[:_MAX_GEOM_LABEL_CHARS],
                    fontsize=FS_AXIS,
                    color=TEXT_PRIMARY,
                    ha="center",
                    va="center",
                    bbox_pad=0.14,
                    zorder=4,
                )

        xs_all = [p[0] for p in id_to_2d.values()] + [float(lb.x) for lb in spec.labels]
        ys_all = [p[1] for p in id_to_2d.values()] + [float(lb.y) for lb in spec.labels]
        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        if xs_all and ys_all:
            pad = max(0.12 * (max(xs_all) - min(xs_all) or 1), 0.12 * (max(ys_all) - min(ys_all) or 1), 0.25)
            ax.set_xlim(min(xs_all) - pad, max(xs_all) + pad)
            ax.set_ylim(min(ys_all) - pad, max(ys_all) + pad)
        ax.set_aspect("equal", adjustable="datalim")
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_solid_wireframe_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_field_lines_to_png_bytes(spec: PracticeFieldLinesSpec) -> bytes | None:
    expanded = expand_field_line_presets(list(spec.presets))
    all_lines = list(spec.lines) + expanded
    if not all_lines and spec.uniform_field is None:
        return None
    xs_all: list[float] = []
    ys_all: list[float] = []
    for ln in all_lines:
        xs_all.extend(ln.x)
        ys_all.extend(ln.y)
    for pr in spec.presets:
        if isinstance(pr, PracticeFieldPresetLongStraightWire):
            xs_all.extend([pr.cx, pr.cx])
            ys_all.extend([pr.cy, pr.cy])
    if spec.uniform_field is not None:
        xs_all.extend([0, float(spec.uniform_field.dx)])
        ys_all.extend([0, float(spec.uniform_field.dy)])
    if not xs_all:
        xs_all, ys_all = [-1.0, 1.0], [-1.0, 1.0]
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.4, 4.0), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        span_all = max(max(xs_all) - min(xs_all), max(ys_all) - min(ys_all), 1.0)
        for pr in spec.presets:
            if isinstance(pr, PracticeFieldPresetLongStraightWire):
                cx, cy = float(pr.cx), float(pr.cy)
                rr = max(0.026 * span_all, 0.08)
                ax.add_patch(
                    Circle(
                        (cx, cy),
                        rr,
                        facecolor="white",
                        edgecolor=TEXT_PRIMARY,
                        linewidth=max(1.0, FLOW_AUX_STROKE_LW),
                        zorder=6,
                    )
                )
                if pr.current_out_of_page:
                    ax.add_patch(
                        Circle(
                            (cx, cy),
                            rr * 0.34,
                            facecolor=TEXT_PRIMARY,
                            edgecolor=TEXT_PRIMARY,
                            linewidth=0.0,
                            zorder=6.2,
                        )
                    )
                else:
                    ax.plot(
                        [cx - rr * 0.62, cx + rr * 0.62],
                        [cy - rr * 0.62, cy + rr * 0.62],
                        color=TEXT_PRIMARY,
                        linewidth=max(0.9, FLOW_AUX_STROKE_LW),
                        zorder=6.2,
                    )
                    ax.plot(
                        [cx - rr * 0.62, cx + rr * 0.62],
                        [cy + rr * 0.62, cy - rr * 0.62],
                        color=TEXT_PRIMARY,
                        linewidth=max(0.9, FLOW_AUX_STROKE_LW),
                        zorder=6.2,
                    )
        for i, ln in enumerate(all_lines):
            col = (ln.color or "").strip() or PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)]
            ax.plot(
                ln.x,
                ln.y,
                color=col,
                linewidth=FIELD_LINE_TRACE_LW,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=2,
            )
            if ln.arrow != "none":
                at_end = ln.arrow == "end"
                xt, yt, ux, uy = segment_arrow_tangent(ln.x, ln.y, at_end=at_end)
                ah = 0.12 * max(
                    max(ln.x) - min(ln.x),
                    max(ln.y) - min(ln.y),
                    0.5,
                )
                ax.add_patch(
                    FancyArrowPatch(
                        (xt - ux * ah * 0.35, yt - uy * ah * 0.35),
                        (xt, yt),
                        arrowstyle="-|>",
                        mutation_scale=FLOW_ARROW_MUTATION_SCALE,
                        linewidth=FORCE_ARROW_LW * FIELD_LINE_ARROW_LW_FACTOR,
                        color=col,
                        zorder=3,
                    )
                )
        if spec.uniform_field is not None:
            u = spec.uniform_field
            dx, dy = float(u.dx), float(u.dy)
            mag = math.hypot(dx, dy) or 1.0
            ux, uy = dx / mag, dy / mag
            cx = (min(xs_all) + max(xs_all)) / 2
            cy = (min(ys_all) + max(ys_all)) / 2
            span = span_all * 0.35
            nx = 4
            for k in range(-(nx // 2), nx // 2 + 1):
                px, py = -uy, ux
                shift = k * span * 0.16
                x0 = cx + px * shift - ux * span * 0.34
                y0 = cy + py * shift - uy * span * 0.34
                x1 = cx + px * shift + ux * span * 0.34
                y1 = cy + py * shift + uy * span * 0.34
                ax.add_patch(
                    FancyArrowPatch(
                        (x0, y0),
                        (x1, y1),
                        arrowstyle="-|>",
                        mutation_scale=FLOW_ARROW_MUTATION_SCALE,
                        linewidth=FORCE_ARROW_LW,
                        color=TEXT_PRIMARY,
                        zorder=4,
                    )
                )
            lb = (u.label or "").strip()
            if lb:
                text_with_halo(
                    ax,
                    cx + ux * span * 0.55,
                    cy + uy * span * 0.55,
                    _mpl_plain(lb),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    bbox_pad=0.1,
                    zorder=5,
                )
        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        pad = max(0.1 * (max(xs_all) - min(xs_all) or 1), 0.1 * (max(ys_all) - min(ys_all) or 1), 0.3)
        ax.set_xlim(min(xs_all) - pad, max(xs_all) + pad)
        ax.set_ylim(min(ys_all) - pad, max(ys_all) + pad)
        ax.set_aspect("equal", adjustable="datalim")
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_field_lines_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_probability_tree_to_png_bytes(spec: PracticeProbabilityTreeSpec) -> bytes | None:
    if not spec.nodes:
        return None
    by_id = {n.id: n for n in spec.nodes}
    roots = [n for n in spec.nodes if not n.parent_id or n.parent_id not in by_id]
    if not roots:
        return None
    children: dict[str, list[str]] = {}
    for n in spec.nodes:
        pid = (n.parent_id or "").strip()
        if pid and pid in by_id:
            children.setdefault(pid, []).append(n.id)
    for pid in children:
        children[pid].sort(key=lambda nid: (int(by_id.get(nid).order) if by_id.get(nid) is not None else 0, nid))

    def subtree_width(nid: str) -> int:
        ch = children.get(nid, [])
        if not ch:
            return 1
        return max(1, sum(subtree_width(c) for c in ch))

    pos: dict[str, tuple[float, float]] = {}

    def place(nid: str, x0: float, x1: float, depth: int) -> None:
        ch = children.get(nid, [])
        y = -float(depth) * 1.35
        if not ch:
            pos[nid] = ((x0 + x1) / 2, y)
            return
        total = sum(subtree_width(c) for c in ch)
        cur = x0
        for c in ch:
            w = subtree_width(c)
            frac = w / max(1, total)
            ca = cur
            cb = cur + (x1 - x0) * frac
            place(c, ca, cb, depth + 1)
            cur = cb
        pos[nid] = ((x0 + x1) / 2, y)

    root_ids = sorted((r.id for r in roots), key=lambda s: s)
    root_w = {rid: max(1, subtree_width(rid)) for rid in root_ids}
    total_root_w = float(sum(root_w.values()))
    x_cur = 0.0
    for rid in root_ids:
        frac = root_w[rid] / max(total_root_w, 1.0)
        x_next = x_cur + max(2.2, total_root_w * 1.2 * frac)
        place(rid, x_cur, x_next, 0)
        x_cur = x_next + 0.35
    w0 = max(3.0, x_cur)

    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(max(5.0, w0 * 0.85), 3.8 + 0.35 * max(3, len(spec.nodes))), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        for n in spec.nodes:
            pid = (n.parent_id or "").strip()
            if not pid or pid not in pos or n.id not in pos:
                continue
            x0, y0 = pos[pid]
            x1, y1 = pos[n.id]
            ax.plot(
                [x0, x0],
                [y0, (y0 + y1) / 2.0],
                color=EDGE_NEUTRAL,
                linewidth=FLOW_EDGE_LINEWIDTH,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=1,
            )
            ax.plot(
                [x0, x1],
                [(y0 + y1) / 2.0, (y0 + y1) / 2.0],
                color=EDGE_NEUTRAL,
                linewidth=FLOW_EDGE_LINEWIDTH,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=1,
            )
            ax.plot(
                [x1, x1],
                [(y0 + y1) / 2.0, y1],
                color=EDGE_NEUTRAL,
                linewidth=FLOW_EDGE_LINEWIDTH,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=1,
            )
            el = (n.edge_label or "").strip()
            if el:
                mx = (x0 + x1) / 2
                my = (y0 + y1) / 2
                text_with_halo(
                    ax,
                    mx,
                    my + 0.12,
                    _mpl_plain(_short_tick_label(el, 20)),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="center",
                    va="bottom",
                    bbox_pad=0.12,
                    zorder=2,
                )
        node_w, node_h = 0.85, 0.42
        for n in spec.nodes:
            if n.id not in pos:
                continue
            x, y = pos[n.id]
            ax.add_patch(
                FancyBboxPatch(
                    (x - node_w / 2, y - node_h / 2),
                    node_w,
                    node_h,
                    boxstyle="round,pad=0.02,rounding_size=0.06",
                    facecolor=FLOW_NODE_FILL,
                    edgecolor=EDGE_NEUTRAL,
                    linewidth=FLOW_NODE_PATCH_LW,
                    zorder=3,
                )
            )
            tx = (n.text or "").strip() or n.id
            text_with_halo(
                ax,
                x,
                y,
                _mpl_label(_short_tick_label(tx, 16), use_mathtext=bool(n.use_mathtext)),
                fontsize=FS_SMALL,
                color=TEXT_PRIMARY,
                ha="center",
                va="center",
                bbox_pad=0.1,
                zorder=4,
            )
            ln = (n.leaf_note or "").strip()
            if ln and not children.get(n.id):
                text_with_halo(
                    ax,
                    x,
                    y - node_h * 0.85,
                    _mpl_plain(_short_tick_label(ln, 24)),
                    fontsize=FS_SMALL - 1,
                    color=TEXT_SECONDARY,
                    ha="center",
                    va="top",
                    bbox_pad=0.1,
                    zorder=4,
                )
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        pad_x = 0.5
        pad_y = 0.55
        ax.set_xlim(min(xs) - pad_x, max(xs) + pad_x)
        ax.set_ylim(min(ys) - pad_y, max(ys) + pad_y + 0.5)
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_probability_tree_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _pedigree_roman_generation(display_index: int) -> str:
    """将 1-based 代次显示为罗马数字（Ⅰ、Ⅱ…）。"""
    if display_index < 1:
        return "?"
    pairs = ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"))
    v = display_index
    parts: list[str] = []
    for val, sym in pairs:
        while v >= val:
            parts.append(sym)
            v -= val
    return "".join(parts)


def render_pedigree_to_png_bytes(spec: PracticePedigreeSpec) -> bytes | None:
    if not spec.individuals:
        return None
    by_id = {p.id: p for p in spec.individuals}
    by_gen: dict[int, list[str]] = {}
    for p in spec.individuals:
        by_gen.setdefault(int(p.generation), []).append(p.id)
    for g in by_gen:
        by_gen[g].sort()

    pos: dict[str, tuple[float, float]] = {}
    y_step = 1.5
    for gen in sorted(by_gen.keys()):
        row = by_gen[gen]
        n = len(row)
        row_w = max(3.0, n * 1.2)
        x_center_shift = (n - 1) * 1.25 / 2.0
        for i, pid in enumerate(row):
            ind = by_id[pid]
            if ind.x_hint is not None:
                x = (float(ind.x_hint) - 0.5) * row_w
            else:
                x = i * 1.25 - x_center_shift
            y = -float(gen) * y_step
            pos[pid] = (x, y)

    # 轻量布局修正：婚配双方靠近、子代向父母中点收敛（仅对无 x_hint 个体生效）
    for _ in range(2):
        for m in spec.marriages:
            a, b = (m.left or "").strip(), (m.right or "").strip()
            if a not in pos or b not in pos:
                continue
            pa, pb = by_id.get(a), by_id.get(b)
            if pa is None or pb is None or pa.generation != pb.generation:
                continue
            xa, ya = pos[a]
            xb, yb = pos[b]
            if abs(ya - yb) > 0.05:
                continue
            target_gap = 0.72
            mid = (xa + xb) / 2.0
            if pa.x_hint is None:
                xa = mid - target_gap / 2.0
            if pb.x_hint is None:
                xb = mid + target_gap / 2.0
            pos[a] = (xa, ya)
            pos[b] = (xb, yb)
        for d in spec.descents:
            mo, fa, ch = (d.mother or "").strip(), (d.father or "").strip(), (d.child or "").strip()
            if mo not in pos or fa not in pos or ch not in pos or ch not in by_id:
                continue
            xc, yc = pos[ch]
            if by_id[ch].x_hint is not None:
                continue
            xm, _ym = pos[mo]
            xf, _yf = pos[fa]
            xmid = (xm + xf) / 2.0
            pos[ch] = (xc * 0.45 + xmid * 0.55, yc)

    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(max(5.5, len(spec.individuals) * 0.65), 3.8 + 0.5 * len(by_gen)), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        def draw_person(pid: str) -> None:
            if pid not in pos:
                return
            x, y = pos[pid]
            p = by_id[pid]
            r = 0.22
            if p.sex == "male":
                if p.affected:
                    ax.add_patch(
                        Rectangle(
                            (x - r, y - r),
                            2 * r,
                            2 * r,
                            facecolor=TEXT_PRIMARY,
                            edgecolor=EDGE_NEUTRAL,
                            linewidth=FLOW_AUX_STROKE_LW,
                            zorder=3,
                        )
                    )
                else:
                    ax.add_patch(
                        Rectangle(
                            (x - r, y - r),
                            2 * r,
                            2 * r,
                            facecolor="white",
                            edgecolor=EDGE_NEUTRAL,
                            linewidth=FLOW_AUX_STROKE_LW,
                            zorder=3,
                        )
                    )
                    if p.carrier:
                        left = MplPath(
                            [(x - r, y - r), (x, y - r), (x, y + r), (x - r, y + r), (0, 0)],
                            [MplPath.MOVETO, MplPath.LINETO, MplPath.LINETO, MplPath.LINETO, MplPath.CLOSEPOLY],
                        )
                        ax.add_patch(
                            PathPatch(
                                left,
                                facecolor="#c8c8c8",
                                edgecolor="none",
                                zorder=3.2,
                            )
                        )
                        ax.add_patch(
                            Rectangle(
                                (x - r, y - r),
                                2 * r,
                                2 * r,
                                facecolor="none",
                                edgecolor=EDGE_NEUTRAL,
                                linewidth=FLOW_AUX_STROKE_LW,
                                zorder=3.5,
                            )
                        )
            elif p.sex == "female":
                if p.affected:
                    ax.add_patch(
                        Circle(
                            (x, y),
                            r,
                            facecolor=TEXT_PRIMARY,
                            edgecolor=EDGE_NEUTRAL,
                            linewidth=FLOW_AUX_STROKE_LW,
                            zorder=3,
                        )
                    )
                else:
                    ax.add_patch(
                        Circle(
                            (x, y),
                            r,
                            facecolor="white",
                            edgecolor=EDGE_NEUTRAL,
                            linewidth=FLOW_AUX_STROKE_LW,
                            zorder=3,
                        )
                    )
                    if p.carrier:
                        ax.add_patch(
                            Wedge(
                                (x, y),
                                r,
                                90,
                                270,
                                width=0,
                                facecolor="#c8c8c8",
                                edgecolor="none",
                                zorder=3.2,
                            )
                        )
                        ax.add_patch(
                            Circle(
                                (x, y),
                                r,
                                facecolor="none",
                                edgecolor=EDGE_NEUTRAL,
                                linewidth=FLOW_AUX_STROKE_LW,
                                zorder=3.5,
                            )
                        )
            else:
                ax.plot([x, x + r * 1.1], [y + r, y - r], color=EDGE_NEUTRAL, lw=FLOW_AUX_STROKE_LW, zorder=3)
                ax.plot([x, x + r * 1.1], [y - r, y + r], color=EDGE_NEUTRAL, lw=FLOW_AUX_STROKE_LW, zorder=3)
                if p.affected:
                    ax.fill(
                        [x, x + r * 1.1, x],
                        [y + r, y, y - r],
                        color=TEXT_PRIMARY,
                        zorder=3.1,
                    )
                elif p.carrier:
                    ax.fill(
                        [x, x + r * 0.55, x],
                        [y + r * 0.6, y, y - r * 0.6],
                        color="#c8c8c8",
                        zorder=3.1,
                    )
            if p.deceased:
                ax.plot(
                    [x - r * 0.95, x + r * 0.95],
                    [y + r * 0.95, y - r * 0.95],
                    color=TEXT_PRIMARY,
                    linewidth=1.15,
                    zorder=6,
                )
            pb = (spec.proband_id or "").strip()
            if pb and pid == pb:
                ax.annotate(
                    "",
                    xy=(x, y + r * 1.05),
                    xytext=(x, y + r * 1.55),
                    arrowprops=dict(
                        arrowstyle="-|>",
                        color=PRINT_SERIES_PALETTE[0],
                        lw=FLOW_EDGE_LINEWIDTH * 0.85,
                        mutation_scale=10,
                    ),
                    zorder=7,
                )
            note = _short_tick_label(_mpl_plain((p.note or "").strip()), 12)
            if note:
                text_with_halo(
                    ax,
                    x,
                    y - r * 1.45,
                    note,
                    fontsize=FS_SMALL - 1,
                    color=TEXT_SECONDARY,
                    va="top",
                    bbox_pad=0.1,
                    zorder=6,
                )

        for m in spec.marriages:
            a, b = (m.left or "").strip(), (m.right or "").strip()
            if a not in pos or b not in pos:
                continue
            xa, ya = pos[a]
            xb, yb = pos[b]
            if abs(ya - yb) > 0.01:
                continue
            ax.plot([xa, xb], [ya, ya], color=EDGE_NEUTRAL, linewidth=FLOW_EDGE_LINEWIDTH, zorder=2)

        for d in spec.descents:
            mo, fa, ch = (d.mother or "").strip(), (d.father or "").strip(), (d.child or "").strip()
            if mo not in pos or fa not in pos or ch not in pos:
                continue
            xm, ym = pos[mo]
            xf, yf = pos[fa]
            xc, yc = pos[ch]
            if abs(ym - yf) > 0.05:
                continue
            mid_x = (xm + xf) / 2
            mid_y = ym
            ax.plot([xm, xf], [ym, ym], color=EDGE_NEUTRAL, linewidth=FLOW_EDGE_LINEWIDTH, zorder=2)
            y_mid = (mid_y + yc) / 2
            ax.plot([mid_x, mid_x], [mid_y, y_mid], color=EDGE_NEUTRAL, linewidth=FLOW_EDGE_LINEWIDTH, zorder=2)
            ax.plot([mid_x, xc], [y_mid, yc], color=EDGE_NEUTRAL, linewidth=FLOW_EDGE_LINEWIDTH, zorder=2)

        for pid in by_id:
            draw_person(pid)

        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        pad = 0.55
        if xs:
            roman_x = min(xs) - 0.78
            for gen in sorted(by_gen.keys()):
                row = by_gen[gen]
                if not row:
                    continue
                _xr, y_row = pos[row[0]]
                text_with_halo(
                    ax,
                    roman_x,
                    y_row,
                    _pedigree_roman_generation(int(gen) + 1),
                    fontsize=FS_AXIS,
                    color=TEXT_SECONDARY,
                    ha="center",
                    va="center",
                    bbox_pad=0.1,
                    zorder=1,
                )
            xs.append(roman_x)

        if spec.show_legend:
            parts: list[str] = []
            if any(p.sex == "male" for p in spec.individuals):
                parts.append("□ 男性")
            if any(p.sex == "female" for p in spec.individuals):
                parts.append("○ 女性")
            if any(p.affected for p in spec.individuals):
                parts.append("● 患者")
            if any(p.carrier and not p.affected for p in spec.individuals):
                parts.append("半填 携带者")
            if any(p.deceased for p in spec.individuals):
                parts.append("╱ 已故")
            if (spec.proband_id or "").strip():
                parts.append("↓ 先证者")
            if parts:
                ax.text(
                    0.99,
                    0.99,
                    "  ".join(parts),
                    transform=ax.transAxes,
                    ha="right",
                    va="top",
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    bbox={"boxstyle": "round,pad=0.14", "facecolor": "white", "edgecolor": "#333333", "linewidth": 0.6, "alpha": 0.9},
                    zorder=8,
                )

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)
        ax.set_aspect("equal", adjustable="datalim")
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_pedigree_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_energy_profile_to_png_bytes(spec: PracticeEnergyProfileSpec) -> bytes | None:
    if len(spec.x) < 2 or len(spec.y) != len(spec.x):
        return None
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.5, 3.6), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.plot(
            spec.x,
            spec.y,
            color=PRINT_SERIES_PALETTE[0],
            linewidth=LW_SERIES_NORMAL,
            solid_capstyle=TECH_LINE_CAPSTYLE,
            solid_joinstyle=TECH_LINE_JOINSTYLE,
            zorder=2,
        )
        ax.scatter(spec.x, spec.y, color=PRINT_SERIES_PALETTE[3], s=22, zorder=3, edgecolors=EDGE_NEUTRAL, linewidths=0.6)
        x_vals = [float(v) for v in spec.x]
        y_vals = [float(v) for v in spec.y]
        x_span = max(max(x_vals) - min(x_vals), 1.0)
        y_span = max(max(y_vals) - min(y_vals), 1.0)
        rlab = _mpl_plain(_short_tick_label(figure_matplotlib_plain_text(spec.reactants_label), 12))
        plab = _mpl_plain(_short_tick_label(figure_matplotlib_plain_text(spec.products_label), 12))
        if rlab:
            text_with_halo(
                ax,
                x_vals[0],
                y_vals[0] - 0.09 * y_span,
                rlab,
                fontsize=FS_SMALL,
                color=TEXT_SECONDARY,
                va="top",
                bbox_pad=0.1,
                zorder=4,
            )
        if plab:
            text_with_halo(
                ax,
                x_vals[-1],
                y_vals[-1] - 0.09 * y_span,
                plab,
                fontsize=FS_SMALL,
                color=TEXT_SECONDARY,
                va="top",
                bbox_pad=0.1,
                zorder=4,
            )
        bi, bj = spec.barrier_i, spec.barrier_j
        if bi is not None and bj is not None and bi < len(spec.x) and bj < len(spec.x) and bi != bj:
            xi, yi = float(spec.x[bi]), float(spec.y[bi])
            xj, yj = float(spec.x[bj]), float(spec.y[bj])
            xm = (xi + xj) / 2
            y_lo = min(yi, yj)
            y_hi = max(yi, yj)
            ax.annotate(
                "",
                xy=(xm, y_hi),
                xytext=(xm, y_lo),
                arrowprops=dict(arrowstyle="<->", color=TEXT_PRIMARY, lw=FLOW_EDGE_LINEWIDTH * 0.9),
                zorder=4,
            )
            bl = (spec.barrier_label or "").strip()
            if bl:
                text_with_halo(
                    ax,
                    xm + x_span * 0.04,
                    (y_lo + y_hi) / 2,
                    _mpl_plain(figure_matplotlib_plain_text(bl)),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="left",
                    va="center",
                    bbox_pad=0.1,
                    zorder=5,
                )
        ax.set_xlabel(
            _mpl_plain(figure_matplotlib_plain_text(spec.x_label or "进程")),
            fontsize=FS_AXIS,
            color=TEXT_PRIMARY,
        )
        ax.set_ylabel(
            _mpl_plain(figure_matplotlib_plain_text(spec.y_label or "能量")),
            fontsize=FS_AXIS,
            color=TEXT_PRIMARY,
        )
        if spec.title.strip():
            ax.set_title(
                _mpl_plain(figure_matplotlib_plain_text(spec.title.strip())),
                fontsize=FS_TITLE,
            )
        _style_cartesian_chart_axes(ax, grid_x=True, grid_y=True)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_energy_profile_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_electrochemical_cell_to_png_bytes(spec: PracticeElectrochemicalCellSpec) -> bytes | None:
    _configure_matplotlib_font()
    try:
        left_t = _short_tick_label(
            _mpl_plain(figure_matplotlib_plain_text((spec.left_label or "-").strip() or "-")),
            max_len=20,
        )
        right_t = _short_tick_label(
            _mpl_plain(figure_matplotlib_plain_text((spec.right_label or "+").strip() or "+")),
            max_len=20,
        )
        elec_t = _short_tick_label(
            _mpl_plain(figure_matplotlib_plain_text((spec.electrolyte_label or "").strip())),
            max_len=28,
        )
        label_units = max(_text_visual_units(left_t), _text_visual_units(right_t), 4.0)
        fig_w = min(7.2, max(5.2, 4.9 + 0.06 * label_units))
        fig, ax = plt.subplots(figsize=(fig_w, 3.9), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_xlim(0, 10.6)
        ax.set_ylim(0, 8.2)
        ax.axis("off")
        bx, by = 1.7, 1.0
        bw, bh = 7.2, 4.7
        electrode_w = 0.55
        inset = 0.72
        left_ex = bx + inset
        right_ex = bx + bw - inset - electrode_w
        y_liq_top = by + bh - 0.5
        beaker = FancyBboxPatch(
            (bx, by),
            bw,
            bh,
            boxstyle="round,pad=0.02,rounding_size=0.15",
            facecolor="#e8f4fc",
            edgecolor=EDGE_NEUTRAL,
            linewidth=FLOW_AUX_STROKE_LW,
            zorder=1,
        )
        ax.add_patch(beaker)
        ax.plot([bx, bx + bw], [by, by], color=EDGE_NEUTRAL, linewidth=FLOW_AUX_STROKE_LW, zorder=2)
        ax.add_patch(
            Rectangle((left_ex, by + 0.25), electrode_w, bh - 0.55, facecolor="#c0c0c0", edgecolor=EDGE_NEUTRAL, linewidth=1.0, zorder=2)
        )
        ax.add_patch(
            Rectangle((right_ex, by + 0.25), electrode_w, bh - 0.55, facecolor="#c0c0c0", edgecolor=EDGE_NEUTRAL, linewidth=1.0, zorder=2)
        )
        fs_el = FS_AXIS - 0.5 if label_units > 8 else FS_AXIS
        text_with_halo(
            ax,
            left_ex + electrode_w / 2,
            by + bh * 0.52,
            left_t,
            ha="center",
            va="center",
            fontsize=fs_el,
            color=TEXT_PRIMARY,
            bbox_pad=0.12,
            zorder=4,
        )
        text_with_halo(
            ax,
            right_ex + electrode_w / 2,
            by + bh * 0.52,
            right_t,
            ha="center",
            va="center",
            fontsize=fs_el,
            color=TEXT_PRIMARY,
            bbox_pad=0.12,
            zorder=4,
        )
        hrl = _short_tick_label(_mpl_plain(figure_matplotlib_plain_text((spec.half_reaction_left or "").strip())), 24)
        hrr = _short_tick_label(_mpl_plain(figure_matplotlib_plain_text((spec.half_reaction_right or "").strip())), 24)
        if hrl:
            text_with_halo(
                ax,
                left_ex + electrode_w / 2,
                by + 0.08,
                hrl,
                fontsize=FS_SMALL - 0.3,
                color=TEXT_SECONDARY,
                va="bottom",
                bbox_pad=0.1,
                zorder=4,
            )
        if hrr:
            text_with_halo(
                ax,
                right_ex + electrode_w / 2,
                by + 0.08,
                hrr,
                fontsize=FS_SMALL - 0.3,
                color=TEXT_SECONDARY,
                va="bottom",
                bbox_pad=0.1,
                zorder=4,
            )
        if elec_t:
            text_with_halo(
                ax,
                bx + bw / 2,
                by + bh * 0.46,
                elec_t,
                ha="center",
                va="center",
                fontsize=FS_SMALL,
                color=TEXT_SECONDARY,
                bbox_pad=0.12,
                zorder=4,
            )
        if spec.salt_bridge_u:
            y_liq = y_liq_top
            y_top = y_liq + 1.0
            xl_foot = left_ex + electrode_w
            xr_foot = right_ex
            br_col = "#7a8b99"
            lw_br = FLOW_AUX_STROKE_LW * 0.95
            ax.plot(
                [xl_foot, xl_foot],
                [y_liq, y_top],
                color=br_col,
                linewidth=lw_br,
                solid_capstyle="round",
                zorder=2,
            )
            ax.plot(
                [xl_foot, xr_foot],
                [y_top, y_top],
                color=br_col,
                linewidth=lw_br,
                solid_capstyle="round",
                zorder=2,
            )
            ax.plot(
                [xr_foot, xr_foot],
                [y_top, y_liq],
                color=br_col,
                linewidth=lw_br,
                solid_capstyle="round",
                zorder=2,
            )
        wire_y = by + bh + 0.1
        left_wire_x = left_ex + electrode_w / 2
        right_wire_x = right_ex + electrode_w / 2
        ax.plot([left_wire_x, right_wire_x], [wire_y, wire_y], color=EDGE_NEUTRAL, linewidth=LW_CIRCUIT_WIRE, zorder=3)
        e_dir = 1.0 if spec.electron_cw else -1.0
        for x in np.linspace(left_wire_x + 0.15, right_wire_x - 0.15, 5):
            dx = 0.25 * e_dir
            ax.add_patch(
                FancyArrowPatch(
                    (x, wire_y),
                    (x + dx, wire_y),
                    arrowstyle="-|>",
                    mutation_scale=10,
                    linewidth=1.2,
                    color=PRINT_SERIES_PALETTE[0],
                    zorder=4,
                )
            )
        text_with_halo(
            ax,
            bx + bw / 2,
            wire_y + 0.28,
            _mpl_plain("e-"),
            ha="center",
            va="bottom",
            fontsize=FS_AXIS,
            color=TEXT_PRIMARY,
            bbox_pad=0.1,
            zorder=5,
        )
        if spec.cation_to != "none":
            to_right = spec.cation_to == "right"
            for y in np.linspace(by + 0.95, by + bh - 1.05, 3):
                x0, x1 = (bx + bw * 0.38, bx + bw * 0.70) if to_right else (bx + bw * 0.62, bx + bw * 0.30)
                ax.add_patch(
                    FancyArrowPatch(
                        (x0, y),
                        (x1, y),
                        arrowstyle="-|>",
                        mutation_scale=8,
                        linewidth=1.0,
                        color=PRINT_SERIES_PALETTE[2],
                        zorder=2,
                    )
                )
            text_with_halo(
                ax,
                bx + bw * (0.76 if to_right else 0.24),
                by + bh * 0.48,
                _mpl_plain("+"),
                fontsize=FS_SMALL,
                color=PRINT_SERIES_PALETTE[2],
                bbox_pad=0.1,
                zorder=4,
            )
        if spec.anion_to != "none":
            to_left = spec.anion_to == "left"
            for y in np.linspace(by + 1.1, by + bh - 1.2, 3):
                x0, x1 = (bx + bw * 0.62, bx + bw * 0.30) if to_left else (bx + bw * 0.38, bx + bw * 0.70)
                ax.add_patch(
                    FancyArrowPatch(
                        (x0, y + 0.15),
                        (x1, y + 0.15),
                        arrowstyle="-|>",
                        mutation_scale=8,
                        linewidth=1.0,
                        color=PRINT_SERIES_PALETTE[1],
                        zorder=2,
                    )
                )
            text_with_halo(
                ax,
                bx + bw * (0.24 if to_left else 0.76),
                by + bh * 0.42,
                _mpl_plain("-"),
                fontsize=FS_SMALL,
                color=PRINT_SERIES_PALETTE[1],
                bbox_pad=0.1,
                zorder=4,
            )
        mode_txt = "原电池" if spec.mode == "galvanic" else "电解池"
        text_with_halo(
            ax,
            bx + bw / 2,
            0.42,
            _mpl_plain(mode_txt),
            ha="center",
            va="bottom",
            fontsize=FS_SMALL,
            color=TEXT_SECONDARY,
            bbox_pad=0.1,
            zorder=5,
        )
        if spec.title.strip():
            ax.set_title(
                _mpl_plain(figure_matplotlib_plain_text(spec.title.strip())),
                fontsize=FS_TITLE,
            )
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_electrochemical_cell_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_directed_graph_to_png_bytes(spec: PracticeDirectedGraphSpec) -> bytes | None:
    """有向图：layered 按节点 layer 分行；circular 圆周排布；边可带 label。"""
    raw_nodes = [n for n in spec.nodes if (n.id or "").strip()]
    if not raw_nodes:
        return None
    nodes: list[PracticeDirectedGraphNode] = []
    seen_ids: set[str] = set()
    for n in raw_nodes:
        nid = (n.id or "").strip()
        if nid in seen_ids:
            continue
        seen_ids.add(nid)
        nodes.append(n)
    if not nodes:
        return None
    id_set = {n.id for n in nodes}
    node_by_id = {n.id: n for n in nodes}
    edges: list[PracticeDirectedGraphEdge] = [
        e
        for e in spec.edges
        if (e.source or "").strip() in id_set and (e.target or "").strip() in id_set
    ]

    def _draw_nodes_edges(
        ax,
        pos: dict[str, tuple[float, float]],
        node_boxes: dict[str, tuple[float, float, float, float]],
        layer_rank: dict[str, int] | None,
    ) -> None:
        for edge in edges:
            s = (edge.source or "").strip()
            t = (edge.target or "").strip()
            if s not in pos or t not in pos:
                continue
            x1, y1 = pos[s]
            x2, y2 = pos[t]
            if s == t:
                cx, cy, w, bh = node_boxes[s]
                ax.annotate(
                    "",
                    xy=(cx + w * 0.38, cy + bh * 0.52),
                    xytext=(cx - w * 0.38, cy + bh * 0.52),
                    arrowprops={
                        "arrowstyle": "-|>",
                        "connectionstyle": "arc3,rad=-0.45",
                        "color": ARROW_MUTED,
                        "lw": FLOW_EDGE_LINEWIDTH,
                        "mutation_scale": FLOW_ARROW_MUTATION_SCALE,
                    },
                    zorder=4,
                )
                continue
            dx = x2 - x1
            dy = y2 - y1
            dist = math.hypot(dx, dy)
            if dist < 1e-6:
                continue
            ux, uy = dx / dist, dy / dist
            connstyle = None
            if layer_rank is not None:
                rs, rt = layer_rank.get(s, 0), layer_rank.get(t, 0)
                _, _, _, hs = node_boxes[s]
                _, _, _, ht = node_boxes[t]
                shrink_y = 0.2 + 0.018 * max(hs, ht)
                if rs < rt:
                    xa, ya = x1, y1 - hs / 2 - shrink_y
                    xb, yb = x2, y2 + ht / 2 + shrink_y
                elif rs > rt:
                    xa, ya = x1, y1 + hs / 2 + shrink_y
                    xb, yb = x2, y2 - ht / 2 - shrink_y
                else:
                    _, _, w1, _ = node_boxes[s]
                    _, _, w2, _ = node_boxes[t]
                    if x1 <= x2:
                        xa, ya = x1 + w1 / 2 + 0.05, y1
                        xb, yb = x2 - w2 / 2 - 0.05, y2
                        connstyle = "arc3,rad=0.18"
                    else:
                        xa, ya = x1 - w1 / 2 - 0.05, y1
                        xb, yb = x2 + w2 / 2 + 0.05, y2
                        connstyle = "arc3,rad=-0.18"
                dx2, dy2 = xb - xa, yb - ya
                dist2 = math.hypot(dx2, dy2)
                if dist2 < 1e-6:
                    continue
                ux, uy = dx2 / dist2, dy2 / dist2
                xa2, ya2 = xa + ux * 0.12, ya + uy * 0.12
                xb2, yb2 = xb - ux * 0.12, yb - uy * 0.12
            else:
                ws, hs = node_boxes[s][2], node_boxes[s][3]
                wt, ht = node_boxes[t][2], node_boxes[t][3]

                def _dg_circ_pad(wb: float, hb: float) -> float:
                    return 0.5 * math.hypot(wb, hb) + 0.1

                ss = _dg_circ_pad(ws, hs)
                st = _dg_circ_pad(wt, ht)
                xa, ya = x1 + ux * ss, y1 + uy * ss
                xb, yb = x2 - ux * st, y2 - uy * st
                xa2, ya2 = xa + ux * 0.12, ya + uy * 0.12
                xb2, yb2 = xb - ux * 0.12, yb - uy * 0.12
            arr = FancyArrowPatch(
                (xa2, ya2),
                (xb2, yb2),
                arrowstyle="-|>",
                mutation_scale=FLOW_ARROW_MUTATION_SCALE,
                linewidth=FLOW_EDGE_LINEWIDTH,
                color=ARROW_MUTED,
                connectionstyle=connstyle if connstyle else "arc3,rad=0.0",
                zorder=1,
            )
            ax.add_patch(arr)
            el = (edge.label or "").strip()
            if el:
                mx, my = (xa2 + xb2) / 2, (ya2 + yb2) / 2
                px, py = -uy * 0.18, ux * 0.18
                ax.text(
                    mx + px,
                    my + py,
                    _mpl_plain(_short_tick_label(el, 16)),
                    fontsize=FS_SMALL - 1,
                    ha="center",
                    va="center",
                    color=TEXT_SECONDARY,
                    bbox={"boxstyle": "round,pad=0.1", "facecolor": "white", "edgecolor": "none", "alpha": 0.92},
                    zorder=5,
                )

    _configure_matplotlib_font()
    try:
        if spec.layout == "layered":
            by_layer: dict[int, list[str]] = {}
            for n in nodes:
                nid = (n.id or "").strip()
                by_layer.setdefault(int(n.layer), []).append(nid)
            for L in by_layer:
                by_layer[L].sort(
                    key=lambda nid: (
                        float(node_by_id[nid].x_hint) if node_by_id[nid].x_hint is not None else 1e9,
                        nid,
                    )
                )
            sorted_layers = sorted(by_layer.keys())
            if not sorted_layers:
                return None

            node_attr: dict[str, tuple[float, float, str, bool, str, int]] = {}
            for n in nodes:
                nid = (n.id or "").strip()
                raw = (n.text if n else "") or nid
                um = bool(n.use_mathtext)
                joined, lines, fs_delta = _flowchart_display_lines(
                    raw, use_mathtext=um, fallback_id=nid
                )
                if um:
                    txt_disp = _mpl_label(joined, use_mathtext=True)
                    if not _use_mathtext_effective(um, joined):
                        txt_disp = _short_tick_label(
                            txt_disp.replace("\n", " "), max_len=56
                        )
                    w, h = _flowchart_node_box_dims([txt_disp])
                else:
                    txt_disp = joined
                    w, h = _flowchart_node_box_dims(lines)
                node_attr[nid] = (w, h, raw, um, txt_disp, fs_delta)

            pos: dict[str, tuple[float, float]] = {}
            node_boxes: dict[str, tuple[float, float, float, float]] = {}
            y_step = 1.14
            gap = 0.34
            layer_rank: dict[str, int] = {}
            for li, L in enumerate(sorted_layers):
                row = by_layer[L]
                if not row:
                    continue
                total_w = sum(node_attr[nid][0] for nid in row) + gap * max(0, len(row) - 1)
                x_left = -total_w / 2.0
                cy = -li * y_step
                x_cur = x_left
                for nid in row:
                    w, h, _, _, _, _ = node_attr[nid]
                    cx = x_cur + w / 2.0
                    yh = float(node_by_id[nid].y_hint) if node_by_id[nid].y_hint is not None else 0.0
                    py = cy + yh * 0.28
                    pos[nid] = (cx, py)
                    node_boxes[nid] = (cx, py, w, h)
                    layer_rank[nid] = li
                    x_cur += w + gap

            max_li = len(sorted_layers) - 1
            fig_w = min(9.0, 4.4 + 0.5 * max((a[0] for a in node_attr.values()), default=1.0))
            fig_h = 3.0 + 0.5 * (max_li + 1)
            fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=_FIG_DPI)
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")
            ax.set_aspect("equal", adjustable="datalim")

            max_half_w = 0.0
            for nid, (cx, cy) in pos.items():
                w, h, raw, um, txt_disp, fs_delta = node_attr[nid]
                max_half_w = max(max_half_w, w / 2.0)
                ax.add_patch(
                    FancyBboxPatch(
                        (cx - w / 2, cy - h / 2),
                        w,
                        h,
                        boxstyle="round,pad=0.04,rounding_size=0.06",
                        linewidth=FLOW_NODE_PATCH_LW,
                        edgecolor=EDGE_NEUTRAL,
                        facecolor=FLOW_NODE_FILL,
                        zorder=2,
                    )
                )
                fs = max(7, FS_SUBPLOT + fs_delta)
                try:
                    ax.text(
                        cx,
                        cy,
                        txt_disp,
                        ha="center",
                        va="center",
                        fontsize=fs,
                        color=TEXT_PRIMARY,
                        zorder=3,
                    )
                except Exception:
                    raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
                    ax.text(
                        cx,
                        cy,
                        _mpl_plain(_short_tick_label(raw_c, 56)),
                        ha="center",
                        va="center",
                        fontsize=fs,
                        color=TEXT_PRIMARY,
                        zorder=3,
                    )

            _draw_nodes_edges(ax, pos, node_boxes, layer_rank)

            if spec.title.strip():
                ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)
            margin_x = max(0.85, max_half_w + 0.55)
            margin_y = 0.78
            xs = [p[0] for p in pos.values()]
            ys = [p[1] for p in pos.values()]
            max_h = max((b[3] for b in node_boxes.values()), default=0.45)
            ax.set_xlim(min(xs) - margin_x, max(xs) + margin_x)
            ax.set_ylim(min(ys) - margin_y, max(ys) + margin_y + max_h)
            ax.axis("off")
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            data = buf.getvalue()
            return data if len(data) > 100 else None

        n = len(nodes)
        node_attr_c: dict[str, tuple[float, float, str, bool, str, int]] = {}
        for n in nodes:
            nid = (n.id or "").strip()
            raw = (n.text if n else "") or nid
            um = bool(n.use_mathtext)
            joined, lines, fs_delta = _flowchart_display_lines(
                raw, use_mathtext=um, fallback_id=nid
            )
            if um:
                txt_disp = _mpl_label(joined, use_mathtext=True)
                if not _use_mathtext_effective(um, joined):
                    txt_disp = _short_tick_label(
                        txt_disp.replace("\n", " "), max_len=56
                    )
                w, h = _flowchart_node_box_dims([txt_disp])
            else:
                txt_disp = joined
                w, h = _flowchart_node_box_dims(lines)
            node_attr_c[nid] = (w, h, raw, um, txt_disp, fs_delta)

        max_box_r = max(
            (0.5 * math.hypot(w, h) for w, h, _, _, _, _ in node_attr_c.values()),
            default=0.35,
        )
        R = max(1.42, 0.48 * math.sqrt(float(n)) + 0.92 + 0.35 * max_box_r)
        pos_c: dict[str, tuple[float, float]] = {}
        for i, node in enumerate(nodes):
            nid = (node.id or "").strip()
            theta = 2 * math.pi * i / n - math.pi / 2
            pos_c[nid] = (R * math.cos(theta), R * math.sin(theta))

        fig_w = min(8.4, 5.4 + 0.24 * max_box_r)
        fig, ax = plt.subplots(figsize=(fig_w, 4.2), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_aspect("equal", adjustable="datalim")

        node_boxes_c: dict[str, tuple[float, float, float, float]] = {}
        max_half_w = 0.0
        for nid, (cx, cy) in pos_c.items():
            w, h, raw, um, txt_disp, fs_delta = node_attr_c[nid]
            max_half_w = max(max_half_w, w / 2.0)
            node_boxes_c[nid] = (cx, cy, w, h)
            ax.add_patch(
                FancyBboxPatch(
                    (cx - w / 2, cy - h / 2),
                    w,
                    h,
                    boxstyle="round,pad=0.04,rounding_size=0.06",
                    linewidth=FLOW_NODE_PATCH_LW,
                    edgecolor=EDGE_NEUTRAL,
                    facecolor=FLOW_NODE_FILL,
                    zorder=2,
                )
            )
            fs = max(7, FS_SUBPLOT + fs_delta)
            try:
                ax.text(
                    cx,
                    cy,
                    txt_disp,
                    ha="center",
                    va="center",
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )
            except Exception:
                raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
                ax.text(
                    cx,
                    cy,
                    _mpl_plain(_short_tick_label(raw_c, 56)),
                    ha="center",
                    va="center",
                    fontsize=fs,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )

        _draw_nodes_edges(ax, pos_c, node_boxes_c, None)

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)
        margin = max(0.58, max_half_w + 0.42)
        lim = max(2.05, R + margin + 0.25 * max_box_r)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_directed_graph_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_unit_circle_trig_to_png_bytes(spec: PracticeUnitCircleTrigSpec) -> bytes | None:
    rad = math.radians(float(spec.angle_deg))
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(4.8, 4.8), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_aspect("equal")
        ax.set_xlim(-1.45, 1.45)
        ax.set_ylim(-1.45, 1.45)
        ax.axhline(0, color=EDGE_NEUTRAL, linewidth=0.8, zorder=1)
        ax.axvline(0, color=EDGE_NEUTRAL, linewidth=0.8, zorder=1)
        circ = Circle((0, 0), 1.0, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM, zorder=2)
        ax.add_patch(circ)
        ax.plot(
            [0, math.cos(rad)],
            [0, math.sin(rad)],
            color=PRINT_SERIES_PALETTE[0],
            linewidth=LW_SERIES_NORMAL,
            solid_capstyle=TECH_LINE_CAPSTYLE,
            solid_joinstyle=TECH_LINE_JOINSTYLE,
            zorder=3,
        )
        if spec.show_cos:
            ax.plot(
                [0, math.cos(rad)],
                [0, 0],
                color=PRINT_SERIES_PALETTE[1],
                linewidth=LW_SERIES_NORMAL * 0.95,
                linestyle="--",
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=3,
            )
            ax.text(math.cos(rad) / 2, -0.12, _mpl_plain("cos"), fontsize=FS_SMALL, ha="center", color=TEXT_SECONDARY)
        if spec.show_sin:
            ax.plot(
                [math.cos(rad), math.cos(rad)],
                [0, math.sin(rad)],
                color=PRINT_SERIES_PALETTE[2],
                linewidth=LW_SERIES_NORMAL * 0.95,
                linestyle="--",
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=3,
            )
            ax.text(math.cos(rad) + 0.12, math.sin(rad) / 2, _mpl_plain("sin"), fontsize=FS_SMALL, va="center", color=TEXT_SECONDARY)
        if spec.show_tan and abs(math.cos(rad)) > 0.08:
            t = math.tan(rad)
            ax.plot(
                [1.0, 1.0],
                [0, t],
                color=PRINT_SERIES_PALETTE[3],
                linewidth=LW_SERIES_NORMAL * 0.95,
                linestyle=":",
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=3,
            )
        arc = Arc((0, 0), 0.45, 0.45, theta1=0, theta2=float(spec.angle_deg), color=TEXT_SECONDARY, linewidth=FLOW_AUX_STROKE_LW)
        ax.add_patch(arc)
        al = (spec.angle_label or "").strip()
        if al:
            ax.text(0.32, 0.32, _mpl_plain(al), fontsize=FS_SMALL, color=TEXT_SECONDARY)
        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_unit_circle_trig_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_optics_ray_to_png_bytes(spec: PracticeOpticsRaySpec) -> bytes | None:
    if not spec.rays:
        return None
    ori = spec.interface_orientation if spec.interface_orientation in ("horizontal", "vertical", "angled") else "horizontal"
    iy = float(spec.interface_y)
    ix = float(spec.interface_x)
    ipx = float(spec.interface_pivot_x)
    ipy = float(spec.interface_pivot_y)
    iang = math.radians(float(spec.interface_angle_deg))
    xs: list[float] = [float(r.x0) for r in spec.rays] + [float(r.x1) for r in spec.rays]
    ys: list[float] = [float(r.y0) for r in spec.rays] + [float(r.y1) for r in spec.rays]
    if ori == "horizontal":
        ys.append(iy)
    elif ori == "vertical":
        xs.append(ix)
    else:
        span_g = 3.0
        xs.extend([ipx - math.cos(iang) * span_g, ipx + math.cos(iang) * span_g])
        ys.extend([ipy - math.sin(iang) * span_g, ipy + math.sin(iang) * span_g])
    if spec.principal_axis is not None:
        pa = spec.principal_axis
        xs.extend([float(pa.x0), float(pa.x1)])
        ys.extend([float(pa.y0), float(pa.y1)])
    if spec.thin_lens is not None:
        tl = spec.thin_lens
        half = float(tl.diameter) / 2
        cx, cy = float(tl.center_x), float(tl.center_y)
        xs.extend([cx, cx])
        ys.extend([cy - half, cy + half])
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.4, 4.0), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        span = max(xmax - xmin, ymax - ymin, 1.0)

        def draw_interface() -> None:
            if ori == "horizontal":
                ax.axhline(
                    iy,
                    color=EDGE_NEUTRAL,
                    linewidth=LW_TIMELINE_AXIS,
                    linestyle=LINE_STYLE_SOLID,
                    zorder=1,
                )
                if spec.show_normal:
                    xm = (xmin + xmax) / 2
                    ax.plot(
                        [xm, xm],
                        [iy - span * 0.9, iy + span * 0.9],
                        color=AUX_LINE_COLOR,
                        linewidth=AUX_LINE_WIDTH,
                        linestyle=LINE_STYLE_DOT,
                        solid_capstyle=TECH_LINE_CAPSTYLE,
                        zorder=1,
                    )
                    ax.text(xm + 0.08 * span * 0.12, iy + 0.12 * span, _mpl_plain("N"), fontsize=FS_SMALL, color=TEXT_SECONDARY)
            elif ori == "vertical":
                ax.axvline(
                    ix,
                    color=EDGE_NEUTRAL,
                    linewidth=LW_TIMELINE_AXIS,
                    linestyle=LINE_STYLE_SOLID,
                    zorder=1,
                )
                if spec.show_normal:
                    ym = (ymin + ymax) / 2
                    ax.plot(
                        [ix - span * 0.9, ix + span * 0.9],
                        [ym, ym],
                        color=AUX_LINE_COLOR,
                        linewidth=AUX_LINE_WIDTH,
                        linestyle=LINE_STYLE_DOT,
                        solid_capstyle=TECH_LINE_CAPSTYLE,
                        zorder=1,
                    )
                    ax.text(ix + 0.12 * span, ym + 0.06 * span, _mpl_plain("N"), fontsize=FS_SMALL, color=TEXT_SECONDARY)
            else:
                ux, uy = math.cos(iang), math.sin(iang)
                ext = span * 1.4
                ax.plot(
                    [ipx - ux * ext, ipx + ux * ext],
                    [ipy - uy * ext, ipy + uy * ext],
                    color=EDGE_NEUTRAL,
                    linewidth=LW_TIMELINE_AXIS,
                    linestyle=LINE_STYLE_SOLID,
                    solid_capstyle=TECH_LINE_CAPSTYLE,
                    zorder=1,
                )
                if spec.show_normal:
                    nx, ny = -uy, ux
                    ax.plot(
                        [ipx - nx * ext * 0.45, ipx + nx * ext * 0.45],
                        [ipy - ny * ext * 0.45, ipy + ny * ext * 0.45],
                        color=AUX_LINE_COLOR,
                        linewidth=AUX_LINE_WIDTH,
                        linestyle=LINE_STYLE_DOT,
                        solid_capstyle=TECH_LINE_CAPSTYLE,
                        zorder=1,
                    )
                    ax.text(ipx + nx * 0.22 * span + 0.05, ipy + ny * 0.22 * span + 0.05, _mpl_plain("N"), fontsize=FS_SMALL, color=TEXT_SECONDARY)

        draw_interface()

        if spec.principal_axis is not None:
            pa = spec.principal_axis
            ax.plot(
                [float(pa.x0), float(pa.x1)],
                [float(pa.y0), float(pa.y1)],
                color=AUX_LINE_COLOR,
                linewidth=AUX_LINE_WIDTH,
                linestyle=LINE_STYLE_DASHDOT_TUPLE,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                zorder=2,
            )

        if spec.thin_lens is not None:
            tl = spec.thin_lens
            cx, cy = float(tl.center_x), float(tl.center_y)
            half = float(tl.diameter) / 2
            d = float(tl.diameter)
            ax.plot(
                [cx, cx],
                [cy - half, cy + half],
                color=EDGE_NEUTRAL,
                linewidth=LW_GEOM,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=2,
            )
            tip = 0.18 * d
            if tl.convex_toward_right:
                ax.add_patch(
                    Polygon([(cx, cy - half), (cx, cy + half), (cx - tip, cy)], closed=True, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM * 0.85, zorder=2)
                )
                ax.add_patch(
                    Polygon([(cx, cy - half), (cx, cy + half), (cx + tip, cy)], closed=True, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM * 0.85, zorder=2)
                )
            else:
                ax.add_patch(
                    Polygon([(cx, cy - half), (cx, cy + half), (cx + tip * 0.85, cy)], closed=True, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM * 0.85, zorder=2)
                )
                ax.add_patch(
                    Polygon([(cx, cy - half), (cx, cy + half), (cx - tip * 0.85, cy)], closed=True, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM * 0.85, zorder=2)
                )

        top_l = (spec.medium_top_label or "").strip()
        bot_l = (spec.medium_bottom_label or "").strip()
        if ori == "horizontal":
            if top_l:
                text_with_halo(
                    ax,
                    xmin - 0.05 * span,
                    ymax + 0.08 * span,
                    _mpl_plain(top_l),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="left",
                    va="bottom",
                    bbox_pad=0.1,
                    zorder=4,
                )
            if bot_l:
                text_with_halo(
                    ax,
                    xmin - 0.05 * span,
                    ymin - 0.12 * span,
                    _mpl_plain(bot_l),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="left",
                    va="top",
                    bbox_pad=0.1,
                    zorder=4,
                )
        elif ori == "vertical":
            if top_l:
                text_with_halo(
                    ax,
                    ix - 0.18 * span,
                    ymax + 0.06 * span,
                    _mpl_plain(top_l),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="center",
                    va="bottom",
                    bbox_pad=0.1,
                    zorder=4,
                )
            if bot_l:
                text_with_halo(
                    ax,
                    ix + 0.18 * span,
                    ymax + 0.06 * span,
                    _mpl_plain(bot_l),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="center",
                    va="bottom",
                    bbox_pad=0.1,
                    zorder=4,
                )
        else:
            if top_l:
                text_with_halo(
                    ax,
                    xmin - 0.06 * span,
                    ymax + 0.06 * span,
                    _mpl_plain(top_l),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="left",
                    va="bottom",
                    bbox_pad=0.1,
                    zorder=4,
                )
            if bot_l:
                text_with_halo(
                    ax,
                    xmin - 0.06 * span,
                    ymin - 0.1 * span,
                    _mpl_plain(bot_l),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
                    ha="left",
                    va="top",
                    bbox_pad=0.1,
                    zorder=4,
                )

        for i, r in enumerate(spec.rays):
            col = (r.color or "").strip() or PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)]
            ls = LINE_STYLE_AUX_DASH if r.style == "dashed" else LINE_STYLE_SOLID
            x0, y0 = float(r.x0), float(r.y0)
            x1, y1 = float(r.x1), float(r.y1)
            dx, dy = x1 - x0, y1 - y0
            dist = math.hypot(dx, dy)
            if dist < 1e-9:
                continue
            ux, uy = dx / dist, dy / dist
            shaft_end = 0.88
            ax.plot(
                [x0, x0 + dx * shaft_end],
                [y0, y0 + dy * shaft_end],
                color=col,
                linewidth=CHART_SERIES_LW_NORMAL,
                linestyle=ls,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                zorder=3,
            )
            ax.add_patch(
                FancyArrowPatch(
                    (
                        x0 + dx * 0.74,
                        y0 + dy * 0.74,
                    ),
                    (
                        x1 - ux * 0.01,
                        y1 - uy * 0.01,
                    ),
                    arrowstyle="-|>",
                    mutation_scale=max(
                        10, int(FLOW_ARROW_MUTATION_SCALE * OPTICS_RAY_MUTATION_SCALE_FACTOR)
                    ),
                    linewidth=CHART_SERIES_LW_NORMAL * OPTICS_RAY_ARROW_LW_FACTOR,
                    color=col,
                    linestyle=ls,
                    zorder=4,
                )
            )
            lb = (r.label or "").strip()
            if lb:
                disp_lb = _mpl_label(_short_tick_label(lb, 12), use_mathtext=bool(r.use_mathtext))
                if not _use_mathtext_effective(bool(r.use_mathtext), lb):
                    disp_lb = _mpl_plain(_short_tick_label(lb, 12))
                text_with_halo(
                    ax,
                    (x0 + x1) / 2 - uy * 0.06 * span,
                    (y0 + y1) / 2 + ux * 0.06 * span,
                    disp_lb,
                    fontsize=FS_SMALL - 1,
                    color=TEXT_SECONDARY,
                    ha="center",
                    va="center",
                    bbox_pad=0.1,
                    zorder=5,
                )
        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        pad = max(0.25 * (max(xs) - min(xs) or 1), 0.25 * (max(ys) - min(ys) or 1), 0.4)
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)
        ax.set_aspect("equal", adjustable="datalim")
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_optics_ray_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _composite_panel_to_png_bytes(panel: PracticeCompositePanel) -> bytes | None:
    if isinstance(panel, PracticeCompositePanelPlot):
        return render_plot_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelBar):
        return render_bar_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelGroupedBar):
        return render_grouped_bar_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelPie):
        return render_pie_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelGeometry):
        return render_geometry_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelFlowchart):
        return render_flowchart_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelTable):
        return render_table_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelTimeline):
        return render_timeline_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelNumberLine):
        return render_number_line_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelVenn):
        return render_venn_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelHistogram):
        return render_histogram_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelForceDiagram):
        return render_force_diagram_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelCircuit):
        return render_circuit_simple_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelSvg):
        return rasterize_svg_to_png(panel.spec.svg, dpi=float(_FIG_DPI))
    if isinstance(panel, PracticeCompositePanelSolidWireframe):
        return render_solid_wireframe_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelFieldLines):
        return render_field_lines_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelProbabilityTree):
        return render_probability_tree_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelPedigree):
        return render_pedigree_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelEnergyProfile):
        return render_energy_profile_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelElectrochemicalCell):
        return render_electrochemical_cell_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelUnitCircleTrig):
        return render_unit_circle_trig_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelOpticsRay):
        return render_optics_ray_to_png_bytes(panel.spec)
    if isinstance(panel, PracticeCompositePanelDirectedGraph):
        return render_directed_graph_to_png_bytes(panel.spec)
    return None


def render_composite_to_png_bytes(spec: PracticeCompositeSpec) -> bytes | None:
    """多子图栅格，每格嵌入子图 PNG（避免子轴坐标系不一致问题）。"""
    if not spec.panels:
        return None
    n = len(spec.panels)
    ncols = min(max(1, spec.ncols), n)
    nrows = (n + ncols - 1) // ncols
    _configure_matplotlib_font()
    try:
        fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 3.0 * nrows), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        if nrows == 1 and ncols == 1:
            ax_list: list = [axes]
        else:
            ax_list = np.asarray(axes).ravel().tolist()
        n_slots = len(ax_list)
        if spec.title.strip():
            fig.suptitle(spec.title.strip(), fontsize=FS_TITLE + 1, y=0.995)

        any_ok = False
        for i, panel in enumerate(spec.panels):
            ax = ax_list[i]
            ax.set_facecolor("white")
            png = _composite_panel_to_png_bytes(panel)
            if png and len(png) > 50:
                try:
                    img = mpimg.imread(io.BytesIO(png), format="png")
                    ax.imshow(img, aspect="auto")
                    any_ok = True
                except Exception as ie:
                    logger.debug("render_composite_to_png_bytes: panel %s imread failed: %s", i, ie)
                    ax.text(0.5, 0.5, "(子图略)", ha="center", va="center", transform=ax.transAxes)
                    if isinstance(panel, PracticeCompositePanelSvg):
                        any_ok = True
            else:
                ax.text(0.5, 0.5, "(子图略)", ha="center", va="center", transform=ax.transAxes)
                if isinstance(panel, PracticeCompositePanelSvg):
                    any_ok = True
            st = (panel.subtitle or "").strip()
            if st:
                ax.set_title(st, fontsize=FS_SUBPLOT)
            ax.axis("off")

        for j in range(n, n_slots):
            ax_list[j].axis("off")

        if spec.title.strip():
            fig.tight_layout(rect=[0, 0, 1, 0.94])
        else:
            fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 and any_ok else None
    except Exception as e:
        logger.warning("render_composite_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_table_to_png_bytes(spec: PracticeTableSpec) -> bytes | None:
    if not spec.rows:
        return None
    ncol = max(len(r) for r in spec.rows)
    if ncol < 1:
        return None
    rows_pad: list[list[str]] = []
    for r in spec.rows:
        cells = [str(c)[:48] if c is not None else "" for c in r]
        while len(cells) < ncol:
            cells.append("")
        rows_pad.append(cells[:ncol])
    hdr = spec.headers
    col_labels: list[str] | None = None
    cell_text = rows_pad
    if hdr and len(hdr) == ncol:
        col_labels = [str(h)[:48] for h in hdr]
    elif hdr and len(hdr) > 0:
        col_labels = None

    _configure_matplotlib_font()
    try:
        fig_h = min(11.0, 1.0 + len(cell_text) * 0.42 + (1 if col_labels else 0) * 0.35)
        fig_w = min(13.0, 1.6 + ncol * 1.15)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.axis("off")
        tbl = ax.table(
            cellText=cell_text,
            colLabels=col_labels,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(FS_TABLE)
        tbl.scale(1.0, 1.45)
        for (r, c), cell in tbl.get_celld().items():
            cell.set_edgecolor(EDGE_NEUTRAL)
            cell.set_linewidth(0.55)
            if r == 0 and col_labels is not None:
                cell.set_facecolor("#e9eef6")
                cell.set_text_props(color=TEXT_PRIMARY, weight="bold")
            else:
                cell.set_facecolor("#fdfdfd" if (r % 2) == 0 else "#f5f8fc")
                cell.set_text_props(color=TEXT_PRIMARY)
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=12)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_table_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_timeline_to_png_bytes(spec: PracticeTimelineSpec) -> bytes | None:
    if not spec.items:
        return None
    items = sorted(spec.items, key=lambda it: it.t)
    ts = [it.t for it in items]
    t0 = spec.t_min if spec.t_min is not None else min(ts)
    t1 = spec.t_max if spec.t_max is not None else max(ts)
    if t1 <= t0:
        t1 = t0 + 1.0
    pad = (t1 - t0) * 0.08 + 0.1
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.6, 2.8), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        axis_left = t0 - pad
        axis_right = t1 + pad
        ax.plot(
            [axis_left, axis_right],
            [0, 0],
            color=EDGE_NEUTRAL,
            linewidth=LW_TIMELINE_AXIS,
            solid_capstyle=TECH_LINE_CAPSTYLE,
            solid_joinstyle=TECH_LINE_JOINSTYLE,
        )
        arr_len = max(0.035 * (t1 - t0), 0.06)
        ax.add_patch(
            FancyArrowPatch(
                (axis_left + arr_len, 0),
                (axis_left, 0),
                arrowstyle="-|>",
                mutation_scale=10,
                linewidth=LW_TIMELINE_AXIS * 0.9,
                color=EDGE_NEUTRAL,
                zorder=2,
            )
        )
        ax.add_patch(
            FancyArrowPatch(
                (axis_right - arr_len, 0),
                (axis_right, 0),
                arrowstyle="-|>",
                mutation_scale=10,
                linewidth=LW_TIMELINE_AXIS * 0.9,
                color=EDGE_NEUTRAL,
                zorder=2,
            )
        )
        ys = [0.0] * len(ts)
        if spec.connect and len(ts) > 1:
            ax.plot(
                ts,
                ys,
                color=PRINT_SERIES_PALETTE[0],
                linewidth=LW_TIMELINE_SERIES,
                solid_capstyle=TECH_LINE_CAPSTYLE,
                solid_joinstyle=TECH_LINE_JOINSTYLE,
                marker="o",
                markersize=8,
                zorder=3,
            )
        else:
            ax.plot(
                ts, ys, linestyle="none", marker="o", color=PRINT_SERIES_PALETTE[0], markersize=8, zorder=3
            )
        if spec.show_ticks:
            for t in ts:
                ax.plot(
                    [t, t],
                    [-0.06, 0.06],
                    color=EDGE_NEUTRAL,
                    linewidth=LW_NUMBER_LINE_MARK * 0.85,
                    zorder=3,
                )
        label_offsets: list[float] = []
        prev_t: float | None = None
        base_up = 13.0
        base_dn = -17.0
        for i, t in enumerate(ts):
            row = items[i].row
            if row is not None:
                label_offsets.append(14.0 * float(max(-3, min(3, row))))
            else:
                if prev_t is not None and (t - prev_t) < max((t1 - t0) * 0.12, 0.45):
                    sign = -1.0 if (i % 2) else 1.0
                    label_offsets.append((base_up if sign > 0 else base_dn) + sign * TIMELINE_LABEL_STAGGER_PT)
                else:
                    label_offsets.append(base_up if (i % 2 == 0) else base_dn)
            prev_t = t
        anchors = [(float(it.t), 0.0 + (0.02 if label_offsets[i] > 0 else -0.02)) for i, it in enumerate(items)]
        labels_raw = [_short_tick_label(it.label, max_len=18) for it in items]
        x_span = max(t1 - t0, 1.0)
        relaxed = _relax_label_positions(
            anchors,
            labels_raw,
            x_span,
            fontsize=FS_LEGEND,
            max_iters=72,
            max_shift=max(0.08 * x_span, 0.16),
        )
        for i, it in enumerate(items):
            lb = labels_raw[i]
            if not lb:
                continue
            rx, _ry = relaxed[i]
            dy = label_offsets[i]
            text_with_halo(
                ax,
                rx,
                0.0 + (0.16 if dy >= 0 else -0.18),
                lb,
                fontsize=FS_LEGEND,
                color=TEXT_PRIMARY,
                ha="center",
                va="bottom" if dy >= 0 else "top",
                bbox_pad=0.12,
                zorder=Z_LABEL_TEXT,
            )
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=8)
        ax.set_xlim(t0 - pad, t1 + pad)
        ax.set_ylim(-0.58, 0.62)
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_timeline_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_number_line_to_png_bytes(spec: PracticeNumberLineSpec) -> bytes | None:
    xm, xM = float(spec.x_min), float(spec.x_max)
    if not (math.isfinite(xm) and math.isfinite(xM)) or xM <= xm:
        return None
    span = xM - xm
    pad = max(span * 0.06, 0.15)
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.8, 2.2), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        if spec.show_axis_arrows:
            ax.add_patch(
                FancyArrowPatch(
                    (xm + span * 0.03, 0),
                    (xm - span * 0.02, 0),
                    arrowstyle="-|>",
                    mutation_scale=10,
                    linewidth=LW_NUMBER_LINE_AXIS * 0.9,
                    color=TEXT_PRIMARY,
                    zorder=2,
                )
            )
            ax.add_patch(
                FancyArrowPatch(
                    (xM - span * 0.03, 0),
                    (xM + span * 0.02, 0),
                    arrowstyle="-|>",
                    mutation_scale=10,
                    linewidth=LW_NUMBER_LINE_AXIS * 0.9,
                    color=TEXT_PRIMARY,
                    zorder=2,
                )
            )
        ax.plot(
            [xm, xM],
            [0, 0],
            color=TEXT_PRIMARY,
            linewidth=LW_NUMBER_LINE_AXIS,
            solid_capstyle="butt",
            zorder=1.8,
        )
        if spec.auto_ticks:
            n_tick = max(2, int(spec.tick_count))
            auto_ticks = [xm + (xM - xm) * i / n_tick for i in range(n_tick + 1)]
            for tx in auto_ticks:
                ax.plot(
                    [tx, tx],
                    [-0.05, 0.05],
                    color=EDGE_NEUTRAL,
                    linewidth=max(0.8, LW_NUMBER_LINE_MARK * 0.65),
                    zorder=1.9,
                    alpha=0.8,
                )

        def _draw_endpoint(xv: float, is_open: bool) -> None:
            rr = max(NUMBER_LINE_ENDPOINT_R_FACTOR * span, 0.045)
            ax.add_patch(
                Circle(
                    (xv, 0.0),
                    rr,
                    facecolor="white" if is_open else PRINT_SERIES_PALETTE[1],
                    edgecolor=TEXT_PRIMARY,
                    linewidth=max(0.8, LW_NUMBER_LINE_MARK * 0.75),
                    zorder=4.2,
                )
            )

        for iv in spec.intervals:
            a, b = float(iv.a), float(iv.b)
            lo, hi = min(a, b), max(a, b)
            if hi < xm or lo > xM:
                continue
            lo = max(lo, xm)
            hi = min(hi, xM)
            ax.plot(
                [lo, hi],
                [0, 0],
                color=PRINT_SERIES_PALETTE[1],
                linewidth=LW_NUMBER_LINE_BAND,
                solid_capstyle="butt",
                zorder=3,
            )
            left_open = bool(iv.open_left) if a <= b else bool(iv.open_right)
            right_open = bool(iv.open_right) if a <= b else bool(iv.open_left)
            _draw_endpoint(lo, left_open)
            _draw_endpoint(hi, right_open)
        for m in spec.marks:
            x = float(m.x)
            if not math.isfinite(x):
                continue
            ax.plot(
                [x, x], [-0.12, 0.12], color=TEXT_PRIMARY, linewidth=LW_NUMBER_LINE_MARK, zorder=4
            )
            t = (m.label or "").strip()
            if t:
                ax.text(
                    x,
                    0.22,
                    _short_tick_label(t, 12),
                    ha="center",
                    fontsize=FS_LEGEND,
                    color=TEXT_PRIMARY,
                )
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=6)
        ax.set_xlim(xm - pad, xM + pad)
        ax.set_ylim(-0.35, 0.45)
        ax.axis("off")
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_number_line_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_venn_to_png_bytes(spec: PracticeVennSpec) -> bytes | None:
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(4.8, 3.4), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        if spec.n_sets == 2:
            ax.add_patch(
                Circle((-0.35, 0.0), 0.55, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_VENN)
            )
            ax.add_patch(
                Circle((0.35, 0.0), 0.55, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_VENN)
            )
            ax.text(
                -0.7, 0.72, _short_tick_label(spec.label_a, 8), fontsize=FS_VENN_MED, ha="center"
            )
            ax.text(
                0.7, 0.72, _short_tick_label(spec.label_b, 8), fontsize=FS_VENN_MED, ha="center"
            )
            ax.text(
                -0.58,
                0.0,
                _short_tick_label(spec.only_a, 22),
                fontsize=FS_LEGEND,
                ha="center",
                va="center",
            )
            ax.text(
                0.58,
                0.0,
                _short_tick_label(spec.only_b, 22),
                fontsize=FS_LEGEND,
                ha="center",
                va="center",
            )
            ax.text(
                0.0,
                0.0,
                _short_tick_label(spec.ab, 18),
                fontsize=FS_LEGEND,
                ha="center",
                va="center",
            )
            ax.set_xlim(-1.15, 1.15)
            ax.set_ylim(-0.75, 0.85)
        else:
            ax.add_patch(
                Circle((-0.4, 0.25), 0.45, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM)
            )
            ax.add_patch(
                Circle((0.4, 0.25), 0.45, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM)
            )
            ax.add_patch(
                Circle((0.0, -0.35), 0.45, fill=False, edgecolor=EDGE_NEUTRAL, linewidth=LW_GEOM)
            )
            ax.text(
                -0.85, 0.85, _short_tick_label(spec.label_a, 6), fontsize=FS_SUBPLOT, ha="center"
            )
            ax.text(
                0.85, 0.85, _short_tick_label(spec.label_b, 6), fontsize=FS_SUBPLOT, ha="center"
            )
            ax.text(
                0.0, -0.95, _short_tick_label(spec.label_c, 6), fontsize=FS_SUBPLOT, ha="center"
            )
            ax.text(-0.45, 0.35, _short_tick_label(spec.only_a, 12), fontsize=FS_SMALL, ha="center")
            ax.text(0.45, 0.35, _short_tick_label(spec.only_b, 12), fontsize=FS_SMALL, ha="center")
            ax.text(0.0, -0.45, _short_tick_label(spec.only_c, 12), fontsize=FS_SMALL, ha="center")
            ax.text(0.0, 0.2, _short_tick_label(spec.abc, 14), fontsize=FS_SMALL, ha="center")
            ax.text(-0.2, -0.05, _short_tick_label(spec.ab, 10), fontsize=FS_SMALL, ha="center")
            ax.text(0.2, -0.05, _short_tick_label(spec.ac, 10), fontsize=FS_SMALL, ha="center")
            ax.text(0.0, -0.15, _short_tick_label(spec.bc, 10), fontsize=FS_SMALL, ha="center")
            ax.set_xlim(-1.1, 1.1)
            ax.set_ylim(-1.0, 1.0)
        ax.set_aspect("equal", adjustable="datalim")
        ax.axis("off")
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=TITLE_PAD_PT)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_venn_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_histogram_to_png_bytes(spec: PracticeHistogramSpec) -> bytes | None:
    if len(spec.edges) < 2 or len(spec.counts) != len(spec.edges) - 1:
        return None
    edges = np.array([float(e) for e in spec.edges], dtype=float)
    counts = np.array([float(c) for c in spec.counts], dtype=float)
    if np.any(np.diff(edges) <= 0) or np.any(counts < 0):
        return None
    widths = np.diff(edges)
    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.bar(
            edges[:-1],
            counts,
            width=widths * 0.92,
            align="edge",
            edgecolor=EDGE_NEUTRAL,
            linewidth=LW_HIST_BAR,
            color=HIST_BAR_FILL,
            zorder=2,
        )
        if spec.show_values:
            ymax = float(np.max(counts)) if counts.size else 0.0
            yoff = max(0.02 * max(ymax, 1.0), 0.03)
            for x0, w, c in zip(edges[:-1], widths, counts):
                if float(c) <= 0:
                    continue
                text_with_halo(
                    ax,
                    float(x0 + w * 0.46),
                    float(c + yoff),
                    _short_tick_label(f"{float(c):g}", 8),
                    fontsize=FS_SMALL - 0.2,
                    color=TEXT_SECONDARY,
                    bbox_pad=0.1,
                    zorder=Z_LABEL_TEXT,
                )
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        if spec.x_label.strip():
            ax.set_xlabel(spec.x_label.strip(), fontsize=FS_AXIS)
        if spec.y_label.strip():
            ax.set_ylabel(spec.y_label.strip(), fontsize=FS_AXIS)
        _style_cartesian_chart_axes(ax, grid_x=False, grid_y=True)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        data = buf.getvalue()
        return data if len(data) > 100 else None
    except Exception as e:
        logger.warning("render_histogram_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def render_question_figure_with_diag(q: PracticeQuestion) -> tuple[bytes | None, str]:
    """按 figure_kind 分派渲染；inline svg 由 PDF 矢量嵌入，此处不栅格。"""
    spec = q.figure_spec
    if spec is None:
        return None, "no_spec"
    kind = q.figure_kind
    if kind == "none":
        return None, "figure_kind_none"
    if kind == "svg":
        return None, "inline_svg_embedded_in_pdf"

    if kind == "geometry" and isinstance(spec, PracticeGeometrySpec):
        png = render_geometry_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "flowchart" and isinstance(spec, PracticeFlowchartSpec):
        png = render_flowchart_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "plot" and isinstance(spec, PracticePlotSpec):
        png = render_plot_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "bar" and isinstance(spec, PracticeBarSpec):
        png = render_bar_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "grouped_bar" and isinstance(spec, PracticeGroupedBarSpec):
        png = render_grouped_bar_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "pie" and isinstance(spec, PracticePieSpec):
        png = render_pie_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "composite" and isinstance(spec, PracticeCompositeSpec):
        png = render_composite_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "table" and isinstance(spec, PracticeTableSpec):
        png = render_table_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "timeline" and isinstance(spec, PracticeTimelineSpec):
        png = render_timeline_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "number_line" and isinstance(spec, PracticeNumberLineSpec):
        png = render_number_line_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "venn" and isinstance(spec, PracticeVennSpec):
        png = render_venn_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "histogram" and isinstance(spec, PracticeHistogramSpec):
        png = render_histogram_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "force_diagram" and isinstance(spec, PracticeForceDiagramSpec):
        png = render_force_diagram_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "circuit_simple" and isinstance(spec, PracticeCircuitSpec):
        png = render_circuit_simple_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "solid_wireframe" and isinstance(spec, PracticeSolidWireframeSpec):
        png = render_solid_wireframe_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "field_lines" and isinstance(spec, PracticeFieldLinesSpec):
        png = render_field_lines_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "probability_tree" and isinstance(spec, PracticeProbabilityTreeSpec):
        png = render_probability_tree_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "pedigree" and isinstance(spec, PracticePedigreeSpec):
        png = render_pedigree_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "energy_profile" and isinstance(spec, PracticeEnergyProfileSpec):
        png = render_energy_profile_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "electrochemical_cell" and isinstance(spec, PracticeElectrochemicalCellSpec):
        png = render_electrochemical_cell_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "unit_circle_trig" and isinstance(spec, PracticeUnitCircleTrigSpec):
        png = render_unit_circle_trig_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "optics_ray" and isinstance(spec, PracticeOpticsRaySpec):
        png = render_optics_ray_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")
    if kind == "directed_graph" and isinstance(spec, PracticeDirectedGraphSpec):
        png = render_directed_graph_to_png_bytes(spec)
        return (png, "ok") if png else (None, "render_returned_empty")

    logger.debug(
        "render_question_figure_with_diag: kind_spec_mismatch kind=%s spec_type=%s",
        kind,
        type(spec).__name__,
    )
    return None, f"kind_spec_mismatch:{kind}:{type(spec).__name__}"


def render_question_figure_to_png_bytes(q: PracticeQuestion) -> bytes | None:
    """按 figure_kind 分派渲染。"""
    png, _reason = render_question_figure_with_diag(q)
    return png

"""分块练习 PDF 配图：折线 / 柱状 / 饼图 / 几何草图 / 流程图（matplotlib Agg）。"""

from __future__ import annotations

import io
import logging
import math

import matplotlib

matplotlib.use("Agg")

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import (
    Arc,
    Circle,
    FancyArrowPatch,
    FancyBboxPatch,
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
from app.services.practice_figure_field_presets import expand_field_line_presets
from app.services.practice_figure_primitives import (
    project_vertex_cabinet,
    project_vertex_isometric,
    segment_arrow_tangent,
)
from app.services.practice_svg_safe import rasterize_svg_to_png

logger = logging.getLogger(__name__)

_FONT_CONFIGURED = False

# 占比低于此值的扇区合并为「其他」（经 clamp 上限后仍可能较多扇区）
_PIE_MERGE_FRACTION = 0.03
_MAX_BAR_TICK_CHARS = 14
_MAX_GEOM_LABEL_CHARS = 22
_MAX_FLOW_TEXT_MATH = 120
_GEOM_VIEW_MIN_RADIUS = 0.45

# 印刷/彩印基线：savefig 与 composite 内 SVG 栅格化（rasterize_svg_to_png）共用同一 DPI。
# 像素量级约 figsize(inches) * _FIG_DPI；例如 5.2×3.4 @168 ≈ 874×571。
_FIG_DPI = 168

# 线宽（matplotlib 数据坐标 / 点线）
LW_SERIES_NORMAL = 1.45
LW_SERIES_DENSE = 1.85
LW_SCATTER_EDGE = 1.05
LW_ERROR_CAP = 2.2
LW_BAR_EDGE = 0.45
LW_GEOM = 1.45
LW_FLOW_NODE = 1.0
LW_FLOW_ARROW = 1.25
LW_FORCE_ARROW = 1.55
LW_CIRCUIT_WIRE = 1.6
LW_TIMELINE_AXIS = 1.55
LW_TIMELINE_SERIES = 1.15
LW_NUMBER_LINE_AXIS = 1.55
LW_NUMBER_LINE_MARK = 1.35
LW_NUMBER_LINE_BAND = 6.5
LW_VENN = 1.65
LW_HIST_BAR = 0.55

# 字号（pt）
FS_TITLE = 12
FS_AXIS = 11
FS_LEGEND = 9
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
        ax.grid(True, linestyle="--", alpha=_GRID_ALPHA)

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
                ax.legend(handles, labels, loc="best", fontsize=FS_LEGEND, framealpha=0.92)

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
        ax.bar(
            x, spec.values, color=BAR_FILL_PRIMARY, edgecolor=EDGE_NEUTRAL, linewidth=LW_BAR_EDGE
        )
        rot = 35 if len(spec.categories) > 5 else 0
        tick_labels = [_short_tick_label(c) for c in spec.categories]
        ax.set_xticks(list(x))
        ax.set_xticklabels(tick_labels, rotation=rot, ha="right")
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        if spec.x_label.strip():
            ax.set_xlabel(spec.x_label.strip(), fontsize=FS_AXIS)
        if spec.y_label.strip():
            ax.set_ylabel(spec.y_label.strip(), fontsize=FS_AXIS)
        ax.grid(True, axis="y", linestyle="--", alpha=_GRID_ALPHA)
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
        for i, s in enumerate(spec.series):
            offset = -0.4 + bar_w / 2 + i * bar_w
            xpos = [xi + offset for xi in x]
            label = (s.label or "").strip() or f"系列{i + 1}"
            ax.bar(
                xpos,
                s.values,
                width=bar_w * 0.92,
                color=PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)],
                edgecolor=EDGE_NEUTRAL,
                linewidth=LW_BAR_EDGE,
                label=label,
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
        ax.grid(True, axis="y", linestyle="--", alpha=_GRID_ALPHA)
        if spec.show_legend:
            ax.legend(loc="best", fontsize=FS_LEGEND, framealpha=0.92)
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
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=10)
        pie_labels = [_short_tick_label(lb, max_len=12) for lb in mlab]
        nslice = len(use)
        pie_colors = [PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)] for i in range(nslice)]
        _wedges, _texts, autotexts = ax.pie(
            use,
            labels=pie_labels,
            autopct="%1.0f%%",
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
                    zorder=0,
                )
            else:
                patch = Polygon(
                    arr, closed=True, facecolor="none", edgecolor=ec, linewidth=LW_GEOM, zorder=0
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
                patch = Circle((cx, cy), r, facecolor=fc, edgecolor=ec, linewidth=LW_GEOM, zorder=0)
            else:
                patch = Circle(
                    (cx, cy), r, facecolor="none", edgecolor=ec, linewidth=LW_GEOM, zorder=0
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
                    zorder=0,
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
                    zorder=0,
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
            ax.plot([x0, x1], [y0, y1], color=EDGE_NEUTRAL, linewidth=LW_GEOM, zorder=1)

        if has_pts:
            px = [id_to_xy[k][0] for k in id_to_xy]
            py = [id_to_xy[k][1] for k in id_to_xy]
            ax.scatter(
                px,
                py,
                s=32,
                color=PRINT_SERIES_PALETTE[0],
                edgecolors=EDGE_NEUTRAL,
                linewidths=0.55,
                zorder=2,
            )

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
            try:
                ax.text(
                    lx,
                    ly,
                    disp,
                    fontsize=FS_SUBPLOT,
                    ha="center",
                    va="center",
                    color=TEXT_PRIMARY,
                    zorder=3,
                )
            except Exception:
                ax.text(
                    lx,
                    ly,
                    _short_tick_label(_mpl_plain(t), max_len=_MAX_GEOM_LABEL_CHARS),
                    fontsize=FS_SUBPLOT,
                    ha="center",
                    va="center",
                    color=TEXT_PRIMARY,
                    zorder=3,
                )

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
        ax.grid(True, linestyle="--", alpha=_GRID_ALPHA * 0.72)
        fig.tight_layout()

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
    pos: dict[str, tuple[float, float]] = {}
    y_step = 1.05
    x_step = 1.55
    for r in range(max_r + 1):
        row = layers.get(r, [])
        n_row = len(row)
        if n_row == 0:
            continue
        total_w = (n_row - 1) * x_step
        x0 = -total_w / 2.0
        for j, nid in enumerate(row):
            pos[nid] = (x0 + j * x_step, -r * y_step)

    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.4, 3.2 + 0.45 * (max_r + 1)), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_aspect("equal", adjustable="datalim")

        node_boxes: dict[str, tuple[float, float, float, float]] = {}
        max_half_w = 0.0
        h = 0.42
        for nid, (cx, cy) in pos.items():
            node = next((x for x in nodes if (x.id or "").strip() == nid), None)
            raw = (node.text if node else "") or nid
            raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
            um = bool(node and node.use_mathtext)
            txt = _mpl_label(raw_c, use_mathtext=um)
            if not _use_mathtext_effective(um, raw_c):
                txt = _short_tick_label(txt, max_len=14)
            w = max(0.55, min(2.0, 0.11 * max(len(raw), 2) + 0.35))
            max_half_w = max(max_half_w, w / 2.0)
            node_boxes[nid] = (cx, cy, w, h)
            rect = FancyBboxPatch(
                (cx - w / 2, cy - h / 2),
                w,
                h,
                boxstyle="round,pad=0.04,rounding_size=0.06",
                linewidth=LW_FLOW_NODE,
                edgecolor=EDGE_NEUTRAL,
                facecolor=FLOW_NODE_FILL,
                zorder=2,
            )
            ax.add_patch(rect)
            try:
                ax.text(
                    cx,
                    cy,
                    txt,
                    ha="center",
                    va="center",
                    fontsize=FS_SUBPLOT,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )
            except Exception:
                um = bool(node and node.use_mathtext)
                txt_fb = _mpl_label(raw_c, use_mathtext=um)
                if not _use_mathtext_effective(um, raw_c):
                    txt_fb = _short_tick_label(txt_fb, max_len=14)
                ax.text(
                    cx,
                    cy,
                    txt_fb,
                    ha="center",
                    va="center",
                    fontsize=FS_SUBPLOT,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )

        shrink_y = 0.22
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
                        "lw": LW_FLOW_ARROW,
                        "mutation_scale": 12,
                    },
                    zorder=4,
                )
                continue
            x1, y1 = pos[s]
            x2, y2 = pos[t]
            if rank.get(s, 0) < rank.get(t, 0):
                xa, ya = x1, y1 - h / 2 - shrink_y
                xb, yb = x2, y2 + h / 2 + shrink_y
            else:
                xa, ya = x1, y1 + h / 2 + shrink_y
                xb, yb = x2, y2 - h / 2 - shrink_y
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
                mutation_scale=13,
                linewidth=LW_FLOW_ARROW,
                color=ARROW_MUTED,
                zorder=1,
            )
            ax.add_patch(arr)

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)
        margin_x = max(0.8, max_half_w + 0.5)
        margin_y = 0.75
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        ax.set_xlim(min(xs) - margin_x, max(xs) + margin_x)
        ax.set_ylim(min(ys) - margin_y, max(ys) + margin_y + h)
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
        R = max(1.35, 0.48 * math.sqrt(float(n)) + 0.92)
        pos: dict[str, tuple[float, float]] = {}
        for i, node in enumerate(nodes):
            nid = (node.id or "").strip()
            theta = 2 * math.pi * i / n - math.pi / 2
            pos[nid] = (R * math.cos(theta), R * math.sin(theta))

        w_cap = min(2.2, 2.65 / math.sqrt(float(n)))

        fig, ax = plt.subplots(figsize=(5.4, 4.0), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_aspect("equal", adjustable="datalim")

        node_boxes: dict[str, tuple[float, float, float, float]] = {}
        max_half_w = 0.0
        h = 0.42
        for nid, (cx, cy) in pos.items():
            node = next((x for x in nodes if (x.id or "").strip() == nid), None)
            raw = (node.text if node else "") or nid
            raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
            um = bool(node and node.use_mathtext)
            txt = _mpl_label(raw_c, use_mathtext=um)
            if not _use_mathtext_effective(um, raw_c):
                txt = _short_tick_label(txt, max_len=14)
            w = max(0.55, min(w_cap, 0.11 * max(len(raw), 2) + 0.35))
            max_half_w = max(max_half_w, w / 2.0)
            node_boxes[nid] = (cx, cy, w, h)
            rect = FancyBboxPatch(
                (cx - w / 2, cy - h / 2),
                w,
                h,
                boxstyle="round,pad=0.04,rounding_size=0.06",
                linewidth=LW_FLOW_NODE,
                edgecolor=EDGE_NEUTRAL,
                facecolor=FLOW_NODE_FILL,
                zorder=2,
            )
            ax.add_patch(rect)
            try:
                ax.text(
                    cx,
                    cy,
                    txt,
                    ha="center",
                    va="center",
                    fontsize=FS_SUBPLOT,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )
            except Exception:
                um = bool(node and node.use_mathtext)
                txt_fb = _mpl_label(raw_c, use_mathtext=um)
                if not _use_mathtext_effective(um, raw_c):
                    txt_fb = _short_tick_label(txt_fb, max_len=14)
                ax.text(
                    cx,
                    cy,
                    txt_fb,
                    ha="center",
                    va="center",
                    fontsize=FS_SUBPLOT,
                    color=TEXT_PRIMARY,
                    zorder=3,
                )

        shrink = 0.28
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
                        "lw": LW_FLOW_ARROW,
                        "mutation_scale": 12,
                    },
                    zorder=4,
                )
                continue
            if dist < 1e-6:
                continue
            ux, uy = dx / dist, dy / dist
            xa, ya = x1 + ux * shrink, y1 + uy * shrink
            xb, yb = x2 - ux * shrink, y2 - uy * shrink
            arr = FancyArrowPatch(
                (xa, ya),
                (xb, yb),
                arrowstyle="-|>",
                mutation_scale=13,
                linewidth=LW_FLOW_ARROW,
                color=ARROW_MUTED,
                zorder=1,
            )
            ax.add_patch(arr)

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)

        margin = max(0.55, max_half_w + 0.35)
        lim = max(2.05, R + margin)
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

        xs: list[float] = []
        ys: list[float] = []
        for f in spec.forces:
            xs.extend([f.x0, f.x1])
            ys.extend([f.y0, f.y1])
        if spec.object_dot:
            xs.append(float(spec.object_x))
            ys.append(float(spec.object_y))
            ax.scatter(
                [spec.object_x],
                [spec.object_y],
                s=78,
                c="#d8d8d8",
                edgecolors=EDGE_NEUTRAL,
                linewidths=0.95,
                zorder=1,
            )

        for i, f in enumerate(spec.forces):
            col = (f.color or "").strip() or PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)]
            z = max(1, min(5, int(f.zorder)))
            arr = FancyArrowPatch(
                (float(f.x0), float(f.y0)),
                (float(f.x1), float(f.y1)),
                arrowstyle="-|>",
                mutation_scale=14,
                linewidth=LW_FORCE_ARROW,
                color=col,
                zorder=z,
            )
            ax.add_patch(arr)
            lb = (f.label or "").strip()
            if lb:
                mx = (float(f.x0) + float(f.x1)) / 2.0
                my = (float(f.y0) + float(f.y1)) / 2.0
                disp = _mpl_label(lb, use_mathtext=f.use_mathtext)
                if not _use_mathtext_effective(f.use_mathtext, lb):
                    disp = _short_tick_label(disp, 14)
                try:
                    ax.text(
                        mx,
                        my,
                        disp,
                        fontsize=FS_LEGEND,
                        ha="center",
                        va="center",
                        color=TEXT_PRIMARY,
                        bbox={
                            "boxstyle": "round,pad=0.15",
                            "facecolor": "white",
                            "edgecolor": "none",
                            "alpha": 0.88,
                        },
                        zorder=z + 1,
                    )
                except Exception:
                    ax.text(
                        mx,
                        my,
                        _short_tick_label(_mpl_plain(lb), 14),
                        fontsize=FS_LEGEND,
                        ha="center",
                        va="center",
                        color=TEXT_PRIMARY,
                        bbox={
                            "boxstyle": "round,pad=0.15",
                            "facecolor": "white",
                            "edgecolor": "none",
                            "alpha": 0.88,
                        },
                        zorder=z + 1,
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


def _circuit_edge_polyline(
    spec: PracticeCircuitSpec,
    e,
    id_to_xy: dict[str, tuple[float, float]],
) -> list[tuple[float, float]] | None:
    s = (e.source or "").strip()
    t = (e.target or "").strip()
    if s not in id_to_xy or t not in id_to_xy:
        return None
    pts: list[tuple[float, float]] = [id_to_xy[s]]
    for v in e.via:
        pts.append((float(v.x), float(v.y)))
    pts.append(id_to_xy[t])
    return pts


def _circuit_draw_symbol(ax, el: str, mx: float, my: float, ux: float, uy: float, g: float) -> None:
    px, py = -uy, ux
    el = (el or "wire").strip().lower()
    if el == "wire":
        return
    if el == "resistor":
        w, h = 0.2 * g, 0.07 * g
        ax.add_patch(
            Rectangle(
                (mx - w / 2, my - h / 2),
                w,
                h,
                facecolor="white",
                edgecolor=TEXT_PRIMARY,
                linewidth=LW_FLOW_NODE,
                zorder=4,
            )
        )
        return
    if el == "cell":
        o = 0.06 * g
        ax.plot(
            [mx - px * o, mx - px * o],
            [my - py * o, my + py * o],
            color=TEXT_PRIMARY,
            lw=LW_CIRCUIT_WIRE,
            zorder=4,
        )
        ax.plot(
            [mx + px * o, mx + px * o],
            [my - py * o, my + py * o],
            color=TEXT_PRIMARY,
            lw=LW_CIRCUIT_WIRE,
            zorder=4,
        )
        return
    if el == "lamp":
        ax.add_patch(
            Circle(
                (mx, my),
                0.07 * g,
                fill=False,
                edgecolor=TEXT_PRIMARY,
                linewidth=LW_FLOW_NODE,
                zorder=4,
            )
        )
        return
    if el == "switch":
        ax.plot(
            [mx - ux * 0.1 * g, mx + ux * 0.1 * g],
            [my - uy * 0.1 * g, my + uy * 0.1 * g],
            color=TEXT_PRIMARY,
            lw=LW_FLOW_NODE,
            zorder=4,
        )
        return
    if el == "ammeter":
        ax.add_patch(
            Circle(
                (mx, my),
                0.07 * g,
                fill="#ececec",
                edgecolor=TEXT_PRIMARY,
                linewidth=LW_FLOW_NODE,
                zorder=4,
            )
        )
        ax.text(
            mx,
            my,
            "A",
            ha="center",
            va="center",
            fontsize=FS_CIRCUIT_SYMBOL,
            color=TEXT_PRIMARY,
            zorder=5,
        )
        return
    if el == "voltmeter":
        ax.add_patch(
            Circle(
                (mx, my),
                0.07 * g,
                fill="#ececec",
                edgecolor=TEXT_PRIMARY,
                linewidth=LW_FLOW_NODE,
                zorder=4,
            )
        )
        ax.text(
            mx,
            my,
            "V",
            ha="center",
            va="center",
            fontsize=FS_CIRCUIT_SYMBOL,
            color=TEXT_PRIMARY,
            zorder=5,
        )
        return
    ax.add_patch(
        Rectangle(
            (mx - 0.06 * g, my - 0.05 * g),
            0.12 * g,
            0.1 * g,
            facecolor="#e2e2e2",
            edgecolor=EDGE_NEUTRAL,
            linewidth=LW_FLOW_NODE,
            zorder=4,
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
    valid_edges = [e for e in spec.edges if _circuit_edge_polyline(spec, e, id_to_xy)]
    if not valid_edges:
        return None

    _configure_matplotlib_font()
    try:
        fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

        xs = [xy[0] for xy in id_to_xy.values()]
        ys = [xy[1] for xy in id_to_xy.values()]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
        g = span * 0.35

        for e in valid_edges:
            pts = _circuit_edge_polyline(spec, e, id_to_xy)
            if not pts or len(pts) < 2:
                continue
            px = [p[0] for p in pts]
            py = [p[1] for p in pts]
            ax.plot(
                px,
                py,
                color=TEXT_PRIMARY,
                linewidth=LW_CIRCUIT_WIRE,
                solid_capstyle="round",
                zorder=2,
            )
            mid_seg = len(pts) // 2
            i0 = max(0, mid_seg - 1)
            x0, y0 = pts[i0]
            x1, y1 = pts[min(i0 + 1, len(pts) - 1)]
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            dx, dy = x1 - x0, y1 - y0
            dist = math.hypot(dx, dy) or 1.0
            ux, uy = dx / dist, dy / dist
            _circuit_draw_symbol(ax, e.element, mx, my, ux, uy, g)

        for nid, (x, y) in id_to_xy.items():
            ax.scatter(
                [x],
                [y],
                s=40,
                c=PRINT_SERIES_PALETTE[0],
                edgecolors=TEXT_PRIMARY,
                linewidths=0.65,
                zorder=3,
            )
            ax.text(
                x,
                y - 0.04 * span,
                _short_tick_label(nid, 10),
                ha="center",
                va="top",
                fontsize=FS_CIRCUIT_SYMBOL,
                color=TEXT_SECONDARY,
            )

        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        pad = 0.12 * span + 0.2
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
        logger.warning("render_circuit_simple_to_png_bytes failed: %s", e)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def _project_solid_vertex(spec: PracticeSolidWireframeSpec, vx: float, vy: float, vz: float) -> tuple[float, float]:
    if spec.projection == "cabinet":
        return project_vertex_cabinet(vx, vy, vz)
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
                linewidth=LW_GEOM * 0.6,
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
                linewidth=LW_GEOM * 1.15,
                alpha=_clamp_alpha(max(f.alpha, 0.45), _GEOM_POLY_ALPHA_LO, _GEOM_POLY_ALPHA_HI),
                zorder=2,
            )
            ax.add_patch(poly)

        for e in spec.edges:
            a = (e.a or "").strip()
            b = (e.b or "").strip()
            if a not in id_to_2d or b not in id_to_2d:
                continue
            x0, y0 = id_to_2d[a]
            x1, y1 = id_to_2d[b]
            ax.plot([x0, x1], [y0, y1], color=EDGE_NEUTRAL, linewidth=LW_GEOM, solid_capstyle="round", zorder=3)

        for ae in spec.auxiliary_edges:
            a = (ae.a or "").strip()
            b = (ae.b or "").strip()
            if a not in id_to_2d or b not in id_to_2d:
                continue
            x0, y0 = id_to_2d[a]
            x1, y1 = id_to_2d[b]
            ls = "-" if ae.style == "solid" else "--"
            ax.plot([x0, x1], [y0, y1], color=PRINT_SERIES_PALETTE[2], linewidth=LW_GEOM * 0.9, linestyle=ls, solid_capstyle="round", zorder=3)
            lab = (ae.label or "").strip()
            if lab:
                ax.text(
                    (x0 + x1) / 2,
                    (y0 + y1) / 2 + 0.08,
                    _mpl_plain(_short_tick_label(lab, 12)),
                    fontsize=FS_SMALL - 1,
                    ha="center",
                    color=TEXT_SECONDARY,
                    zorder=4,
                )

        for lb in spec.labels:
            t = (lb.text or "").strip()
            if not t:
                continue
            disp = _mpl_label(t, use_mathtext=lb.use_mathtext)
            try:
                ax.text(
                    float(lb.x),
                    float(lb.y),
                    disp,
                    fontsize=FS_AXIS,
                    ha="center",
                    va="center",
                    color=TEXT_PRIMARY,
                    zorder=4,
                )
            except Exception:
                ax.text(
                    float(lb.x),
                    float(lb.y),
                    _mpl_plain(t)[:_MAX_GEOM_LABEL_CHARS],
                    fontsize=FS_AXIS,
                    ha="center",
                    va="center",
                    color=TEXT_PRIMARY,
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
        for pr in spec.presets:
            if isinstance(pr, PracticeFieldPresetLongStraightWire):
                sym = "o" if pr.current_out_of_page else "x"
                ax.text(
                    float(pr.cx),
                    float(pr.cy),
                    sym,
                    fontsize=FS_TITLE + 2,
                    ha="center",
                    va="center",
                    color=TEXT_PRIMARY,
                    zorder=6,
                )
        for i, ln in enumerate(all_lines):
            col = (ln.color or "").strip() or PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)]
            ax.plot(ln.x, ln.y, color=col, linewidth=LW_SERIES_NORMAL, solid_capstyle="round", zorder=2)
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
                        mutation_scale=12,
                        linewidth=LW_FORCE_ARROW * 0.85,
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
            span = max(max(xs_all) - min(xs_all), max(ys_all) - min(ys_all), 1.0) * 0.35
            ax.add_patch(
                FancyArrowPatch(
                    (cx - ux * span * 0.4, cy - uy * span * 0.4),
                    (cx + ux * span * 0.4, cy + uy * span * 0.4),
                    arrowstyle="-|>",
                    mutation_scale=14,
                linewidth=LW_FORCE_ARROW,
                color=TEXT_PRIMARY,
                zorder=4,
                )
            )
            lb = (u.label or "").strip()
            if lb:
                ax.text(
                    cx + ux * span * 0.55,
                    cy + uy * span * 0.55,
                    _mpl_plain(lb),
                    fontsize=FS_SMALL,
                    color=TEXT_SECONDARY,
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
    if len(roots) != 1:
        return None
    root_id = roots[0].id
    children: dict[str, list[str]] = {}
    for n in spec.nodes:
        pid = (n.parent_id or "").strip()
        if pid and pid in by_id:
            children.setdefault(pid, []).append(n.id)

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

    w0 = float(subtree_width(root_id))
    place(root_id, 0.0, max(3.0, w0 * 1.2), 0)

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
            ax.plot([x0, x1], [y0, y1], color=EDGE_NEUTRAL, linewidth=LW_FLOW_ARROW, zorder=1)
            el = (n.edge_label or "").strip()
            if el:
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                ax.text(
                    mx,
                    my + 0.12,
                    _mpl_plain(_short_tick_label(el, 20)),
                    fontsize=FS_SMALL,
                    ha="center",
                    va="bottom",
                    color=TEXT_SECONDARY,
                    bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.9},
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
                    linewidth=LW_FLOW_NODE,
                    zorder=3,
                )
            )
            tx = (n.text or "").strip() or n.id
            ax.text(
                x,
                y,
                _mpl_plain(_short_tick_label(tx, 16)),
                fontsize=FS_SMALL,
                ha="center",
                va="center",
                color=TEXT_PRIMARY,
                zorder=4,
            )
            ln = (n.leaf_note or "").strip()
            if ln and not children.get(n.id):
                ax.text(
                    x,
                    y - node_h * 0.85,
                    _mpl_plain(_short_tick_label(ln, 24)),
                    fontsize=FS_SMALL - 1,
                    ha="center",
                    va="top",
                    color=TEXT_SECONDARY,
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
        for i, pid in enumerate(row):
            ind = by_id[pid]
            if ind.x_hint is not None:
                x = float(ind.x_hint) * max(3.0, n * 1.2)
            else:
                x = i * 1.25
            y = -float(gen) * y_step
            pos[pid] = (x, y)

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
                ax.add_patch(
                    Rectangle(
                        (x - r, y - r),
                        2 * r,
                        2 * r,
                        facecolor="white",
                        edgecolor=EDGE_NEUTRAL,
                        linewidth=LW_FLOW_NODE,
                        zorder=3,
                    )
                )
            elif p.sex == "female":
                ax.add_patch(
                    Circle(
                        (x, y),
                        r,
                        facecolor="white",
                        edgecolor=EDGE_NEUTRAL,
                        linewidth=LW_FLOW_NODE,
                        zorder=3,
                    )
                )
            else:
                ax.plot([x, x + r * 1.1], [y + r, y - r], color=EDGE_NEUTRAL, lw=LW_FLOW_NODE, zorder=3)
                ax.plot([x, x + r * 1.1], [y - r, y + r], color=EDGE_NEUTRAL, lw=LW_FLOW_NODE, zorder=3)
            if p.affected:
                if p.sex == "male":
                    ax.add_patch(
                        Rectangle(
                            (x - r * 0.55, y - r * 0.55),
                            r * 1.1,
                            r * 1.1,
                            facecolor=TEXT_PRIMARY,
                            zorder=4,
                        )
                    )
                elif p.sex == "female":
                    ax.add_patch(
                        Circle((x, y), r * 0.45, facecolor=TEXT_PRIMARY, zorder=4)
                    )
            if p.carrier and not p.affected:
                ax.text(x, y, "·", fontsize=14, ha="center", va="center", color=PRINT_SERIES_PALETTE[2], zorder=5)

        for m in spec.marriages:
            a, b = (m.left or "").strip(), (m.right or "").strip()
            if a not in pos or b not in pos:
                continue
            xa, ya = pos[a]
            xb, yb = pos[b]
            if abs(ya - yb) > 0.01:
                continue
            ax.plot([xa, xb], [ya, ya], color=EDGE_NEUTRAL, linewidth=LW_FLOW_ARROW, zorder=2)

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
            ax.plot([xm, xf], [ym, ym], color=EDGE_NEUTRAL, linewidth=LW_FLOW_ARROW, zorder=2)
            y_mid = (mid_y + yc) / 2
            ax.plot([mid_x, mid_x], [mid_y, y_mid], color=EDGE_NEUTRAL, linewidth=LW_FLOW_ARROW, zorder=2)
            ax.plot([mid_x, xc], [y_mid, yc], color=EDGE_NEUTRAL, linewidth=LW_FLOW_ARROW, zorder=2)

        for pid in by_id:
            draw_person(pid)

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        pad = 0.55
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
        ax.plot(spec.x, spec.y, color=PRINT_SERIES_PALETTE[0], linewidth=LW_SERIES_NORMAL, zorder=2)
        ax.scatter(spec.x, spec.y, color=PRINT_SERIES_PALETTE[3], s=22, zorder=3, edgecolors=EDGE_NEUTRAL, linewidths=0.6)
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
                arrowprops=dict(arrowstyle="<->", color=TEXT_PRIMARY, lw=LW_FLOW_ARROW * 0.9),
                zorder=4,
            )
            bl = (spec.barrier_label or "").strip()
            if bl:
                ax.text(xm + (max(spec.x) - min(spec.x)) * 0.03, (y_lo + y_hi) / 2, _mpl_plain(bl), fontsize=FS_SMALL)
        ax.set_xlabel(_mpl_plain(spec.x_label or "进程"), fontsize=FS_AXIS, color=TEXT_PRIMARY)
        ax.set_ylabel(_mpl_plain(spec.y_label or "能量"), fontsize=FS_AXIS, color=TEXT_PRIMARY)
        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
        ax.grid(True, alpha=_GRID_ALPHA, linestyle="--", linewidth=0.6)
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
        fig, ax = plt.subplots(figsize=(5.2, 3.8), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.axis("off")
        beaker = FancyBboxPatch(
            (2.0, 1.0),
            6.0,
            4.5,
            boxstyle="round,pad=0.02,rounding_size=0.15",
            facecolor="#e8f4fc",
            edgecolor=EDGE_NEUTRAL,
            linewidth=LW_FLOW_NODE,
            zorder=1,
        )
        ax.add_patch(beaker)
        ax.plot([2.0, 8.0], [1.0, 1.0], color=EDGE_NEUTRAL, linewidth=LW_FLOW_NODE, zorder=2)
        ax.add_patch(
            Rectangle((2.7, 1.2), 0.55, 4.0, facecolor="#c0c0c0", edgecolor=EDGE_NEUTRAL, linewidth=1.0, zorder=2)
        )
        ax.add_patch(
            Rectangle((6.75, 1.2), 0.55, 4.0, facecolor="#c0c0c0", edgecolor=EDGE_NEUTRAL, linewidth=1.0, zorder=2)
        )
        ax.text(2.98, 3.3, _mpl_plain((spec.left_label or "-").strip() or "-"), ha="center", va="center", fontsize=FS_AXIS)
        ax.text(7.03, 3.3, _mpl_plain((spec.right_label or "+").strip() or "+"), ha="center", va="center", fontsize=FS_AXIS)
        elab = (spec.electrolyte_label or "").strip()
        if elab:
            ax.text(5.0, 3.1, _mpl_plain(elab), ha="center", va="center", fontsize=FS_SMALL, color=TEXT_SECONDARY)
        ax.plot([3.0, 7.0], [5.6, 5.6], color=EDGE_NEUTRAL, linewidth=LW_CIRCUIT_WIRE, zorder=3)
        e_dir = 1.0 if spec.electron_cw else -1.0
        for x in np.linspace(3.2, 6.8, 5):
            dx = 0.25 * e_dir
            ax.add_patch(
                FancyArrowPatch(
                    (x, 5.6),
                    (x + dx, 5.6),
                    arrowstyle="-|>",
                    mutation_scale=10,
                    linewidth=1.2,
                    color=PRINT_SERIES_PALETTE[0],
                    zorder=4,
                )
            )
        ax.text(5.0, 5.95, _mpl_plain("e-"), ha="center", va="bottom", fontsize=FS_AXIS, color=TEXT_PRIMARY)
        if spec.cation_to != "none":
            to_right = spec.cation_to == "right"
            for y in np.linspace(1.8, 4.5, 3):
                x0, x1 = (4.2, 6.2) if to_right else (5.8, 3.8)
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
            ax.text(6.4 if to_right else 3.2, 3.15, _mpl_plain("+"), fontsize=FS_SMALL, color=PRINT_SERIES_PALETTE[2])
        if spec.anion_to != "none":
            to_left = spec.anion_to == "left"
            for y in np.linspace(2.0, 4.3, 3):
                x0, x1 = (5.8, 3.8) if to_left else (4.2, 6.2)
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
        mode_txt = "原电池" if spec.mode == "galvanic" else "电解池"
        ax.text(5.0, 0.45, _mpl_plain(mode_txt), ha="center", va="bottom", fontsize=FS_SMALL, color=TEXT_SECONDARY)
        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE)
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
        h = 0.42
        shrink_y = 0.22
        shrink_c = 0.28
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
                        "lw": LW_FLOW_ARROW,
                        "mutation_scale": 12,
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
            if layer_rank is not None:
                rs, rt = layer_rank.get(s, 0), layer_rank.get(t, 0)
                if rs < rt:
                    xa, ya = x1, y1 - h / 2 - shrink_y
                    xb, yb = x2, y2 + h / 2 + shrink_y
                elif rs > rt:
                    xa, ya = x1, y1 + h / 2 + shrink_y
                    xb, yb = x2, y2 - h / 2 - shrink_y
                else:
                    _, _, w1, _ = node_boxes[s]
                    _, _, w2, _ = node_boxes[t]
                    if x1 <= x2:
                        xa, ya = x1 + w1 / 2 + 0.05, y1
                        xb, yb = x2 - w2 / 2 - 0.05, y2
                    else:
                        xa, ya = x1 - w1 / 2 - 0.05, y1
                        xb, yb = x2 + w2 / 2 + 0.05, y2
                dx2, dy2 = xb - xa, yb - ya
                dist2 = math.hypot(dx2, dy2)
                if dist2 < 1e-6:
                    continue
                ux, uy = dx2 / dist2, dy2 / dist2
                xa2, ya2 = xa + ux * 0.12, ya + uy * 0.12
                xb2, yb2 = xb - ux * 0.12, yb - uy * 0.12
            else:
                xa, ya = x1 + ux * shrink_c, y1 + uy * shrink_c
                xb, yb = x2 - ux * shrink_c, y2 - uy * shrink_c
                xa2, ya2 = xa, ya
                xb2, yb2 = xb, yb
            arr = FancyArrowPatch(
                (xa2, ya2),
                (xb2, yb2),
                arrowstyle="-|>",
                mutation_scale=13,
                linewidth=LW_FLOW_ARROW,
                color=ARROW_MUTED,
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
                by_layer.setdefault(int(n.layer), []).append(n.id)
            for L in by_layer:
                by_layer[L].sort()
            sorted_layers = sorted(by_layer.keys())
            if not sorted_layers:
                return None
            y_step = 1.05
            x_step = 1.55
            pos: dict[str, tuple[float, float]] = {}
            layer_rank: dict[str, int] = {}
            for li, L in enumerate(sorted_layers):
                row = by_layer[L]
                n_row = len(row)
                total_w = (n_row - 1) * x_step
                x0 = -total_w / 2.0
                for j, nid in enumerate(row):
                    pos[nid] = (x0 + j * x_step, -li * y_step)
                    layer_rank[nid] = li

            max_li = len(sorted_layers) - 1
            fig, ax = plt.subplots(figsize=(5.4, 3.2 + 0.45 * (max_li + 1)), dpi=_FIG_DPI)
            fig.patch.set_facecolor("white")
            ax.set_facecolor("white")
            ax.set_aspect("equal", adjustable="datalim")

            node_boxes: dict[str, tuple[float, float, float, float]] = {}
            max_half_w = 0.0
            h = 0.42
            for nid, (cx, cy) in pos.items():
                node = next((x for x in nodes if (x.id or "").strip() == nid), None)
                raw = (node.text if node else "") or nid
                raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
                um = bool(node and node.use_mathtext)
                txt = _mpl_label(raw_c, use_mathtext=um)
                if not _use_mathtext_effective(um, raw_c):
                    txt = _short_tick_label(txt, max_len=14)
                w = max(0.55, min(2.0, 0.11 * max(len(raw), 2) + 0.35))
                max_half_w = max(max_half_w, w / 2.0)
                node_boxes[nid] = (cx, cy, w, h)
                ax.add_patch(
                    FancyBboxPatch(
                        (cx - w / 2, cy - h / 2),
                        w,
                        h,
                        boxstyle="round,pad=0.04,rounding_size=0.06",
                        linewidth=LW_FLOW_NODE,
                        edgecolor=EDGE_NEUTRAL,
                        facecolor=FLOW_NODE_FILL,
                        zorder=2,
                    )
                )
                try:
                    ax.text(cx, cy, txt, ha="center", va="center", fontsize=FS_SUBPLOT, color=TEXT_PRIMARY, zorder=3)
                except Exception:
                    ax.text(cx, cy, _mpl_plain(_short_tick_label(raw_c, 14)), ha="center", va="center", fontsize=FS_SUBPLOT, color=TEXT_PRIMARY, zorder=3)

            _draw_nodes_edges(ax, pos, node_boxes, layer_rank)

            if spec.title.strip():
                ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)
            margin_x = max(0.8, max_half_w + 0.5)
            margin_y = 0.75
            xs = [p[0] for p in pos.values()]
            ys = [p[1] for p in pos.values()]
            ax.set_xlim(min(xs) - margin_x, max(xs) + margin_x)
            ax.set_ylim(min(ys) - margin_y, max(ys) + margin_y + h)
            ax.axis("off")
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=_FIG_DPI, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            data = buf.getvalue()
            return data if len(data) > 100 else None

        n = len(nodes)
        R = max(1.35, 0.48 * math.sqrt(float(n)) + 0.92)
        pos_c: dict[str, tuple[float, float]] = {}
        for i, node in enumerate(nodes):
            nid = (node.id or "").strip()
            theta = 2 * math.pi * i / n - math.pi / 2
            pos_c[nid] = (R * math.cos(theta), R * math.sin(theta))

        w_cap = min(2.2, 2.65 / math.sqrt(float(n)))
        fig, ax = plt.subplots(figsize=(5.4, 4.0), dpi=_FIG_DPI)
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        ax.set_aspect("equal", adjustable="datalim")

        node_boxes_c: dict[str, tuple[float, float, float, float]] = {}
        max_half_w = 0.0
        h = 0.42
        for nid, (cx, cy) in pos_c.items():
            node = next((x for x in nodes if (x.id or "").strip() == nid), None)
            raw = (node.text if node else "") or nid
            raw_c = (raw or "")[:_MAX_FLOW_TEXT_MATH]
            um = bool(node and node.use_mathtext)
            txt = _mpl_label(raw_c, use_mathtext=um)
            if not _use_mathtext_effective(um, raw_c):
                txt = _short_tick_label(txt, max_len=14)
            w = max(0.55, min(w_cap, 0.11 * max(len(raw), 2) + 0.35))
            max_half_w = max(max_half_w, w / 2.0)
            node_boxes_c[nid] = (cx, cy, w, h)
            ax.add_patch(
                FancyBboxPatch(
                    (cx - w / 2, cy - h / 2),
                    w,
                    h,
                    boxstyle="round,pad=0.04,rounding_size=0.06",
                    linewidth=LW_FLOW_NODE,
                    edgecolor=EDGE_NEUTRAL,
                    facecolor=FLOW_NODE_FILL,
                    zorder=2,
                )
            )
            try:
                ax.text(cx, cy, txt, ha="center", va="center", fontsize=FS_SUBPLOT, color=TEXT_PRIMARY, zorder=3)
            except Exception:
                ax.text(cx, cy, _mpl_plain(_short_tick_label(raw_c, 14)), ha="center", va="center", fontsize=FS_SUBPLOT, color=TEXT_PRIMARY, zorder=3)

        _draw_nodes_edges(ax, pos_c, node_boxes_c, None)

        if spec.title.strip():
            ax.set_title(_mpl_plain(spec.title.strip()), fontsize=FS_TITLE, pad=8)
        margin = max(0.55, max_half_w + 0.35)
        lim = max(2.05, R + margin)
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
        ax.plot([0, math.cos(rad)], [0, math.sin(rad)], color=PRINT_SERIES_PALETTE[0], linewidth=LW_SERIES_NORMAL, zorder=3)
        if spec.show_cos:
            ax.plot([0, math.cos(rad)], [0, 0], color=PRINT_SERIES_PALETTE[1], linewidth=LW_SERIES_NORMAL, linestyle="--", zorder=3)
            ax.text(math.cos(rad) / 2, -0.12, _mpl_plain("cos"), fontsize=FS_SMALL, ha="center", color=TEXT_SECONDARY)
        if spec.show_sin:
            ax.plot([math.cos(rad), math.cos(rad)], [0, math.sin(rad)], color=PRINT_SERIES_PALETTE[2], linewidth=LW_SERIES_NORMAL, linestyle="--", zorder=3)
            ax.text(math.cos(rad) + 0.12, math.sin(rad) / 2, _mpl_plain("sin"), fontsize=FS_SMALL, va="center", color=TEXT_SECONDARY)
        if spec.show_tan and abs(math.cos(rad)) > 0.08:
            t = math.tan(rad)
            ax.plot([1.0, 1.0], [0, t], color=PRINT_SERIES_PALETTE[3], linewidth=LW_SERIES_NORMAL, linestyle=":", zorder=3)
        arc = Arc((0, 0), 0.45, 0.45, theta1=0, theta2=float(spec.angle_deg), color=TEXT_SECONDARY, linewidth=LW_FLOW_NODE)
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
                ax.axhline(iy, color=EDGE_NEUTRAL, linewidth=LW_TIMELINE_AXIS, linestyle="-", zorder=1)
                if spec.show_normal:
                    xm = (xmin + xmax) / 2
                    ax.plot([xm, xm], [iy - span * 0.9, iy + span * 0.9], color=TEXT_SECONDARY, linewidth=1.0, linestyle=":", zorder=1)
                    ax.text(xm + 0.08 * span * 0.12, iy + 0.12 * span, _mpl_plain("N"), fontsize=FS_SMALL, color=TEXT_SECONDARY)
            elif ori == "vertical":
                ax.axvline(ix, color=EDGE_NEUTRAL, linewidth=LW_TIMELINE_AXIS, linestyle="-", zorder=1)
                if spec.show_normal:
                    ym = (ymin + ymax) / 2
                    ax.plot([ix - span * 0.9, ix + span * 0.9], [ym, ym], color=TEXT_SECONDARY, linewidth=1.0, linestyle=":", zorder=1)
                    ax.text(ix + 0.12 * span, ym + 0.06 * span, _mpl_plain("N"), fontsize=FS_SMALL, color=TEXT_SECONDARY)
            else:
                ux, uy = math.cos(iang), math.sin(iang)
                ext = span * 1.4
                ax.plot(
                    [ipx - ux * ext, ipx + ux * ext],
                    [ipy - uy * ext, ipy + uy * ext],
                    color=EDGE_NEUTRAL,
                    linewidth=LW_TIMELINE_AXIS,
                    linestyle="-",
                    zorder=1,
                )
                if spec.show_normal:
                    nx, ny = -uy, ux
                    ax.plot(
                        [ipx - nx * ext * 0.45, ipx + nx * ext * 0.45],
                        [ipy - ny * ext * 0.45, ipy + ny * ext * 0.45],
                        color=TEXT_SECONDARY,
                        linewidth=1.0,
                        linestyle=":",
                        zorder=1,
                    )
                    ax.text(ipx + nx * 0.22 * span + 0.05, ipy + ny * 0.22 * span + 0.05, _mpl_plain("N"), fontsize=FS_SMALL, color=TEXT_SECONDARY)

        draw_interface()

        if spec.principal_axis is not None:
            pa = spec.principal_axis
            ax.plot(
                [float(pa.x0), float(pa.x1)],
                [float(pa.y0), float(pa.y1)],
                color=TEXT_SECONDARY,
                linewidth=1.0,
                linestyle=(0, (4, 4)),
                zorder=2,
            )

        if spec.thin_lens is not None:
            tl = spec.thin_lens
            cx, cy = float(tl.center_x), float(tl.center_y)
            half = float(tl.diameter) / 2
            d = float(tl.diameter)
            ax.plot([cx, cx], [cy - half, cy + half], color=EDGE_NEUTRAL, linewidth=LW_GEOM, solid_capstyle="round", zorder=2)
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
                ax.text(xmin - 0.05 * span, ymax + 0.08 * span, _mpl_plain(top_l), fontsize=FS_SMALL)
            if bot_l:
                ax.text(xmin - 0.05 * span, ymin - 0.12 * span, _mpl_plain(bot_l), fontsize=FS_SMALL)
        elif ori == "vertical":
            if top_l:
                ax.text(ix - 0.18 * span, ymax + 0.06 * span, _mpl_plain(top_l), fontsize=FS_SMALL, ha="center")
            if bot_l:
                ax.text(ix + 0.18 * span, ymax + 0.06 * span, _mpl_plain(bot_l), fontsize=FS_SMALL, ha="center")
        else:
            if top_l:
                ax.text(xmin - 0.06 * span, ymax + 0.06 * span, _mpl_plain(top_l), fontsize=FS_SMALL)
            if bot_l:
                ax.text(xmin - 0.06 * span, ymin - 0.1 * span, _mpl_plain(bot_l), fontsize=FS_SMALL)

        for i, r in enumerate(spec.rays):
            col = (r.color or "").strip() or PRINT_SERIES_PALETTE[i % len(PRINT_SERIES_PALETTE)]
            ls = "--" if r.style == "dashed" else "-"
            ax.plot([r.x0, r.x1], [r.y0, r.y1], color=col, linewidth=LW_SERIES_NORMAL, linestyle=ls, zorder=3)
            ax.add_patch(
                FancyArrowPatch(
                    (float(r.x0), float(r.y0)),
                    (float(r.x1), float(r.y1)),
                    arrowstyle="-|>",
                    mutation_scale=11,
                    linewidth=LW_SERIES_NORMAL * 0.9,
                    color=col,
                    linestyle=ls,
                    zorder=4,
                )
            )
            lb = (r.label or "").strip()
            if lb:
                ax.text(
                    (float(r.x0) + float(r.x1)) / 2,
                    (float(r.y0) + float(r.y1)) / 2 + 0.12 * span * 0.15,
                    _mpl_plain(_short_tick_label(lb, 12)),
                    fontsize=FS_SMALL - 1,
                    ha="center",
                    color=TEXT_SECONDARY,
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
        ax.plot([t0 - pad, t1 + pad], [0, 0], color=EDGE_NEUTRAL, linewidth=LW_TIMELINE_AXIS)
        ys = [0.0] * len(ts)
        if spec.connect and len(ts) > 1:
            ax.plot(
                ts,
                ys,
                color=PRINT_SERIES_PALETTE[0],
                linewidth=LW_TIMELINE_SERIES,
                marker="o",
                markersize=8,
            )
        else:
            ax.plot(
                ts, ys, linestyle="none", marker="o", color=PRINT_SERIES_PALETTE[0], markersize=8
            )
        for it in items:
            lb = _short_tick_label(it.label, max_len=18)
            if lb:
                ax.annotate(
                    lb,
                    (it.t, 0.0),
                    textcoords="offset points",
                    xytext=(0, 14),
                    ha="center",
                    fontsize=FS_LEGEND,
                    color=TEXT_PRIMARY,
                )
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=8)
        ax.set_xlim(t0 - pad, t1 + pad)
        ax.set_ylim(-0.35, 0.55)
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
        ax.plot(
            [xm, xM],
            [0, 0],
            color=TEXT_PRIMARY,
            linewidth=LW_NUMBER_LINE_AXIS,
            solid_capstyle="butt",
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
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE, pad=10)
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
        )
        if spec.title.strip():
            ax.set_title(spec.title.strip(), fontsize=FS_TITLE)
        if spec.x_label.strip():
            ax.set_xlabel(spec.x_label.strip(), fontsize=FS_AXIS)
        if spec.y_label.strip():
            ax.set_ylabel(spec.y_label.strip(), fontsize=FS_AXIS)
        ax.grid(True, axis="y", linestyle="--", alpha=_GRID_ALPHA)
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

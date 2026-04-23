"""将模型返回的松散 JSON 规整为可校验的 PracticeSet 结构。"""

from __future__ import annotations

import math
from typing import Any

from pydantic import ValidationError

from app.models.schemas import PRACTICE_QTYPE_VALUES, PracticeSet
from app.services.json_from_llm import iter_candidate_dicts_from_llm


def _figure_kind_from_raw(fk_raw: Any) -> str:
    s = str(fk_raw).strip().lower() if fk_raw is not None else "none"
    if s in ("plot", "折线", "line", "chart"):
        return "plot"
    if s in ("grouped_bar", "groupedbar", "group_bar", "分组柱", "分组柱状"):
        return "grouped_bar"
    if s in ("histogram", "hist", "直方图", "频率分布"):
        return "histogram"
    if s in ("bar", "柱状", "柱形", "column"):
        return "bar"
    if s in ("pie", "饼", "饼图", "piechart"):
        return "pie"
    if s in ("geometry", "几何", "geo", "plane_geo"):
        return "geometry"
    if s in ("flowchart", "流程图", "flow"):
        return "flowchart"
    if s in ("composite", "multi_panel", "组合图", "子图"):
        return "composite"
    if s in ("table", "表格图", "表"):
        return "table"
    if s in ("timeline", "时间轴"):
        return "timeline"
    if s in ("number_line", "numberline", "数轴"):
        return "number_line"
    if s in ("venn", "韦恩", "文氏"):
        return "venn"
    if s in ("force_diagram", "forcediagram", "force", "受力", "受力图"):
        return "force_diagram"
    if s in ("circuit_simple", "circuitsimple", "circuit", "电路"):
        return "circuit_simple"
    if s in ("svg", "inline_svg", "矢量", "矢量图"):
        return "svg"
    if s in (
        "solid_wireframe",
        "solidwireframe",
        "wireframe",
        "立体线框",
        "轴测",
        "斜二测",
    ):
        return "solid_wireframe"
    if s in ("field_lines", "fieldlines", "场线", "电场线", "磁场线"):
        return "field_lines"
    if s in ("probability_tree", "probabilitytree", "概率树"):
        return "probability_tree"
    if s in ("pedigree", "系谱", "遗传系谱"):
        return "pedigree"
    if s in ("energy_profile", "energyprofile", "能垒", "反应历程"):
        return "energy_profile"
    if s in ("electrochemical_cell", "electrochemicalcell", "原电池", "电解池"):
        return "electrochemical_cell"
    if s in ("unit_circle_trig", "unitcircle", "单位圆", "三角函数线"):
        return "unit_circle_trig"
    if s in ("optics_ray", "opticsray", "光路", "折射", "反射"):
        return "optics_ray"
    if s in ("directed_graph", "directedgraph", "有向图", "食物链", "食物网"):
        return "directed_graph"
    return "none"


def _normalize_plot_series_items(series_raw: list[Any]) -> list[dict[str, Any]]:
    fixed_series: list[dict[str, Any]] = []
    for item in series_raw:
        if not isinstance(item, dict):
            continue
        xs, ys = item.get("x"), item.get("y")
        if not isinstance(xs, list) or not isinstance(ys, list):
            continue
        try:
            xf = [float(v) for v in xs]
            yf = [float(v) for v in ys]
        except (TypeError, ValueError):
            continue
        if len(xf) != len(yf) or len(xf) < 2:
            continue
        lab = item.get("label", "")
        da = str(item.get("draw_as", "line")).strip().lower()
        draw_as = "scatter" if da == "scatter" else "line"
        y_err: list[float] | None = None
        y_err_raw = item.get("y_err")
        if isinstance(y_err_raw, list) and len(y_err_raw) == len(xf):
            try:
                ye = [float(v) for v in y_err_raw]
                if all(math.isfinite(v) and v >= 0 for v in ye):
                    y_err = ye
            except (TypeError, ValueError):
                y_err = None
        entry: dict[str, Any] = {
            "label": str(lab) if lab is not None else "",
            "x": xf,
            "y": yf,
            "draw_as": draw_as,
        }
        if y_err is not None:
            entry["y_err"] = y_err
        fixed_series.append(entry)
    return fixed_series


def _normalize_plot_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    series_raw = spec.get("series")
    if not isinstance(series_raw, list) or not series_raw:
        return None
    fixed_series = _normalize_plot_series_items(series_raw)
    if not fixed_series:
        return None
    sr_raw = spec.get("series_right")
    fixed_right: list[dict[str, Any]] = []
    if isinstance(sr_raw, list) and sr_raw:
        fixed_right = _normalize_plot_series_items(sr_raw)
    lg = spec.get("log_y", False)
    log_y = bool(lg) if isinstance(lg, (bool, int)) else str(lg).strip().lower() in ("1", "true", "yes", "log")
    sl = spec.get("show_legend", True)
    if isinstance(sl, bool):
        show_legend = sl
    else:
        show_legend = str(sl).strip().lower() not in ("0", "false", "no", "")
    fills_raw = spec.get("fill_between")
    if not isinstance(fills_raw, list):
        fills_raw = []
    fixed_fills: list[dict[str, Any]] = []
    for fb in fills_raw[:5]:
        if not isinstance(fb, dict):
            continue
        xs = fb.get("x")
        yl = fb.get("y_lower")
        if yl is None:
            yl = fb.get("y1")
        yu = fb.get("y_upper")
        if yu is None:
            yu = fb.get("y2")
        if not isinstance(xs, list) or not isinstance(yl, list) or not isinstance(yu, list):
            continue
        try:
            xf = [float(v) for v in xs]
            lf = [float(v) for v in yl]
            uf = [float(v) for v in yu]
        except (TypeError, ValueError):
            continue
        if len(xf) != len(lf) or len(xf) != len(uf) or len(xf) < 2:
            continue
        al = fb.get("alpha", 0.28)
        try:
            alpha = float(al)
        except (TypeError, ValueError):
            alpha = 0.28
        alpha = max(0.0, min(1.0, alpha))
        fixed_fills.append(
            {
                "x": xf,
                "y_lower": lf,
                "y_upper": uf,
                "alpha": alpha,
                "color": str(fb.get("color") or ""),
                "label": str(fb.get("label") or ""),
            }
        )
    return {
        "title": str(spec.get("title") or ""),
        "x_label": str(spec.get("x_label") or ""),
        "y_label": str(spec.get("y_label") or ""),
        "y_label_right": str(spec.get("y_label_right") or ""),
        "caption": str(spec.get("caption") or ""),
        "series": fixed_series,
        "series_right": fixed_right,
        "log_y": log_y,
        "show_legend": show_legend,
        "fill_between": fixed_fills,
    }


def _normalize_bar_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    cats = spec.get("categories")
    vals = spec.get("values")
    if not isinstance(cats, list) or not isinstance(vals, list) or not cats or not vals:
        return None
    try:
        vf = [float(v) for v in vals]
    except (TypeError, ValueError):
        return None
    sc = [str(c).strip() if c is not None else "" for c in cats]
    if len(sc) != len(vf) or len(sc) == 0:
        return None
    if not any(x for x in sc):
        return None
    return {
        "title": str(spec.get("title") or ""),
        "x_label": str(spec.get("x_label") or ""),
        "y_label": str(spec.get("y_label") or ""),
        "caption": str(spec.get("caption") or ""),
        "categories": sc,
        "values": vf,
    }


def _normalize_grouped_bar_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    cats = spec.get("categories")
    if not isinstance(cats, list) or not cats:
        return None
    sc = [str(c).strip() if c is not None else "" for c in cats]
    if not any(x for x in sc):
        return None
    n = len(sc)
    series_raw = spec.get("series")
    if not isinstance(series_raw, list) or not series_raw:
        return None
    fixed_series: list[dict[str, Any]] = []
    for item in series_raw:
        if not isinstance(item, dict):
            continue
        vals = item.get("values")
        if not isinstance(vals, list) or len(vals) != n:
            continue
        try:
            vf = [float(v) for v in vals]
        except (TypeError, ValueError):
            continue
        lab = item.get("label", "")
        fixed_series.append(
            {
                "label": str(lab) if lab is not None else "",
                "values": vf,
            }
        )
    if not fixed_series:
        return None
    sl = spec.get("show_legend", True)
    if isinstance(sl, bool):
        show_legend = sl
    else:
        show_legend = str(sl).strip().lower() not in ("0", "false", "no", "")
    return {
        "title": str(spec.get("title") or ""),
        "x_label": str(spec.get("x_label") or ""),
        "y_label": str(spec.get("y_label") or ""),
        "caption": str(spec.get("caption") or ""),
        "categories": sc,
        "series": fixed_series,
        "show_legend": show_legend,
    }


def _normalize_geometry_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    pts_raw = spec.get("points")
    if not isinstance(pts_raw, list):
        pts_raw = []
    points: list[dict[str, Any]] = []
    for p in pts_raw[:64]:
        if not isinstance(p, dict):
            continue
        try:
            x = float(p.get("x", 0))
            y = float(p.get("y", 0))
        except (TypeError, ValueError):
            continue
        pid = str(p.get("id") or "").strip()
        points.append({"id": pid, "x": x, "y": y})
    seg_raw = spec.get("segments")
    if not isinstance(seg_raw, list):
        seg_raw = []
    segments: list[dict[str, str]] = []
    for s in seg_raw[:128]:
        if not isinstance(s, dict):
            continue
        segments.append(
            {
                "a": str(s.get("a") or "").strip(),
                "b": str(s.get("b") or "").strip(),
            }
        )
    lbl_raw = spec.get("labels")
    if not isinstance(lbl_raw, list):
        lbl_raw = []
    labels: list[dict[str, Any]] = []
    for lb in lbl_raw[:32]:
        if not isinstance(lb, dict):
            continue
        try:
            lx = float(lb.get("x", 0))
            ly = float(lb.get("y", 0))
        except (TypeError, ValueError):
            continue
        um = lb.get("use_mathtext", False)
        use_mathtext = bool(um) if isinstance(um, bool) else str(um).strip().lower() in ("1", "true", "yes")
        labels.append(
            {
                "text": str(lb.get("text") or ""),
                "x": lx,
                "y": ly,
                "use_mathtext": use_mathtext,
            }
        )

    circles: list[dict[str, Any]] = []
    for c in (spec.get("circles") or [])[:16]:
        if not isinstance(c, dict):
            continue
        try:
            r = float(c.get("r", c.get("radius", 1)))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(r) and r > 0):
            continue
        cx_raw, cy_raw = c.get("cx"), c.get("cy")
        cx = cy = None
        if cx_raw is not None and cy_raw is not None:
            try:
                cx = float(cx_raw)
                cy = float(cy_raw)
            except (TypeError, ValueError):
                cx = cy = None
        circles.append(
            {
                "center_id": str(c.get("center_id") or "").strip(),
                "cx": cx,
                "cy": cy,
                "r": min(r, 1e6),
                "fill": bool(c.get("fill", False)),
                "fill_color": str(c.get("fill_color") or ""),
                "edge_color": str(c.get("edge_color") or ""),
            }
        )

    polygons: list[dict[str, Any]] = []
    for poly in (spec.get("polygons") or [])[:16]:
        if not isinstance(poly, dict):
            continue
        vids = poly.get("vertex_ids")
        if not isinstance(vids, list):
            continue
        ids = [str(v).strip() for v in vids[:24] if str(v).strip()]
        if len(ids) < 3:
            continue
        al = poly.get("alpha", 0.22)
        try:
            alpha = float(al)
        except (TypeError, ValueError):
            alpha = 0.22
        alpha = max(0.0, min(1.0, alpha))
        polygons.append(
            {
                "vertex_ids": ids,
                "fill": bool(poly.get("fill", False)),
                "alpha": alpha,
                "edge_color": str(poly.get("edge_color") or ""),
                "fill_color": str(poly.get("fill_color") or ""),
            }
        )

    arcs: list[dict[str, Any]] = []
    for a in (spec.get("arcs") or [])[:24]:
        if not isinstance(a, dict):
            continue
        try:
            r = float(a.get("r", a.get("radius", 1)))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(r) and r > 0):
            continue
        cx_raw, cy_raw = a.get("cx"), a.get("cy")
        cx = cy = None
        if cx_raw is not None and cy_raw is not None:
            try:
                cx = float(cx_raw)
                cy = float(cy_raw)
            except (TypeError, ValueError):
                cx = cy = None
        try:
            t1 = float(a.get("theta1_deg", a.get("theta1", 0)))
            t2 = float(a.get("theta2_deg", a.get("theta2", 90)))
        except (TypeError, ValueError):
            t1, t2 = 0.0, 90.0
        arcs.append(
            {
                "center_id": str(a.get("center_id") or "").strip(),
                "cx": cx,
                "cy": cy,
                "r": min(r, 1e6),
                "theta1_deg": t1,
                "theta2_deg": t2,
                "fill": bool(a.get("fill", False)),
                "fill_color": str(a.get("fill_color") or ""),
                "edge_color": str(a.get("edge_color") or ""),
            }
        )

    point_ids = {str(p.get("id") or "").strip() for p in points}
    circles = [
        c
        for c in circles
        if (c["center_id"] and c["center_id"] in point_ids) or (c["cx"] is not None and c["cy"] is not None)
    ]
    arcs = [
        a
        for a in arcs
        if (a["center_id"] and a["center_id"] in point_ids) or (a["cx"] is not None and a["cy"] is not None)
    ]
    polygons = [p for p in polygons if all(vid in point_ids for vid in p["vertex_ids"])]

    has_lbl = any(str(lb.get("text") or "").strip() for lb in labels)
    has_extra = bool(circles or polygons or arcs)
    if not points and not segments and not has_lbl and not has_extra:
        return None
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "points": points,
        "segments": segments,
        "labels": labels,
        "circles": circles,
        "polygons": polygons,
        "arcs": arcs,
    }


def _normalize_flowchart_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    nodes_raw = spec.get("nodes")
    if not isinstance(nodes_raw, list):
        nodes_raw = []
    nodes: list[dict[str, str]] = []
    for n in nodes_raw[:32]:
        if not isinstance(n, dict):
            continue
        um = n.get("use_mathtext", False)
        use_mt = bool(um) if isinstance(um, bool) else str(um).strip().lower() in ("1", "true", "yes")
        nodes.append(
            {
                "id": str(n.get("id") or "").strip(),
                "text": str(n.get("text") or ""),
                "use_mathtext": use_mt,
            }
        )
    edges_raw = spec.get("edges")
    if not isinstance(edges_raw, list):
        edges_raw = []
    edges: list[dict[str, str]] = []
    for e in edges_raw[:64]:
        if not isinstance(e, dict):
            continue
        edges.append(
            {
                "source": str(e.get("source") or "").strip(),
                "target": str(e.get("target") or "").strip(),
            }
        )
    if not nodes:
        return None
    lay = str(spec.get("layout", "circular")).strip().lower()
    layout = "layered" if lay == "layered" else "circular"
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "layout": layout,
        "nodes": nodes,
        "edges": edges,
    }


_CIRCUIT_ELEMENTS = frozenset(
    {
        "wire",
        "resistor",
        "cell",
        "battery",
        "capacitor",
        "lamp",
        "switch",
        "rheostat",
        "fuse",
        "diode",
        "ammeter",
        "voltmeter",
        "generic",
    }
)


def _normalize_force_diagram_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    forces_raw = spec.get("forces")
    if not isinstance(forces_raw, list):
        forces_raw = []
    forces: list[dict[str, Any]] = []
    for f in forces_raw[:16]:
        if not isinstance(f, dict):
            continue
        try:
            x0 = float(f.get("x0", 0))
            y0 = float(f.get("y0", 0))
            if f.get("x1") is not None and f.get("y1") is not None:
                x1 = float(f.get("x1"))
                y1 = float(f.get("y1"))
            else:
                dx = float(f.get("dx", 0))
                dy = float(f.get("dy", 0))
                x1, y1 = x0 + dx, y0 + dy
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            continue
        if abs(x1 - x0) < 1e-9 and abs(y1 - y0) < 1e-9:
            continue
        zo = f.get("zorder", 2)
        try:
            zorder = int(zo)
        except (TypeError, ValueError):
            zorder = 2
        um = f.get("use_mathtext", False)
        use_mt = bool(um) if isinstance(um, bool) else str(um).strip().lower() in ("1", "true", "yes")
        forces.append(
            {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "label": str(f.get("label") or ""),
                "use_mathtext": use_mt,
                "color": str(f.get("color") or ""),
                "zorder": zorder,
            }
        )
    if not forces:
        return None
    od = spec.get("object_dot", False)
    object_dot = bool(od) if isinstance(od, bool) else str(od).strip().lower() in ("1", "true", "yes")
    try:
        ox = float(spec.get("object_x", 0))
        oy = float(spec.get("object_y", 0))
    except (TypeError, ValueError):
        ox, oy = 0.0, 0.0
    os_raw = str(spec.get("object_style") or "dot").strip().lower()
    object_style = "block" if os_raw == "block" else "dot"
    sah = spec.get("show_axes_hint", False)
    show_axes_hint = bool(sah) if isinstance(sah, bool) else str(sah).strip().lower() in ("1", "true", "yes")
    nrm = spec.get("normalize_force_lengths", False)
    normalize_force_lengths = bool(nrm) if isinstance(nrm, bool) else str(nrm).strip().lower() in ("1", "true", "yes")
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "forces": forces,
        "object_dot": object_dot,
        "object_x": ox,
        "object_y": oy,
        "object_style": object_style,
        "show_axes_hint": show_axes_hint,
        "normalize_force_lengths": normalize_force_lengths,
    }


def _normalize_circuit_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    nodes_raw = spec.get("nodes")
    if not isinstance(nodes_raw, list):
        nodes_raw = []
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for n in nodes_raw[:24]:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        if not nid or nid in seen:
            continue
        try:
            x = float(n.get("x", 0))
            y = float(n.get("y", 0))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(x) and math.isfinite(y)):
            continue
        seen.add(nid)
        nodes.append({"id": nid, "x": x, "y": y})
    edges_raw = spec.get("edges")
    if not isinstance(edges_raw, list):
        edges_raw = []
    id_set = {n["id"] for n in nodes}
    edges: list[dict[str, Any]] = []
    for e in edges_raw[:32]:
        if not isinstance(e, dict):
            continue
        src = str(e.get("source") or "").strip()
        tgt = str(e.get("target") or "").strip()
        if not src or not tgt or src not in id_set or tgt not in id_set:
            continue
        el = str(e.get("element") or "wire").strip().lower()
        if el in ("cap", "电容", "电容器"):
            el = "capacitor"
        elif el in ("battery", "电池", "电池组", "蓄电池"):
            el = "battery"
        elif el in ("rheostat", "变阻器", "滑动变阻器"):
            el = "rheostat"
        elif el in ("fuse", "保险丝", "熔断器"):
            el = "fuse"
        elif el in ("diode", "二极管"):
            el = "diode"
        if el not in _CIRCUIT_ELEMENTS:
            el = "wire"
        switch_state_raw = str(e.get("switch_state") or e.get("state") or "").strip().lower()
        if switch_state_raw in ("闭合", "接通", "closed", "on", "1", "true"):
            switch_state = "closed"
        elif switch_state_raw in ("断开", "开路", "open", "off", "0", "false"):
            switch_state = "open"
        else:
            switch_state = "default"
        slider_position: float | None = None
        slider_raw = e.get("slider_position", e.get("slider_t", e.get("wiper_t")))
        if slider_raw is not None:
            try:
                slider_val = float(slider_raw)
            except (TypeError, ValueError):
                slider_val = float("nan")
            if math.isfinite(slider_val):
                slider_position = min(1.0, max(0.0, slider_val))
        via_list: list[dict[str, float]] = []
        vraw = e.get("via")
        if isinstance(vraw, list):
            for v in vraw[:8]:
                if not isinstance(v, dict):
                    continue
                try:
                    vx = float(v.get("x", 0))
                    vy = float(v.get("y", 0))
                except (TypeError, ValueError):
                    continue
                if math.isfinite(vx) and math.isfinite(vy):
                    via_list.append({"x": vx, "y": vy})
        edges.append(
            {
                "source": src,
                "target": tgt,
                "element": el,
                "via": via_list,
                "switch_state": switch_state,
                "slider_position": slider_position,
            }
        )
    if len(nodes) < 2 or not edges:
        return None
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "nodes": nodes,
        "edges": edges,
    }


def _normalize_pie_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    labels = spec.get("labels")
    vals = spec.get("values")
    if not isinstance(labels, list) or not isinstance(vals, list) or not labels or not vals:
        return None
    try:
        vf = [float(v) for v in vals]
    except (TypeError, ValueError):
        return None
    if any(v < 0 for v in vf):
        return None
    sl = [str(lab).strip() if lab is not None else "" for lab in labels]
    if len(sl) != len(vf) or len(sl) == 0:
        return None
    if sum(vf) <= 0:
        return None
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "labels": sl,
        "values": vf,
    }


def _normalize_table_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    rows_raw = spec.get("rows")
    if not isinstance(rows_raw, list) or not rows_raw:
        return None
    rows: list[list[str]] = []
    for r in rows_raw[:32]:
        if isinstance(r, list):
            rows.append([str(c)[:500] if c is not None else "" for c in r[:16]])
        elif r is not None:
            rows.append([str(r)])
    if not rows:
        return None
    ncol = max(len(x) for x in rows)
    if ncol < 1:
        return None
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    hdr_raw = spec.get("headers")
    headers: list[str] = []
    if isinstance(hdr_raw, list) and hdr_raw:
        headers = [str(h)[:500] if h is not None else "" for h in hdr_raw[:ncol]]
        while len(headers) < ncol:
            headers.append("")
        headers = headers[:ncol]
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "headers": headers,
        "rows": rows,
    }


def _normalize_timeline_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    items_raw = spec.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        return None
    items: list[dict[str, Any]] = []
    for it in items_raw[:24]:
        if not isinstance(it, dict):
            continue
        try:
            t = float(it.get("t", 0))
        except (TypeError, ValueError):
            continue
        items.append({"label": str(it.get("label") or ""), "t": t})
    if not items:
        return None
    cn = spec.get("connect", True)
    connect = bool(cn) if isinstance(cn, bool) else str(cn).strip().lower() not in ("0", "false", "no")
    t_min = spec.get("t_min")
    t_max = spec.get("t_max")
    out: dict[str, Any] = {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "items": items,
        "connect": connect,
    }
    if t_min is not None:
        try:
            out["t_min"] = float(t_min)
        except (TypeError, ValueError):
            pass
    if t_max is not None:
        try:
            out["t_max"] = float(t_max)
        except (TypeError, ValueError):
            pass
    return out


def _normalize_number_line_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    try:
        x_min = float(spec.get("x_min", 0))
        x_max = float(spec.get("x_max", 1))
    except (TypeError, ValueError):
        return None
    if x_max <= x_min:
        return None
    marks: list[dict[str, Any]] = []
    for m in (spec.get("marks") or [])[:32]:
        if not isinstance(m, dict):
            continue
        try:
            x = float(m.get("x", 0))
        except (TypeError, ValueError):
            continue
        marks.append({"x": x, "label": str(m.get("label") or "")})
    intervals: list[dict[str, Any]] = []
    for iv in (spec.get("intervals") or [])[:32]:
        if not isinstance(iv, dict):
            continue
        try:
            a = float(iv.get("a", 0))
            b = float(iv.get("b", 0))
        except (TypeError, ValueError):
            continue
        ol = iv.get("open_left", False)
        or_ = iv.get("open_right", False)
        intervals.append(
            {
                "a": a,
                "b": b,
                "open_left": bool(ol) if isinstance(ol, bool) else str(ol).lower() in ("1", "true", "yes"),
                "open_right": bool(or_) if isinstance(or_, bool) else str(or_).lower() in ("1", "true", "yes"),
            }
        )
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "x_min": x_min,
        "x_max": x_max,
        "marks": marks,
        "intervals": intervals,
    }


def _normalize_venn_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    ns = spec.get("n_sets", 2)
    try:
        n_sets = int(ns)
    except (TypeError, ValueError):
        n_sets = 2
    if n_sets not in (2, 3):
        n_sets = 2
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "n_sets": n_sets,
        "label_a": str(spec.get("label_a") or "A"),
        "label_b": str(spec.get("label_b") or "B"),
        "label_c": str(spec.get("label_c") or "C"),
        "only_a": str(spec.get("only_a") or ""),
        "only_b": str(spec.get("only_b") or ""),
        "only_c": str(spec.get("only_c") or ""),
        "ab": str(spec.get("ab") or ""),
        "ac": str(spec.get("ac") or ""),
        "bc": str(spec.get("bc") or ""),
        "abc": str(spec.get("abc") or ""),
    }


def _normalize_svg_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    raw = spec.get("svg")
    if raw is None:
        raw = spec.get("content")
    s = str(raw or "").strip()
    if not s or "<svg" not in s.lower():
        return None
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "svg": s,
    }


def _normalize_histogram_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    edges_raw = spec.get("edges")
    counts_raw = spec.get("counts")
    if not isinstance(edges_raw, list) or not isinstance(counts_raw, list):
        return None
    if len(edges_raw) < 2:
        return None
    try:
        edges = [float(v) for v in edges_raw]
        counts = [float(v) for v in counts_raw]
    except (TypeError, ValueError):
        return None
    if len(counts) != len(edges) - 1:
        return None
    if any(counts[i] < 0 for i in range(len(counts))):
        return None
    for i in range(len(edges) - 1):
        if edges[i + 1] <= edges[i]:
            return None
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "x_label": str(spec.get("x_label") or ""),
        "y_label": str(spec.get("y_label") or ""),
        "edges": edges,
        "counts": counts,
    }


def _normalize_solid_wireframe_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    proj = str(spec.get("projection") or "isometric").strip().lower()
    if proj == "cabinet":
        projection = "cabinet"
    elif proj in ("oblique", "斜二测", "cavalier", "pep_oblique"):
        projection = "oblique"
    else:
        projection = "isometric"
    verts_raw = spec.get("vertices")
    if not isinstance(verts_raw, list) or len(verts_raw) < 2:
        return None
    vertices: list[dict[str, Any]] = []
    for v in verts_raw[:80]:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("id") or "").strip()
        if not vid:
            continue
        try:
            vx = float(v.get("x", 0))
            vy = float(v.get("y", 0))
            vz = float(v.get("z", 0))
        except (TypeError, ValueError):
            continue
        vertices.append({"id": vid, "x": vx, "y": vy, "z": vz})
    if len(vertices) < 2:
        return None
    id_set = {v["id"] for v in vertices}
    edges_raw = spec.get("edges")
    if not isinstance(edges_raw, list):
        return None
    edges: list[dict[str, str]] = []
    for e in edges_raw[:200]:
        if not isinstance(e, dict):
            continue
        a = str(e.get("a") or "").strip()
        b = str(e.get("b") or "").strip()
        if a and b and a in id_set and b in id_set and a != b:
            edges.append({"a": a, "b": b})
    if not edges:
        return None
    faces: list[dict[str, Any]] = []
    for f in (spec.get("faces") or [])[:32]:
        if not isinstance(f, dict):
            continue
        vids = [str(x).strip() for x in (f.get("vertex_ids") or []) if str(x).strip()]
        vids = [x for x in vids if x in id_set]
        if len(vids) < 3:
            continue
        try:
            al = float(f.get("alpha", 0.35))
        except (TypeError, ValueError):
            al = 0.35
        faces.append(
            {
                "vertex_ids": vids[:24],
                "alpha": max(0.0, min(1.0, al)),
                "fill_color": str(f.get("fill_color") or ""),
                "edge_color": str(f.get("edge_color") or ""),
            }
        )
    labels: list[dict[str, Any]] = []
    for lb in (spec.get("labels") or [])[:32]:
        if not isinstance(lb, dict):
            continue
        try:
            lx = float(lb.get("x", 0))
            ly = float(lb.get("y", 0))
        except (TypeError, ValueError):
            continue
        um = lb.get("use_mathtext", False)
        labels.append(
            {
                "text": str(lb.get("text") or ""),
                "x": lx,
                "y": ly,
                "use_mathtext": bool(um) if isinstance(um, bool) else str(um).lower() in ("1", "true", "yes"),
            }
        )

    def _face_list(key: str) -> list[dict[str, Any]]:
        out_f: list[dict[str, Any]] = []
        for f in (spec.get(key) or [])[:32]:
            if not isinstance(f, dict):
                continue
            vids = [str(x).strip() for x in (f.get("vertex_ids") or []) if str(x).strip()]
            vids = [x for x in vids if x in id_set]
            if len(vids) < 3:
                continue
            try:
                al = float(f.get("alpha", 0.35))
            except (TypeError, ValueError):
                al = 0.35
            out_f.append(
                {
                    "vertex_ids": vids[:24],
                    "alpha": max(0.0, min(1.0, al)),
                    "fill_color": str(f.get("fill_color") or ""),
                    "edge_color": str(f.get("edge_color") or ""),
                }
            )
        return out_f

    section_faces = _face_list("section_faces")
    aux_edges: list[dict[str, Any]] = []
    for ae in (spec.get("auxiliary_edges") or [])[:64]:
        if not isinstance(ae, dict):
            continue
        a = str(ae.get("a") or "").strip()
        b = str(ae.get("b") or "").strip()
        if not a or not b or a not in id_set or b not in id_set:
            continue
        st = str(ae.get("style") or "dashed").strip().lower()
        if st not in ("solid", "dashed"):
            st = "dashed"
        aux_edges.append({"a": a, "b": b, "style": st, "label": str(ae.get("label") or "")})
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "projection": projection,
        "vertices": vertices,
        "edges": edges,
        "faces": faces,
        "section_faces": section_faces,
        "auxiliary_edges": aux_edges,
        "labels": labels,
    }


def _normalize_field_preset_dict(d: dict[str, Any]) -> dict[str, Any] | None:
    k = str(d.get("kind", "")).strip().lower()
    if k == "point_charge":
        try:
            cx = float(d.get("cx", 0))
            cy = float(d.get("cy", 0))
        except (TypeError, ValueError):
            return None
        sg = d.get("sign", 1)
        try:
            si = int(sg)
        except (TypeError, ValueError):
            si = 1
        if si not in (-1, 1):
            si = 1
        try:
            n_lines = int(d.get("n_lines", 12))
        except (TypeError, ValueError):
            n_lines = 12
        n_lines = max(3, min(48, n_lines))
        try:
            r_max = float(d.get("r_max", 1.6))
            r_min = float(d.get("r_min", 0.1))
        except (TypeError, ValueError):
            r_max, r_min = 1.6, 0.1
        if r_max <= 0 or r_min >= r_max:
            return None
        return {
            "kind": "point_charge",
            "cx": cx,
            "cy": cy,
            "sign": si,
            "n_lines": n_lines,
            "r_max": r_max,
            "r_min": r_min,
            "color": str(d.get("color") or ""),
        }
    if k == "solenoid":
        try:
            x0 = float(d.get("x0", 0))
            y0 = float(d.get("y0", 0))
            w = float(d.get("w", 1.8))
            h = float(d.get("h", 2.2))
        except (TypeError, ValueError):
            return None
        if w <= 0 or h <= 0:
            return None
        bd = str(d.get("b_direction") or "right").strip().lower()
        if bd not in ("up", "down", "left", "right"):
            bd = "right"
        try:
            nx = int(d.get("nx", 4))
            ny = int(d.get("ny", 5))
        except (TypeError, ValueError):
            nx, ny = 4, 5
        nx = max(1, min(12, nx))
        ny = max(1, min(12, ny))
        df = d.get("draw_frame", True)
        draw_frame = bool(df) if isinstance(df, bool) else str(df).lower() not in ("0", "false", "no")
        return {
            "kind": "solenoid",
            "x0": x0,
            "y0": y0,
            "w": w,
            "h": h,
            "b_direction": bd,
            "nx": nx,
            "ny": ny,
            "draw_frame": draw_frame,
            "color": str(d.get("color") or ""),
        }
    if k in ("long_straight_wire", "straight_wire"):
        try:
            cx = float(d.get("cx", 0))
            cy = float(d.get("cy", 0))
            r_max = float(d.get("r_max", 2.0))
        except (TypeError, ValueError):
            return None
        if r_max <= 0:
            return None
        try:
            n_circles = int(d.get("n_circles", 6))
        except (TypeError, ValueError):
            n_circles = 6
        n_circles = max(2, min(20, n_circles))
        cop = d.get("current_out_of_page", True)
        current_out = bool(cop) if isinstance(cop, bool) else str(cop).lower() not in ("0", "false", "no")
        try:
            arc_fraction = float(d.get("arc_fraction", 0.92))
        except (TypeError, ValueError):
            arc_fraction = 0.92
        arc_fraction = max(0.5, min(1.0, arc_fraction))
        return {
            "kind": "long_straight_wire",
            "cx": cx,
            "cy": cy,
            "n_circles": n_circles,
            "r_max": r_max,
            "current_out_of_page": current_out,
            "arc_fraction": arc_fraction,
            "color": str(d.get("color") or ""),
        }
    return None


def _normalize_field_lines_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    lines: list[dict[str, Any]] = []
    lines_raw = spec.get("lines")
    if isinstance(lines_raw, list):
        for ln in lines_raw[:48]:
            if not isinstance(ln, dict):
                continue
            xs, ys = ln.get("x"), ln.get("y")
            if not isinstance(xs, list) or not isinstance(ys, list) or len(xs) < 2:
                continue
            try:
                xf = [float(v) for v in xs]
                yf = [float(v) for v in ys]
            except (TypeError, ValueError):
                continue
            if len(xf) != len(yf):
                continue
            ar = str(ln.get("arrow") or "end").strip().lower()
            if ar not in ("end", "start", "none"):
                ar = "end"
            lines.append(
                {
                    "x": xf,
                    "y": yf,
                    "color": str(ln.get("color") or ""),
                    "arrow": ar,
                }
            )

    presets: list[dict[str, Any]] = []
    pr_raw = spec.get("presets")
    if isinstance(pr_raw, list):
        for item in pr_raw[:12]:
            if not isinstance(item, dict):
                continue
            one = _normalize_field_preset_dict(item)
            if one:
                presets.append(one)

    uf_raw = spec.get("uniform_field")
    uniform_field: dict[str, Any] | None = None
    if isinstance(uf_raw, dict):
        try:
            udx = float(uf_raw.get("dx", 1))
            udy = float(uf_raw.get("dy", 0))
        except (TypeError, ValueError):
            udx, udy = 1.0, 0.0
        uniform_field = {
            "dx": udx,
            "dy": udy,
            "label": str(uf_raw.get("label") or ""),
        }

    if not lines and not presets and uniform_field is None:
        return None
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "lines": lines,
        "presets": presets,
        "uniform_field": uniform_field,
    }


def _normalize_probability_tree_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    nodes_raw = spec.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        return None
    nodes: list[dict[str, Any]] = []
    for n in nodes_raw[:40]:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        if not nid:
            continue
        pid = str(n.get("parent_id") or "").strip()
        nodes.append(
            {
                "id": nid,
                "text": str(n.get("text") or ""),
                "parent_id": pid,
                "edge_label": str(n.get("edge_label") or ""),
                "leaf_note": str(n.get("leaf_note") or ""),
            }
        )
    if not nodes:
        return None
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "nodes": nodes,
    }


def _normalize_pedigree_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    ind_raw = spec.get("individuals")
    if not isinstance(ind_raw, list) or not ind_raw:
        return None
    individuals: list[dict[str, Any]] = []
    for p in ind_raw[:40]:
        if not isinstance(p, dict):
            continue
        pid = str(p.get("id") or "").strip()
        if not pid:
            continue
        try:
            gen = int(p.get("generation", 0))
        except (TypeError, ValueError):
            gen = 0
        sx = str(p.get("sex") or "unknown").strip().lower()
        if sx in ("m", "male", "男"):
            sex = "male"
        elif sx in ("f", "female", "女"):
            sex = "female"
        else:
            sex = "unknown"
        xh = p.get("x_hint")
        x_hint: float | None = None
        if xh is not None:
            try:
                xf = float(xh)
                if math.isfinite(xf):
                    x_hint = max(0.0, min(1.0, xf))
            except (TypeError, ValueError):
                x_hint = None
        af = p.get("affected", False)
        cr = p.get("carrier", False)
        dec = p.get("deceased", False)
        individuals.append(
            {
                "id": pid,
                "generation": max(0, min(20, gen)),
                "sex": sex,
                "affected": bool(af) if isinstance(af, bool) else str(af).lower() in ("1", "true", "yes"),
                "carrier": bool(cr) if isinstance(cr, bool) else str(cr).lower() in ("1", "true", "yes"),
                "deceased": bool(dec) if isinstance(dec, bool) else str(dec).lower() in ("1", "true", "yes"),
                "x_hint": x_hint,
            }
        )
    if not individuals:
        return None
    marriages: list[dict[str, str]] = []
    for m in (spec.get("marriages") or [])[:24]:
        if not isinstance(m, dict):
            continue
        marriages.append(
            {
                "left": str(m.get("left") or "").strip(),
                "right": str(m.get("right") or "").strip(),
            }
        )
    descents: list[dict[str, str]] = []
    for d in (spec.get("descents") or [])[:40]:
        if not isinstance(d, dict):
            continue
        descents.append(
            {
                "mother": str(d.get("mother") or "").strip(),
                "father": str(d.get("father") or "").strip(),
                "child": str(d.get("child") or "").strip(),
            }
        )
    pb = str(spec.get("proband_id") or "").strip()
    sl = spec.get("show_legend", False)
    show_legend = bool(sl) if isinstance(sl, bool) else str(sl).strip().lower() in ("1", "true", "yes")
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "individuals": individuals,
        "marriages": marriages,
        "descents": descents,
        "proband_id": pb,
        "show_legend": show_legend,
    }


def _normalize_energy_profile_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    xs_raw, ys_raw = spec.get("x"), spec.get("y")
    if not isinstance(xs_raw, list) or not isinstance(ys_raw, list):
        return None
    if len(xs_raw) < 2:
        return None
    try:
        xf = [float(v) for v in xs_raw]
        yf = [float(v) for v in ys_raw]
    except (TypeError, ValueError):
        return None
    if len(xf) != len(yf):
        return None
    n = len(xf)
    bi = spec.get("barrier_i")
    bj = spec.get("barrier_j")
    barrier_i: int | None = None
    barrier_j: int | None = None
    if bi is not None:
        try:
            ii = int(bi)
            if 0 <= ii < n:
                barrier_i = ii
        except (TypeError, ValueError):
            pass
    if bj is not None:
        try:
            jj = int(bj)
            if 0 <= jj < n:
                barrier_j = jj
        except (TypeError, ValueError):
            pass
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "x_label": str(spec.get("x_label") or ""),
        "y_label": str(spec.get("y_label") or ""),
        "x": xf,
        "y": yf,
        "barrier_i": barrier_i,
        "barrier_j": barrier_j,
        "barrier_label": str(spec.get("barrier_label") or ""),
    }


def _normalize_electrochemical_cell_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    md = str(spec.get("mode") or "galvanic").strip().lower()
    mode = "electrolytic" if md in ("electrolytic", "electrolysis", "电解") else "galvanic"
    ecw = spec.get("electron_cw", True)
    electron_cw = bool(ecw) if isinstance(ecw, bool) else str(ecw).lower() not in ("0", "false", "no")
    ct = str(spec.get("cation_to") or "right").strip().lower()
    if ct not in ("left", "right", "none"):
        ct = "right"
    at = str(spec.get("anion_to") or "left").strip().lower()
    if at not in ("left", "right", "none"):
        at = "left"
    sb = spec.get("salt_bridge_u", False)
    if isinstance(sb, bool):
        salt_bridge_u = sb
    else:
        sbs = str(sb).strip().lower()
        salt_bridge_u = sbs in ("1", "true", "yes", "u", "盐桥")
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "left_label": str(spec.get("left_label") or ""),
        "right_label": str(spec.get("right_label") or ""),
        "electrolyte_label": str(spec.get("electrolyte_label") or ""),
        "mode": mode,
        "electron_cw": electron_cw,
        "cation_to": ct,
        "anion_to": at,
        "salt_bridge_u": salt_bridge_u,
    }


def _normalize_unit_circle_trig_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    try:
        ang = float(spec.get("angle_deg", 45))
    except (TypeError, ValueError):
        ang = 45.0
    ss = spec.get("show_sin", True)
    sc = spec.get("show_cos", True)
    st = spec.get("show_tan", False)
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "angle_deg": ang,
        "show_sin": bool(ss) if isinstance(ss, bool) else str(ss).lower() not in ("0", "false", "no"),
        "show_cos": bool(sc) if isinstance(sc, bool) else str(sc).lower() not in ("0", "false", "no"),
        "show_tan": bool(st) if isinstance(st, bool) else str(st).lower() in ("1", "true", "yes"),
        "angle_label": str(spec.get("angle_label") or ""),
    }


def _normalize_optics_ray_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    try:
        iy = float(spec.get("interface_y", 0))
    except (TypeError, ValueError):
        iy = 0.0
    sn = spec.get("show_normal", True)
    rays_raw = spec.get("rays")
    if not isinstance(rays_raw, list):
        return None
    rays: list[dict[str, Any]] = []
    for r in rays_raw[:24]:
        if not isinstance(r, dict):
            continue
        try:
            x0 = float(r.get("x0", 0))
            y0 = float(r.get("y0", 0))
            x1 = float(r.get("x1", 1))
            y1 = float(r.get("y1", 0))
        except (TypeError, ValueError):
            continue
        st = str(r.get("style") or "solid").strip().lower()
        if st not in ("solid", "dashed"):
            st = "solid"
        rays.append(
            {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "label": str(r.get("label") or ""),
                "color": str(r.get("color") or ""),
                "style": st,
            }
        )
    if not rays:
        return None
    ori = str(spec.get("interface_orientation") or "horizontal").strip().lower()
    if ori not in ("horizontal", "vertical", "angled"):
        ori = "horizontal"
    try:
        ix = float(spec.get("interface_x", 0))
        ipx = float(spec.get("interface_pivot_x", 0))
        ipy = float(spec.get("interface_pivot_y", 0))
        iang = float(spec.get("interface_angle_deg", 0))
    except (TypeError, ValueError):
        ix = ipx = ipy = iang = 0.0
    pa_raw = spec.get("principal_axis")
    principal_axis: dict[str, float] | None = None
    if isinstance(pa_raw, dict):
        try:
            principal_axis = {
                "x0": float(pa_raw.get("x0", 0)),
                "y0": float(pa_raw.get("y0", 0)),
                "x1": float(pa_raw.get("x1", 1)),
                "y1": float(pa_raw.get("y1", 0)),
            }
        except (TypeError, ValueError):
            principal_axis = None
    tl_raw = spec.get("thin_lens")
    thin_lens: dict[str, Any] | None = None
    if isinstance(tl_raw, dict):
        try:
            tcx = float(tl_raw.get("center_x", 0))
            tcy = float(tl_raw.get("center_y", 0))
            td = float(tl_raw.get("diameter", 1.2))
        except (TypeError, ValueError):
            tcx = tcy = 0.0
            td = 1.2
        if td > 0:
            cv = tl_raw.get("convex_toward_right", True)
            convex = bool(cv) if isinstance(cv, bool) else str(cv).lower() not in ("0", "false", "no")
            thin_lens = {
                "center_x": tcx,
                "center_y": tcy,
                "diameter": td,
                "convex_toward_right": convex,
            }
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "interface_orientation": ori,
        "interface_y": iy,
        "interface_x": ix,
        "interface_pivot_x": ipx,
        "interface_pivot_y": ipy,
        "interface_angle_deg": iang,
        "medium_top_label": str(spec.get("medium_top_label") or ""),
        "medium_bottom_label": str(spec.get("medium_bottom_label") or ""),
        "show_normal": bool(sn) if isinstance(sn, bool) else str(sn).lower() not in ("0", "false", "no"),
        "principal_axis": principal_axis,
        "thin_lens": thin_lens,
        "rays": rays,
    }


def _normalize_directed_graph_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    nodes_raw = spec.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        return None
    nodes: list[dict[str, Any]] = []
    for n in nodes_raw[:40]:
        if not isinstance(n, dict):
            continue
        nid = str(n.get("id") or "").strip()
        if not nid:
            continue
        try:
            layer = int(n.get("layer", 0))
        except (TypeError, ValueError):
            layer = 0
        layer = max(0, min(40, layer))
        um = n.get("use_mathtext", False)
        nodes.append(
            {
                "id": nid,
                "text": str(n.get("text") or ""),
                "layer": layer,
                "use_mathtext": bool(um) if isinstance(um, bool) else str(um).lower() in ("1", "true", "yes"),
            }
        )
    if not nodes:
        return None
    edges: list[dict[str, str]] = []
    for e in (spec.get("edges") or [])[:80]:
        if not isinstance(e, dict):
            continue
        s = str(e.get("source") or "").strip()
        t = str(e.get("target") or "").strip()
        if s and t:
            edges.append({"source": s, "target": t, "label": str(e.get("label") or "")})
    lay = str(spec.get("layout") or "layered").strip().lower()
    if lay not in ("layered", "circular"):
        lay = "layered"
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "layout": lay,
        "nodes": nodes,
        "edges": edges,
    }


def _normalize_composite_panel_dict(p: dict[str, Any]) -> dict[str, Any] | None:
    k = str(p.get("kind", "")).strip().lower()
    sub = p.get("spec")
    if not isinstance(sub, dict):
        return None
    subtitle = str(p.get("subtitle") or "")
    if k == "plot":
        sp = _normalize_plot_spec(sub)
        if not sp:
            return None
        return {"kind": "plot", "subtitle": subtitle, "spec": sp}
    if k == "bar":
        sp = _normalize_bar_spec(sub)
        if not sp:
            return None
        return {"kind": "bar", "subtitle": subtitle, "spec": sp}
    if k in ("grouped_bar", "groupedbar"):
        sp = _normalize_grouped_bar_spec(sub)
        if not sp:
            return None
        return {"kind": "grouped_bar", "subtitle": subtitle, "spec": sp}
    if k == "pie":
        sp = _normalize_pie_spec(sub)
        if not sp:
            return None
        return {"kind": "pie", "subtitle": subtitle, "spec": sp}
    if k == "geometry":
        sp = _normalize_geometry_spec(sub)
        if not sp:
            return None
        return {"kind": "geometry", "subtitle": subtitle, "spec": sp}
    if k == "flowchart":
        sp = _normalize_flowchart_spec(sub)
        if not sp:
            return None
        return {"kind": "flowchart", "subtitle": subtitle, "spec": sp}
    if k == "table":
        sp = _normalize_table_spec(sub)
        if not sp:
            return None
        return {"kind": "table", "subtitle": subtitle, "spec": sp}
    if k == "timeline":
        sp = _normalize_timeline_spec(sub)
        if not sp:
            return None
        return {"kind": "timeline", "subtitle": subtitle, "spec": sp}
    if k in ("number_line", "numberline"):
        sp = _normalize_number_line_spec(sub)
        if not sp:
            return None
        return {"kind": "number_line", "subtitle": subtitle, "spec": sp}
    if k == "venn":
        sp = _normalize_venn_spec(sub)
        if not sp:
            return None
        return {"kind": "venn", "subtitle": subtitle, "spec": sp}
    if k in ("histogram", "hist"):
        sp = _normalize_histogram_spec(sub)
        if not sp:
            return None
        return {"kind": "histogram", "subtitle": subtitle, "spec": sp}
    if k in ("force_diagram", "forcediagram", "force"):
        sp = _normalize_force_diagram_spec(sub)
        if not sp:
            return None
        return {"kind": "force_diagram", "subtitle": subtitle, "spec": sp}
    if k in ("circuit_simple", "circuitsimple", "circuit"):
        sp = _normalize_circuit_spec(sub)
        if not sp:
            return None
        return {"kind": "circuit_simple", "subtitle": subtitle, "spec": sp}
    if k == "svg":
        sp = _normalize_svg_spec(sub)
        if not sp:
            return None
        return {"kind": "svg", "subtitle": subtitle, "spec": sp}
    if k in ("solid_wireframe", "wireframe"):
        sp = _normalize_solid_wireframe_spec(sub)
        if not sp:
            return None
        return {"kind": "solid_wireframe", "subtitle": subtitle, "spec": sp}
    if k in ("field_lines", "fieldlines"):
        sp = _normalize_field_lines_spec(sub)
        if not sp:
            return None
        return {"kind": "field_lines", "subtitle": subtitle, "spec": sp}
    if k in ("probability_tree", "probabilitytree"):
        sp = _normalize_probability_tree_spec(sub)
        if not sp:
            return None
        return {"kind": "probability_tree", "subtitle": subtitle, "spec": sp}
    if k == "pedigree":
        sp = _normalize_pedigree_spec(sub)
        if not sp:
            return None
        return {"kind": "pedigree", "subtitle": subtitle, "spec": sp}
    if k in ("energy_profile", "energyprofile"):
        sp = _normalize_energy_profile_spec(sub)
        if not sp:
            return None
        return {"kind": "energy_profile", "subtitle": subtitle, "spec": sp}
    if k in ("electrochemical_cell", "electrochemicalcell"):
        sp = _normalize_electrochemical_cell_spec(sub)
        if not sp:
            return None
        return {"kind": "electrochemical_cell", "subtitle": subtitle, "spec": sp}
    if k in ("unit_circle_trig", "unitcircle"):
        sp = _normalize_unit_circle_trig_spec(sub)
        if not sp:
            return None
        return {"kind": "unit_circle_trig", "subtitle": subtitle, "spec": sp}
    if k in ("optics_ray", "opticsray"):
        sp = _normalize_optics_ray_spec(sub)
        if not sp:
            return None
        return {"kind": "optics_ray", "subtitle": subtitle, "spec": sp}
    if k in ("directed_graph", "directedgraph", "digraph"):
        sp = _normalize_directed_graph_spec(sub)
        if not sp:
            return None
        return {"kind": "directed_graph", "subtitle": subtitle, "spec": sp}
    return None


def _normalize_composite_spec(spec: dict[str, Any]) -> dict[str, Any] | None:
    panels_raw = spec.get("panels")
    if not isinstance(panels_raw, list) or not panels_raw:
        return None
    out_panels: list[dict[str, Any]] = []
    for p in panels_raw[:6]:
        if not isinstance(p, dict):
            continue
        one = _normalize_composite_panel_dict(p)
        if one:
            out_panels.append(one)
    if not out_panels:
        return None
    nc = spec.get("ncols", 2)
    try:
        ncols = int(nc)
    except (TypeError, ValueError):
        ncols = 2
    ncols = max(1, min(3, ncols))
    return {
        "title": str(spec.get("title") or ""),
        "caption": str(spec.get("caption") or ""),
        "ncols": ncols,
        "panels": out_panels,
    }


def _normalize_question_figure(q: dict[str, Any]) -> None:
    """将 figure_kind / figure_spec 规整为可过 PracticeSet 校验的形态；不合法则降级为 none。"""
    fk = _figure_kind_from_raw(q.get("figure_kind", "none"))
    spec = q.get("figure_spec")

    if fk == "none":
        q["figure_kind"] = "none"
        q.pop("figure_spec", None)
        return

    if not isinstance(spec, dict):
        q["figure_kind"] = "none"
        q.pop("figure_spec", None)
        return

    if fk == "plot":
        out = _normalize_plot_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "plot"
        q["figure_spec"] = out
        return

    if fk == "bar":
        out = _normalize_bar_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "bar"
        q["figure_spec"] = out
        return

    if fk == "grouped_bar":
        out = _normalize_grouped_bar_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "grouped_bar"
        q["figure_spec"] = out
        return

    if fk == "pie":
        out = _normalize_pie_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "pie"
        q["figure_spec"] = out
        return

    if fk == "geometry":
        out = _normalize_geometry_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "geometry"
        q["figure_spec"] = out
        return

    if fk == "flowchart":
        out = _normalize_flowchart_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "flowchart"
        q["figure_spec"] = out
        return

    if fk == "composite":
        out = _normalize_composite_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "composite"
        q["figure_spec"] = out
        return

    if fk == "table":
        out = _normalize_table_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "table"
        q["figure_spec"] = out
        return

    if fk == "timeline":
        out = _normalize_timeline_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "timeline"
        q["figure_spec"] = out
        return

    if fk == "number_line":
        out = _normalize_number_line_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "number_line"
        q["figure_spec"] = out
        return

    if fk == "venn":
        out = _normalize_venn_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "venn"
        q["figure_spec"] = out
        return

    if fk == "histogram":
        out = _normalize_histogram_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "histogram"
        q["figure_spec"] = out
        return

    if fk == "force_diagram":
        out = _normalize_force_diagram_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "force_diagram"
        q["figure_spec"] = out
        return

    if fk == "circuit_simple":
        out = _normalize_circuit_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "circuit_simple"
        q["figure_spec"] = out
        return

    if fk == "svg":
        out = _normalize_svg_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "svg"
        q["figure_spec"] = out
        return

    if fk == "solid_wireframe":
        out = _normalize_solid_wireframe_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "solid_wireframe"
        q["figure_spec"] = out
        return

    if fk == "field_lines":
        out = _normalize_field_lines_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "field_lines"
        q["figure_spec"] = out
        return

    if fk == "probability_tree":
        out = _normalize_probability_tree_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "probability_tree"
        q["figure_spec"] = out
        return

    if fk == "pedigree":
        out = _normalize_pedigree_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "pedigree"
        q["figure_spec"] = out
        return

    if fk == "energy_profile":
        out = _normalize_energy_profile_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "energy_profile"
        q["figure_spec"] = out
        return

    if fk == "electrochemical_cell":
        out = _normalize_electrochemical_cell_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "electrochemical_cell"
        q["figure_spec"] = out
        return

    if fk == "unit_circle_trig":
        out = _normalize_unit_circle_trig_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "unit_circle_trig"
        q["figure_spec"] = out
        return

    if fk == "optics_ray":
        out = _normalize_optics_ray_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "optics_ray"
        q["figure_spec"] = out
        return

    if fk == "directed_graph":
        out = _normalize_directed_graph_spec(spec)
        if out is None:
            q["figure_kind"] = "none"
            q.pop("figure_spec", None)
            return
        q["figure_kind"] = "directed_graph"
        q["figure_spec"] = out
        return

    q["figure_kind"] = "none"
    q.pop("figure_spec", None)


def normalize_practice_qtype(raw: str) -> str:
    """将模型返回的题型别名统一为五种标准名之一。"""
    t = (raw or "").strip()
    if t in PRACTICE_QTYPE_VALUES:
        return t
    if "多选" in t or "多项" in t:
        return "多选"
    if "判断" in t:
        return "判断"
    if "填空" in t or t in ("填",):
        return "填空"
    if any(x in t for x in ("简答", "主观", "解答", "计算", "证明", "问答", "应用", "综合", "论述")):
        return "简答"
    if "选择" in t or t in ("选",):
        return "单选"
    return "简答"


def repair_practice_dict(data: dict[str, Any]) -> dict[str, Any]:
    """修正常见类型错误：order_index 为字符串、options 为 null/单字符串等。"""
    out = dict(data)
    for k in ("knowledge_point_key", "knowledge_point_name"):
        v = out.get(k)
        if v is None:
            out[k] = ""
        else:
            out[k] = str(v).strip()

    qs = out.get("questions")
    if not isinstance(qs, list):
        out["questions"] = []
        return out

    fixed: list[dict[str, Any]] = []
    for i, raw in enumerate(qs):
        if not isinstance(raw, dict):
            continue
        q = dict(raw)
        oi = q.get("order_index", i + 1)
        if isinstance(oi, str):
            oi = oi.strip()
            try:
                oi = int(oi)
            except ValueError:
                oi = i + 1
        elif not isinstance(oi, int):
            try:
                oi = int(oi)
            except (TypeError, ValueError):
                oi = i + 1
        q["order_index"] = oi

        qt = q.get("qtype")
        q["qtype"] = normalize_practice_qtype(str(qt) if qt is not None else "填空")

        for sk in ("stem", "answer_outline"):
            v = q.get(sk)
            q[sk] = str(v) if v is not None else ""

        if not str(q.get("stem", "")).strip():
            q["stem"] = "（题干暂缺，请重新生成本题。）"

        opt = q.get("options")
        if opt is None:
            q["options"] = []
        elif isinstance(opt, str):
            q["options"] = [opt] if opt.strip() else []
        elif isinstance(opt, list):
            q["options"] = [str(x) for x in opt if x is not None and str(x).strip() != ""]
        else:
            q["options"] = []

        so = q.get("source_question_order")
        if so is not None and so != "":
            try:
                q["source_question_order"] = int(so)
            except (TypeError, ValueError):
                q["source_question_order"] = None
        else:
            q["source_question_order"] = None

        upf = q.get("use_paper_figure", False)
        if isinstance(upf, bool):
            q["use_paper_figure"] = upf
        else:
            q["use_paper_figure"] = str(upf).strip().lower() in ("1", "true", "yes")

        pir = q.get("paper_image_ref")
        if pir is not None and str(pir).strip():
            q["paper_image_ref"] = str(pir).strip()
        else:
            q["paper_image_ref"] = None

        _normalize_question_figure(q)
        fixed.append(q)

    out["questions"] = fixed
    return out


def parse_practice_set_from_llm_text(text: str) -> PracticeSet:
    """扫描多段 JSON 候选，先 repair 再校验 PracticeSet。"""
    last_err: ValidationError | None = None
    for d in iter_candidate_dicts_from_llm(text):
        if not isinstance(d, dict) or "questions" not in d:
            continue
        try:
            return PracticeSet.model_validate(repair_practice_dict(d))
        except ValidationError as e:
            last_err = e
            continue
    if last_err is None:
        raise ValueError("未在模型输出中找到可识别的练习题 JSON。")
    n = last_err.error_count()
    raise ValueError(
        f"练习题 JSON 校验未通过（共 {n} 处字段问题）。"
        "常见原因：缺少 knowledge_point_key / questions、某题缺少题干 stem。"
    ) from last_err

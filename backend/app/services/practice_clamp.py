"""练习集字段过长时截断，避免 JSON 损坏与 PDF 渲染异常。"""

from __future__ import annotations

import logging
import math

# 题干出现下列词且 plot 点数过少时，视为用折线冒充光滑曲线，整题去图。
_SMOOTH_CURVE_STEM_KEYS: tuple[str, ...] = (
    "二次函数",
    "抛物线",
    "反比例函数",
    "反比例",
    "指数函数",
    "对数函数",
    "幂函数",
    "三角函数",
    "正弦",
    "余弦",
    "正切",
)
_MIN_PLOT_POINTS_FOR_SMOOTH_CONTEXT = 15

from app.models.schemas import (
    PracticeBarSpec,
    PracticeCircuitEdge,
    PracticeCircuitNode,
    PracticeCircuitSpec,
    PracticeCircuitVia,
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
    PracticeFieldLine,
    PracticeFieldLinesSpec,
    PracticeFieldPresetLongStraightWire,
    PracticeFieldPresetPointCharge,
    PracticeFieldPresetSolenoid,
    PracticeFlowchartEdge,
    PracticeFlowchartNode,
    PracticeFlowchartSpec,
    PracticeForceDiagramSpec,
    PracticeForceItem,
    PracticeGeometryArc,
    PracticeGeometryCircle,
    PracticeGeometryLabel,
    PracticeGeometryPolygon,
    PracticeGeometrySpec,
    PracticeGroupedBarSeries,
    PracticeGroupedBarSpec,
    PracticeHistogramSpec,
    PracticeNumberLineInterval,
    PracticeNumberLineMark,
    PracticeNumberLineSpec,
    PracticeDirectedGraphEdge,
    PracticeDirectedGraphNode,
    PracticeDirectedGraphSpec,
    PracticeOpticsPrincipalAxis,
    PracticeOpticsRaySegment,
    PracticeOpticsRaySpec,
    PracticeOpticsThinLens,
    PracticePedigreeDescent,
    PracticePedigreeIndividual,
    PracticePedigreeMarriage,
    PracticePedigreeSpec,
    PracticePieSpec,
    PracticePlotFillBetween,
    PracticePlotSeries,
    PracticePlotSpec,
    PracticeProbabilityTreeNode,
    PracticeProbabilityTreeSpec,
    PracticeSet,
    PracticeSolidAuxiliaryEdge,
    PracticeSolidEdge,
    PracticeSolidFace,
    PracticeSolidVertex3D,
    PracticeSolidWireframeSpec,
    PracticeSvgSpec,
    PracticeTableSpec,
    PracticeTimelineItem,
    PracticeTimelineSpec,
    PracticeUniformField,
    PracticeUnitCircleTrigSpec,
    PracticeVennSpec,
)
from app.services.practice_path_security import resolve_under_data_dir
from app.services.practice_svg_safe import sanitize_practice_svg

_MAX_STEM = 4000
_MAX_OUTLINE = 6000
_MAX_OPTION_LEN = 800

_MAX_FIG_POINTS = 200
_MAX_FIG_SERIES = 5
_MAX_FIG_CAPTION = 220
_MAX_FIG_TITLE = 120
_MAX_FIG_AXIS_LABEL = 80
_MAX_FIG_SERIES_LABEL = 80

_MAX_BAR_ITEMS = 32
_MAX_BAR_CAT_LEN = 48
_MAX_PIE_SLICES = 16
_MAX_PIE_LABEL_LEN = 48
_MAX_GEOM_POINTS = 64
_MAX_GEOM_SEGMENTS = 128
_MAX_GEOM_LABELS = 32
_MAX_GEOM_CIRCLES = 16
_MAX_GEOM_POLYGONS = 16
_MAX_GEOM_ARCS = 24
_MAX_GEOM_POLY_VERTS = 24
_MAX_GEOM_COLOR_STR = 32
_MAX_FLOW_NODES = 32
_MAX_FLOW_EDGES = 64
_MAX_FLOW_TEXT = 120

_MAX_TABLE_ROWS = 28
_MAX_TABLE_COLS = 12
_MAX_TABLE_CELL = 120
_MAX_TIMELINE_ITEMS = 24
_MAX_NL_MARKS = 32
_MAX_NL_INTERVALS = 32
_MAX_HIST_BINS = 40
_MAX_COMPOSITE_PANELS = 6
_MAX_FORCE_ITEMS = 12
_MAX_CIRCUIT_NODES = 24
_MAX_CIRCUIT_EDGES = 32
_MAX_FORCE_LABEL = 48
_MAX_FORCE_LABEL_MATH = 96
_MAX_SVG_BYTES = 100_000
_MAX_GEOM_LABEL_PLAIN = 48
_MAX_GEOM_LABEL_MATH = 120
_MAX_FLOW_TEXT_MATH = 120

_MAX_SOLID_VERTS = 48
_MAX_SOLID_EDGES = 120
_MAX_SOLID_FACES = 16
_MAX_SOLID_AUX_EDGES = 48
_MAX_DIGRAPH_NODES = 32
_MAX_DIGRAPH_EDGES = 64
_MAX_FIELD_LINES = 32
_MAX_FIELD_LINE_POINTS = 48
_MAX_FIELD_PRESETS = 8
_MAX_PROB_TREE_NODES = 28
_MAX_PED_INDIVIDUALS = 24
_MAX_PED_MARRIAGES = 12
_MAX_PED_DESCENTS = 24
_MAX_ENERGY_PROFILE_POINTS = 36

logger = logging.getLogger(__name__)


def _clamp_solid_wireframe_spec_inner(spec: PracticeSolidWireframeSpec) -> PracticeSolidWireframeSpec | None:
    verts: list[PracticeSolidVertex3D] = []
    seen_v: set[str] = set()
    for v in spec.vertices[:_MAX_SOLID_VERTS]:
        vid = (v.id or "").strip()[:32]
        if not vid or vid in seen_v:
            continue
        if not (
            math.isfinite(float(v.x))
            and math.isfinite(float(v.y))
            and math.isfinite(float(v.z))
        ):
            continue
        seen_v.add(vid)
        verts.append(
            PracticeSolidVertex3D(id=vid, x=float(v.x), y=float(v.y), z=float(v.z))
        )
    if len(verts) < 2:
        return None
    id_set = {v.id for v in verts}
    edges: list[PracticeSolidEdge] = []
    for e in spec.edges[:_MAX_SOLID_EDGES]:
        a = (e.a or "").strip()[:32]
        b = (e.b or "").strip()[:32]
        if a and b and a in id_set and b in id_set and a != b:
            edges.append(PracticeSolidEdge(a=a, b=b))
    if not edges:
        return None
    faces: list[PracticeSolidFace] = []
    for f in spec.faces[:_MAX_SOLID_FACES]:
        vids = [(x or "").strip()[:32] for x in f.vertex_ids[:24]]
        vids = [x for x in vids if x in id_set]
        if len(vids) < 3:
            continue
        faces.append(
            PracticeSolidFace(
                vertex_ids=vids,
                alpha=float(f.alpha),
                fill_color=(f.fill_color or "")[:_MAX_GEOM_COLOR_STR],
                edge_color=(f.edge_color or "")[:_MAX_GEOM_COLOR_STR],
            )
        )

    def _clamp_face_list(src: list[PracticeSolidFace]) -> list[PracticeSolidFace]:
        out_f: list[PracticeSolidFace] = []
        for f in src[:_MAX_SOLID_FACES]:
            vids = [(x or "").strip()[:32] for x in f.vertex_ids[:24]]
            vids = [x for x in vids if x in id_set]
            if len(vids) < 3:
                continue
            out_f.append(
                PracticeSolidFace(
                    vertex_ids=vids,
                    alpha=float(f.alpha),
                    fill_color=(f.fill_color or "")[:_MAX_GEOM_COLOR_STR],
                    edge_color=(f.edge_color or "")[:_MAX_GEOM_COLOR_STR],
                )
            )
        return out_f

    section_faces = _clamp_face_list(list(spec.section_faces))
    aux_edges: list[PracticeSolidAuxiliaryEdge] = []
    for ae in spec.auxiliary_edges[:_MAX_SOLID_AUX_EDGES]:
        a = (ae.a or "").strip()[:32]
        b = (ae.b or "").strip()[:32]
        if not a or not b or a not in id_set or b not in id_set or a == b:
            continue
        st = ae.style if ae.style in ("solid", "dashed") else "dashed"
        aux_edges.append(
            PracticeSolidAuxiliaryEdge(
                a=a,
                b=b,
                style=st,
                label=(ae.label or "")[:_MAX_GEOM_LABEL_PLAIN],
            )
        )
    labs: list[PracticeGeometryLabel] = []
    for lb in spec.labels[:_MAX_GEOM_LABELS]:
        mx = _MAX_GEOM_LABEL_MATH if lb.use_mathtext else _MAX_GEOM_LABEL_PLAIN
        labs.append(
            PracticeGeometryLabel(
                text=(lb.text or "")[:mx],
                x=float(lb.x),
                y=float(lb.y),
                use_mathtext=bool(lb.use_mathtext),
            )
        )
    proj = spec.projection if spec.projection in ("isometric", "cabinet") else "isometric"
    return PracticeSolidWireframeSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        projection=proj,
        vertices=verts,
        edges=edges,
        faces=faces,
        section_faces=section_faces,
        auxiliary_edges=aux_edges,
        labels=labs,
    )


def _clamp_field_lines_spec_inner(spec: PracticeFieldLinesSpec) -> PracticeFieldLinesSpec | None:
    lines: list[PracticeFieldLine] = []
    for ln in spec.lines[:_MAX_FIELD_LINES]:
        if len(ln.x) != len(ln.y) or len(ln.x) < 2:
            continue
        n = min(len(ln.x), _MAX_FIELD_LINE_POINTS)
        try:
            xf = [float(ln.x[i]) for i in range(n)]
            yf = [float(ln.y[i]) for i in range(n)]
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(t) for t in xf + yf):
            continue
        ar = ln.arrow if ln.arrow in ("end", "start", "none") else "end"
        lines.append(
            PracticeFieldLine(
                x=xf,
                y=yf,
                color=(ln.color or "")[:_MAX_GEOM_COLOR_STR],
                arrow=ar,
            )
        )

    presets_out: list = []
    for pr in spec.presets[:_MAX_FIELD_PRESETS]:
        if isinstance(pr, PracticeFieldPresetPointCharge):
            if not (
                math.isfinite(float(pr.cx))
                and math.isfinite(float(pr.cy))
                and math.isfinite(float(pr.r_max))
                and math.isfinite(float(pr.r_min))
            ):
                continue
            r_max = max(0.05, min(12.0, float(pr.r_max)))
            r_min = max(0.02, min(2.0, float(pr.r_min)))
            if r_min >= r_max:
                continue
            sg = 1 if int(pr.sign) == 1 else -1
            nl = max(3, min(48, int(pr.n_lines)))
            presets_out.append(
                PracticeFieldPresetPointCharge(
                    cx=float(pr.cx),
                    cy=float(pr.cy),
                    sign=sg,
                    n_lines=nl,
                    r_max=r_max,
                    r_min=r_min,
                    color=(pr.color or "")[:_MAX_GEOM_COLOR_STR],
                )
            )
        elif isinstance(pr, PracticeFieldPresetSolenoid):
            if not all(
                math.isfinite(float(pr.x0)),
                math.isfinite(float(pr.y0)),
                math.isfinite(float(pr.w)),
                math.isfinite(float(pr.h)),
            ):
                continue
            w = max(0.05, min(12.0, float(pr.w)))
            h = max(0.05, min(12.0, float(pr.h)))
            bd = pr.b_direction if pr.b_direction in ("up", "down", "left", "right") else "right"
            presets_out.append(
                PracticeFieldPresetSolenoid(
                    x0=float(pr.x0),
                    y0=float(pr.y0),
                    w=w,
                    h=h,
                    b_direction=bd,
                    nx=max(1, min(12, int(pr.nx))),
                    ny=max(1, min(12, int(pr.ny))),
                    draw_frame=bool(pr.draw_frame),
                    color=(pr.color or "")[:_MAX_GEOM_COLOR_STR],
                )
            )
        elif isinstance(pr, PracticeFieldPresetLongStraightWire):
            if not all(
                math.isfinite(float(pr.cx)),
                math.isfinite(float(pr.cy)),
                math.isfinite(float(pr.r_max)),
            ):
                continue
            r_max = max(0.05, min(12.0, float(pr.r_max)))
            af = max(0.5, min(1.0, float(pr.arc_fraction)))
            presets_out.append(
                PracticeFieldPresetLongStraightWire(
                    cx=float(pr.cx),
                    cy=float(pr.cy),
                    n_circles=max(2, min(20, int(pr.n_circles))),
                    r_max=r_max,
                    current_out_of_page=bool(pr.current_out_of_page),
                    arc_fraction=af,
                    color=(pr.color or "")[:_MAX_GEOM_COLOR_STR],
                )
            )

    uf: PracticeUniformField | None = None
    if spec.uniform_field is not None:
        u = spec.uniform_field
        if math.isfinite(float(u.dx)) and math.isfinite(float(u.dy)):
            uf = PracticeUniformField(
                dx=float(u.dx),
                dy=float(u.dy),
                label=(u.label or "")[:40],
            )

    if not lines and not presets_out and uf is None:
        return None
    return PracticeFieldLinesSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        lines=lines,
        presets=presets_out,
        uniform_field=uf,
    )


def _clamp_probability_tree_spec_inner(spec: PracticeProbabilityTreeSpec) -> PracticeProbabilityTreeSpec | None:
    nodes: list[PracticeProbabilityTreeNode] = []
    for n in spec.nodes[:_MAX_PROB_TREE_NODES]:
        nid = (n.id or "").strip()[:32]
        if not nid:
            continue
        nodes.append(
            PracticeProbabilityTreeNode(
                id=nid,
                text=(n.text or "")[:_MAX_FLOW_TEXT],
                parent_id=(n.parent_id or "").strip()[:32],
                edge_label=(n.edge_label or "")[:48],
                leaf_note=(n.leaf_note or "")[:72],
            )
        )
    if not nodes:
        return None
    id_set = {n.id for n in nodes}
    roots = [n for n in nodes if not n.parent_id or n.parent_id not in id_set]
    if len(roots) != 1:
        return None
    for n in nodes:
        if n.parent_id and n.parent_id not in id_set:
            return None
    for n in nodes:
        seen: set[str] = set()
        cur: str | None = n.id
        for _ in range(len(nodes) + 2):
            if not cur:
                break
            node = next((x for x in nodes if x.id == cur), None)
            if node is None:
                return None
            if not node.parent_id:
                break
            if node.parent_id in seen:
                return None
            seen.add(cur)
            cur = node.parent_id
    return PracticeProbabilityTreeSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        nodes=nodes,
    )


def _clamp_pedigree_spec_inner(spec: PracticePedigreeSpec) -> PracticePedigreeSpec | None:
    inds: list[PracticePedigreeIndividual] = []
    seen: set[str] = set()
    for p in spec.individuals[:_MAX_PED_INDIVIDUALS]:
        pid = (p.id or "").strip()[:32]
        if not pid or pid in seen:
            continue
        seen.add(pid)
        sx = p.sex if p.sex in ("male", "female", "unknown") else "unknown"
        inds.append(
            PracticePedigreeIndividual(
                id=pid,
                generation=int(p.generation),
                sex=sx,
                affected=bool(p.affected),
                carrier=bool(p.carrier),
                x_hint=p.x_hint,
            )
        )
    if not inds:
        return None
    id_set = {i.id for i in inds}
    marriages: list[PracticePedigreeMarriage] = []
    for m in spec.marriages[:_MAX_PED_MARRIAGES]:
        a = (m.left or "").strip()[:32]
        b = (m.right or "").strip()[:32]
        if a in id_set and b in id_set and a != b:
            marriages.append(PracticePedigreeMarriage(left=a, right=b))
    descents: list[PracticePedigreeDescent] = []
    for d in spec.descents[:_MAX_PED_DESCENTS]:
        mo = (d.mother or "").strip()[:32]
        fa = (d.father or "").strip()[:32]
        ch = (d.child or "").strip()[:32]
        if mo in id_set and fa in id_set and ch in id_set and mo != fa:
            descents.append(PracticePedigreeDescent(mother=mo, father=fa, child=ch))
    return PracticePedigreeSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        individuals=inds,
        marriages=marriages,
        descents=descents,
    )


def _clamp_energy_profile_spec_inner(spec: PracticeEnergyProfileSpec) -> PracticeEnergyProfileSpec | None:
    n = min(len(spec.x), len(spec.y), _MAX_ENERGY_PROFILE_POINTS)
    if n < 2:
        return None
    try:
        xf = [float(spec.x[i]) for i in range(n)]
        yf = [float(spec.y[i]) for i in range(n)]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(t) for t in xf + yf):
        return None
    bi = spec.barrier_i
    bj = spec.barrier_j
    if bi is not None and (bi < 0 or bi >= n):
        bi = None
    if bj is not None and (bj < 0 or bj >= n):
        bj = None
    return PracticeEnergyProfileSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
        y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
        x=xf,
        y=yf,
        barrier_i=bi,
        barrier_j=bj,
        barrier_label=(spec.barrier_label or "")[:48],
    )


def _clamp_electrochemical_cell_spec_inner(spec: PracticeElectrochemicalCellSpec) -> PracticeElectrochemicalCellSpec:
    md = spec.mode if spec.mode in ("galvanic", "electrolytic") else "galvanic"
    ct = spec.cation_to if spec.cation_to in ("left", "right", "none") else "right"
    at = spec.anion_to if spec.anion_to in ("left", "right", "none") else "left"
    return PracticeElectrochemicalCellSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        left_label=(spec.left_label or "")[:40],
        right_label=(spec.right_label or "")[:40],
        electrolyte_label=(spec.electrolyte_label or "")[:40],
        mode=md,
        electron_cw=bool(spec.electron_cw),
        cation_to=ct,
        anion_to=at,
    )


def _clamp_unit_circle_trig_spec_inner(spec: PracticeUnitCircleTrigSpec) -> PracticeUnitCircleTrigSpec:
    try:
        ang = float(spec.angle_deg)
    except (TypeError, ValueError):
        ang = 45.0
    if not math.isfinite(ang):
        ang = 45.0
    return PracticeUnitCircleTrigSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        angle_deg=ang,
        show_sin=bool(spec.show_sin),
        show_cos=bool(spec.show_cos),
        show_tan=bool(spec.show_tan),
        angle_label=(spec.angle_label or "")[:32],
    )


def _clamp_optics_ray_spec_inner(spec: PracticeOpticsRaySpec) -> PracticeOpticsRaySpec | None:
    rays: list[PracticeOpticsRaySegment] = []
    for r in spec.rays[:20]:
        if not (
            math.isfinite(float(r.x0))
            and math.isfinite(float(r.y0))
            and math.isfinite(float(r.x1))
            and math.isfinite(float(r.y1))
        ):
            continue
        st = r.style if r.style in ("solid", "dashed") else "solid"
        rays.append(
            PracticeOpticsRaySegment(
                x0=float(r.x0),
                y0=float(r.y0),
                x1=float(r.x1),
                y1=float(r.y1),
                label=(r.label or "")[:40],
                color=(r.color or "")[:_MAX_GEOM_COLOR_STR],
                style=st,
            )
        )
    if not rays:
        return None
    try:
        iy = float(spec.interface_y)
    except (TypeError, ValueError):
        iy = 0.0
    if not math.isfinite(iy):
        iy = 0.0
    try:
        ix = float(spec.interface_x)
    except (TypeError, ValueError):
        ix = 0.0
    if not math.isfinite(ix):
        ix = 0.0
    try:
        ipx = float(spec.interface_pivot_x)
        ipy = float(spec.interface_pivot_y)
        iang = float(spec.interface_angle_deg)
    except (TypeError, ValueError):
        ipx = ipy = iang = 0.0
    if not math.isfinite(ipx):
        ipx = 0.0
    if not math.isfinite(ipy):
        ipy = 0.0
    if not math.isfinite(iang):
        iang = 0.0
    ori = spec.interface_orientation if spec.interface_orientation in ("horizontal", "vertical", "angled") else "horizontal"
    pa: PracticeOpticsPrincipalAxis | None = None
    if spec.principal_axis is not None:
        p = spec.principal_axis
        if (
            math.isfinite(float(p.x0))
            and math.isfinite(float(p.y0))
            and math.isfinite(float(p.x1))
            and math.isfinite(float(p.y1))
        ):
            pa = PracticeOpticsPrincipalAxis(
                x0=float(p.x0),
                y0=float(p.y0),
                x1=float(p.x1),
                y1=float(p.y1),
            )
    tl: PracticeOpticsThinLens | None = None
    if spec.thin_lens is not None:
        t = spec.thin_lens
        try:
            d = float(t.diameter)
        except (TypeError, ValueError):
            d = 1.2
        if math.isfinite(d) and d > 0:
            d = min(10.0, d)
            if math.isfinite(float(t.center_x)) and math.isfinite(float(t.center_y)):
                tl = PracticeOpticsThinLens(
                    center_x=float(t.center_x),
                    center_y=float(t.center_y),
                    diameter=d,
                    convex_toward_right=bool(t.convex_toward_right),
                )
    return PracticeOpticsRaySpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        interface_orientation=ori,
        interface_y=iy,
        interface_x=ix,
        interface_pivot_x=ipx,
        interface_pivot_y=ipy,
        interface_angle_deg=iang,
        medium_top_label=(spec.medium_top_label or "")[:24],
        medium_bottom_label=(spec.medium_bottom_label or "")[:24],
        show_normal=bool(spec.show_normal),
        principal_axis=pa,
        thin_lens=tl,
        rays=rays,
    )


def _clamp_directed_graph_spec_inner(spec: PracticeDirectedGraphSpec) -> PracticeDirectedGraphSpec | None:
    nodes: list[PracticeDirectedGraphNode] = []
    seen: set[str] = set()
    for n in spec.nodes[:_MAX_DIGRAPH_NODES]:
        nid = (n.id or "").strip()[:32]
        if not nid or nid in seen:
            continue
        seen.add(nid)
        try:
            layer = int(n.layer)
        except (TypeError, ValueError):
            layer = 0
        layer = max(0, min(40, layer))
        nodes.append(
            PracticeDirectedGraphNode(
                id=nid,
                text=(n.text or "")[:_MAX_FLOW_TEXT],
                layer=layer,
                use_mathtext=bool(n.use_mathtext),
            )
        )
    if not nodes:
        return None
    id_set = {n.id for n in nodes}
    edges: list[PracticeDirectedGraphEdge] = []
    for e in spec.edges[:_MAX_DIGRAPH_EDGES]:
        s = (e.source or "").strip()[:32]
        t = (e.target or "").strip()[:32]
        if s in id_set and t in id_set:
            edges.append(
                PracticeDirectedGraphEdge(
                    source=s,
                    target=t,
                    label=(e.label or "")[:_MAX_FLOW_TEXT],
                )
            )
    lay = spec.layout if spec.layout in ("layered", "circular") else "layered"
    return PracticeDirectedGraphSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        layout=lay,
        nodes=nodes,
        edges=edges,
    )


def _point_id_set(pts: list) -> set[str]:
    return {(p.id or "").strip() for p in pts if (p.id or "").strip()}


def _clamp_geometry_spec_inner(spec, pts, segs, labs) -> PracticeGeometrySpec | None:
    """从已截断的 points/segments/labels 构造消毒后的 PracticeGeometrySpec；无效则 None。"""
    point_ids = _point_id_set(pts)

    circles: list[PracticeGeometryCircle] = []
    for c in spec.circles[:_MAX_GEOM_CIRCLES]:
        cid = (c.center_id or "").strip()
        ok_center = (cid and cid in point_ids) or (
            c.cx is not None and c.cy is not None and math.isfinite(float(c.cx)) and math.isfinite(float(c.cy))
        )
        if not ok_center:
            continue
        try:
            r = float(c.r)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(r) or r <= 0:
            continue
        circles.append(
            PracticeGeometryCircle(
                center_id=cid,
                cx=c.cx,
                cy=c.cy,
                r=min(r, 1e6),
                fill=bool(c.fill),
                fill_color=(c.fill_color or "")[:_MAX_GEOM_COLOR_STR],
                edge_color=(c.edge_color or "")[:_MAX_GEOM_COLOR_STR],
            )
        )

    polygons: list[PracticeGeometryPolygon] = []
    for poly in spec.polygons[:_MAX_GEOM_POLYGONS]:
        vids = [(v or "").strip() for v in poly.vertex_ids[:_MAX_GEOM_POLY_VERTS]]
        vids = [v for v in vids if v]
        if len(vids) < 3 or not all(v in point_ids for v in vids):
            continue
        polygons.append(
            PracticeGeometryPolygon(
                vertex_ids=vids,
                fill=bool(poly.fill),
                alpha=float(poly.alpha),
                edge_color=(poly.edge_color or "")[:_MAX_GEOM_COLOR_STR],
                fill_color=(poly.fill_color or "")[:_MAX_GEOM_COLOR_STR],
            )
        )

    arcs: list[PracticeGeometryArc] = []
    for a in spec.arcs[:_MAX_GEOM_ARCS]:
        cid = (a.center_id or "").strip()
        ok_center = (cid and cid in point_ids) or (
            a.cx is not None and a.cy is not None and math.isfinite(float(a.cx)) and math.isfinite(float(a.cy))
        )
        if not ok_center:
            continue
        try:
            r = float(a.r)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(r) or r <= 0:
            continue
        arcs.append(
            PracticeGeometryArc(
                center_id=cid,
                cx=a.cx,
                cy=a.cy,
                r=min(r, 1e6),
                theta1_deg=float(a.theta1_deg),
                theta2_deg=float(a.theta2_deg),
                fill=bool(a.fill),
                fill_color=(a.fill_color or "")[:_MAX_GEOM_COLOR_STR],
                edge_color=(a.edge_color or "")[:_MAX_GEOM_COLOR_STR],
            )
        )

    has_seg = any((s.a or "").strip() in point_ids and (s.b or "").strip() in point_ids for s in segs)
    has_extra = bool(circles or polygons or arcs)

    new_labs: list[PracticeGeometryLabel] = []
    for lb in labs:
        mx = _MAX_GEOM_LABEL_MATH if lb.use_mathtext else _MAX_GEOM_LABEL_PLAIN
        try:
            new_labs.append(
                PracticeGeometryLabel(
                    text=(lb.text or "")[:mx],
                    x=float(lb.x),
                    y=float(lb.y),
                    use_mathtext=bool(lb.use_mathtext),
                )
            )
        except (TypeError, ValueError):
            continue

    has_lbl = any((lb.text or "").strip() for lb in new_labs)
    if not pts and not has_lbl and not has_seg and not has_extra:
        return None

    return PracticeGeometrySpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        points=list(pts),
        segments=list(segs),
        labels=new_labs,
        circles=circles,
        polygons=polygons,
        arcs=arcs,
    )


def _stem_suggests_smooth_function_graph(stem: str) -> bool:
    s = stem or ""
    return any(k in s for k in _SMOOTH_CURVE_STEM_KEYS)


def _clamp_one_plot_series(s: PracticePlotSeries) -> PracticePlotSeries | None:
    n = min(len(s.x), len(s.y), _MAX_FIG_POINTS)
    if n < 2:
        return None
    da = s.draw_as if s.draw_as in ("line", "scatter") else "line"
    y_err = None
    if s.y_err is not None and len(s.y_err) >= n:
        y_err = [float(s.y_err[i]) for i in range(n)]
    return PracticePlotSeries(
        label=(s.label or "")[:_MAX_FIG_SERIES_LABEL],
        x=list(s.x[:n]),
        y=list(s.y[:n]),
        draw_as=da,
        y_err=y_err,
    )


def _clamp_plot_spec_model(spec: PracticePlotSpec, stem: str) -> PracticePlotSpec | None:
    new_series: list[PracticePlotSeries] = []
    for s in spec.series[:_MAX_FIG_SERIES]:
        cs = _clamp_one_plot_series(s)
        if cs is not None:
            new_series.append(cs)
    if not new_series:
        return None
    min_pts = min(len(s.x) for s in new_series)
    if _stem_suggests_smooth_function_graph(stem) and min_pts < _MIN_PLOT_POINTS_FOR_SMOOTH_CONTEXT:
        return None
    new_right: list[PracticePlotSeries] = []
    for s in spec.series_right[:_MAX_FIG_SERIES]:
        cs = _clamp_one_plot_series(s)
        if cs is not None:
            new_right.append(cs)
    new_fills: list[PracticePlotFillBetween] = []
    for fb in spec.fill_between[:5]:
        n = min(len(fb.x), len(fb.y_lower), len(fb.y_upper), _MAX_FIG_POINTS)
        if n < 2:
            continue
        new_fills.append(
            PracticePlotFillBetween(
                x=list(fb.x[:n]),
                y_lower=list(fb.y_lower[:n]),
                y_upper=list(fb.y_upper[:n]),
                alpha=float(fb.alpha),
                color=(fb.color or "")[:32],
                label=(fb.label or "")[:_MAX_FIG_SERIES_LABEL],
            )
        )
    use_log = bool(spec.log_y) and not new_right
    return PracticePlotSpec(
        title=(spec.title or "")[:_MAX_FIG_TITLE],
        x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
        y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
        y_label_right=(spec.y_label_right or "")[:_MAX_FIG_AXIS_LABEL],
        caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
        series=new_series,
        series_right=new_right,
        log_y=use_log,
        show_legend=bool(spec.show_legend),
        fill_between=new_fills,
    )


def _clamp_composite_panel(
    panel: PracticeCompositePanel,
    *,
    stem: str,
) -> PracticeCompositePanel | None:
    if isinstance(panel, PracticeCompositePanelPlot):
        clamped = _clamp_plot_spec_model(panel.spec, stem)
        if clamped is None:
            return None
        return PracticeCompositePanelPlot(
            subtitle=(panel.subtitle or "")[:80],
            spec=clamped,
        )
    if isinstance(panel, PracticeCompositePanelBar):
        spec = panel.spec
        if len(spec.categories) > _MAX_BAR_ITEMS or len(spec.values) != len(spec.categories):
            return None
        cats = [(c or "")[:_MAX_BAR_CAT_LEN] for c in spec.categories]
        if not any(cats):
            return None
        return PracticeCompositePanelBar(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeBarSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
                y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                categories=cats,
                values=list(spec.values),
            ),
        )
    if isinstance(panel, PracticeCompositePanelGroupedBar):
        spec = panel.spec
        if len(spec.categories) > _MAX_BAR_ITEMS or len(spec.series) > _MAX_FIG_SERIES:
            return None
        cats = [(c or "")[:_MAX_BAR_CAT_LEN] for c in spec.categories]
        if not any(cats):
            return None
        n = len(cats)
        new_series: list[PracticeGroupedBarSeries] = []
        for gs in spec.series[:_MAX_FIG_SERIES]:
            if len(gs.values) != n:
                return None
            new_series.append(
                PracticeGroupedBarSeries(
                    label=(gs.label or "")[:_MAX_FIG_SERIES_LABEL],
                    values=list(gs.values),
                )
            )
        if not new_series:
            return None
        return PracticeCompositePanelGroupedBar(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeGroupedBarSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
                y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                categories=cats,
                series=new_series,
                show_legend=bool(spec.show_legend),
            ),
        )
    if isinstance(panel, PracticeCompositePanelPie):
        spec = panel.spec
        if len(spec.labels) > _MAX_PIE_SLICES or len(spec.values) != len(spec.labels):
            return None
        labs = [(lb or "")[:_MAX_PIE_LABEL_LEN] for lb in spec.labels]
        return PracticeCompositePanelPie(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticePieSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                labels=labs,
                values=list(spec.values),
            ),
        )
    if isinstance(panel, PracticeCompositePanelGeometry):
        spec = panel.spec
        pts = spec.points[:_MAX_GEOM_POINTS]
        segs = spec.segments[:_MAX_GEOM_SEGMENTS]
        labs = spec.labels[:_MAX_GEOM_LABELS]
        geom = _clamp_geometry_spec_inner(spec, pts, segs, labs)
        if geom is None:
            return None
        return PracticeCompositePanelGeometry(
            subtitle=(panel.subtitle or "")[:80],
            spec=geom,
        )
    if isinstance(panel, PracticeCompositePanelFlowchart):
        spec = panel.spec
        nodes: list[PracticeFlowchartNode] = []
        for n in spec.nodes[:_MAX_FLOW_NODES]:
            mx = _MAX_FLOW_TEXT_MATH if n.use_mathtext else _MAX_FLOW_TEXT
            nodes.append(
                PracticeFlowchartNode(
                    id=(n.id or "")[:32],
                    text=(n.text or "")[:mx],
                    use_mathtext=bool(n.use_mathtext),
                )
            )
        edges: list[PracticeFlowchartEdge] = []
        for e in spec.edges[:_MAX_FLOW_EDGES]:
            edges.append(
                PracticeFlowchartEdge(
                    source=(e.source or "")[:32],
                    target=(e.target or "")[:32],
                )
            )
        if not nodes:
            return None
        lay = spec.layout if spec.layout in ("circular", "layered") else "circular"
        return PracticeCompositePanelFlowchart(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeFlowchartSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                layout=lay,
                nodes=nodes,
                edges=edges,
            ),
        )
    if isinstance(panel, PracticeCompositePanelTable):
        spec = panel.spec
        rows = spec.rows[:_MAX_TABLE_ROWS]
        if not rows:
            return None
        ncol = min(max(len(r) for r in rows), _MAX_TABLE_COLS)
        pad_rows: list[list[str]] = []
        for r in rows:
            cells = [(c or "")[:_MAX_TABLE_CELL] for c in r[:ncol]]
            while len(cells) < ncol:
                cells.append("")
            pad_rows.append(cells[:ncol])
        hdr: list[str] = []
        if spec.headers:
            hdr = [(h or "")[:_MAX_TABLE_CELL] for h in spec.headers[:ncol]]
            while len(hdr) < ncol:
                hdr.append("")
            hdr = hdr[:ncol]
        return PracticeCompositePanelTable(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeTableSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                headers=hdr,
                rows=pad_rows,
            ),
        )
    if isinstance(panel, PracticeCompositePanelTimeline):
        spec = panel.spec
        items = list(spec.items[:_MAX_TIMELINE_ITEMS])
        if not items:
            return None
        return PracticeCompositePanelTimeline(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeTimelineSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                t_min=spec.t_min,
                t_max=spec.t_max,
                items=items,
                connect=bool(spec.connect),
            ),
        )
    if isinstance(panel, PracticeCompositePanelNumberLine):
        spec = panel.spec
        marks = [
            PracticeNumberLineMark(x=m.x, label=(m.label or "")[:40])
            for m in spec.marks[:_MAX_NL_MARKS]
        ]
        intervals: list[PracticeNumberLineInterval] = []
        for iv in spec.intervals[:_MAX_NL_INTERVALS]:
            intervals.append(
                PracticeNumberLineInterval(
                    a=iv.a,
                    b=iv.b,
                    open_left=bool(iv.open_left),
                    open_right=bool(iv.open_right),
                )
            )
        return PracticeCompositePanelNumberLine(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeNumberLineSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                x_min=spec.x_min,
                x_max=spec.x_max,
                marks=marks,
                intervals=intervals,
            ),
        )
    if isinstance(panel, PracticeCompositePanelVenn):
        spec = panel.spec
        return PracticeCompositePanelVenn(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeVennSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                n_sets=spec.n_sets,
                label_a=(spec.label_a or "")[:20],
                label_b=(spec.label_b or "")[:20],
                label_c=(spec.label_c or "")[:20],
                only_a=(spec.only_a or "")[:120],
                only_b=(spec.only_b or "")[:120],
                only_c=(spec.only_c or "")[:120],
                ab=(spec.ab or "")[:120],
                ac=(spec.ac or "")[:120],
                bc=(spec.bc or "")[:120],
                abc=(spec.abc or "")[:120],
            ),
        )
    if isinstance(panel, PracticeCompositePanelHistogram):
        spec = panel.spec
        if len(spec.edges) > _MAX_HIST_BINS + 1:
            return None
        if len(spec.counts) != len(spec.edges) - 1:
            return None
        return PracticeCompositePanelHistogram(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeHistogramSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
                y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
                edges=list(spec.edges),
                counts=list(spec.counts),
            ),
        )
    if isinstance(panel, PracticeCompositePanelForceDiagram):
        spec = panel.spec
        forces: list[PracticeForceItem] = []
        for f in spec.forces[:_MAX_FORCE_ITEMS]:
            mx = _MAX_FORCE_LABEL_MATH if f.use_mathtext else _MAX_FORCE_LABEL
            forces.append(
                PracticeForceItem(
                    x0=float(f.x0),
                    y0=float(f.y0),
                    x1=float(f.x1),
                    y1=float(f.y1),
                    label=(f.label or "")[:mx],
                    use_mathtext=bool(f.use_mathtext),
                    color=(f.color or "")[:_MAX_GEOM_COLOR_STR],
                    zorder=int(f.zorder),
                )
            )
        if not forces:
            return None
        return PracticeCompositePanelForceDiagram(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeForceDiagramSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                forces=forces,
                object_dot=bool(spec.object_dot),
                object_x=float(spec.object_x),
                object_y=float(spec.object_y),
            ),
        )
    if isinstance(panel, PracticeCompositePanelCircuit):
        spec = panel.spec
        nodes: list[PracticeCircuitNode] = []
        seen: set[str] = set()
        for n in spec.nodes[:_MAX_CIRCUIT_NODES]:
            nid = (n.id or "").strip()
            if not nid or nid in seen:
                continue
            seen.add(nid)
            nodes.append(
                PracticeCircuitNode(id=nid[:32], x=float(n.x), y=float(n.y))
            )
        id_set = {n.id for n in nodes}
        edges: list[PracticeCircuitEdge] = []
        for e in spec.edges[:_MAX_CIRCUIT_EDGES]:
            s = (e.source or "").strip()
            t = (e.target or "").strip()
            if s not in id_set or t not in id_set:
                continue
            vias = [
                PracticeCircuitVia(x=float(v.x), y=float(v.y))
                for v in e.via[:8]
                if math.isfinite(float(v.x)) and math.isfinite(float(v.y))
            ]
            el = e.element if e.element in (
                "wire",
                "resistor",
                "cell",
                "lamp",
                "switch",
                "ammeter",
                "voltmeter",
                "generic",
            ) else "wire"
            edges.append(
                PracticeCircuitEdge(source=s[:32], target=t[:32], element=el, via=vias)
            )
        if len(nodes) < 2 or not edges:
            return None
        return PracticeCompositePanelCircuit(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeCircuitSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                nodes=nodes,
                edges=edges,
            ),
        )
    if isinstance(panel, PracticeCompositePanelSvg):
        spec = panel.spec
        clean = sanitize_practice_svg(spec.svg, max_bytes=_MAX_SVG_BYTES)
        if clean is None:
            return None
        return PracticeCompositePanelSvg(
            subtitle=(panel.subtitle or "")[:80],
            spec=PracticeSvgSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                svg=clean,
            ),
        )
    if isinstance(panel, PracticeCompositePanelSolidWireframe):
        cw = _clamp_solid_wireframe_spec_inner(panel.spec)
        if cw is None:
            return None
        return PracticeCompositePanelSolidWireframe(
            subtitle=(panel.subtitle or "")[:80],
            spec=cw,
        )
    if isinstance(panel, PracticeCompositePanelFieldLines):
        cf = _clamp_field_lines_spec_inner(panel.spec)
        if cf is None:
            return None
        return PracticeCompositePanelFieldLines(
            subtitle=(panel.subtitle or "")[:80],
            spec=cf,
        )
    if isinstance(panel, PracticeCompositePanelProbabilityTree):
        cp = _clamp_probability_tree_spec_inner(panel.spec)
        if cp is None:
            return None
        return PracticeCompositePanelProbabilityTree(
            subtitle=(panel.subtitle or "")[:80],
            spec=cp,
        )
    if isinstance(panel, PracticeCompositePanelPedigree):
        pp = _clamp_pedigree_spec_inner(panel.spec)
        if pp is None:
            return None
        return PracticeCompositePanelPedigree(
            subtitle=(panel.subtitle or "")[:80],
            spec=pp,
        )
    if isinstance(panel, PracticeCompositePanelEnergyProfile):
        ep = _clamp_energy_profile_spec_inner(panel.spec)
        if ep is None:
            return None
        return PracticeCompositePanelEnergyProfile(
            subtitle=(panel.subtitle or "")[:80],
            spec=ep,
        )
    if isinstance(panel, PracticeCompositePanelElectrochemicalCell):
        return PracticeCompositePanelElectrochemicalCell(
            subtitle=(panel.subtitle or "")[:80],
            spec=_clamp_electrochemical_cell_spec_inner(panel.spec),
        )
    if isinstance(panel, PracticeCompositePanelUnitCircleTrig):
        return PracticeCompositePanelUnitCircleTrig(
            subtitle=(panel.subtitle or "")[:80],
            spec=_clamp_unit_circle_trig_spec_inner(panel.spec),
        )
    if isinstance(panel, PracticeCompositePanelOpticsRay):
        op = _clamp_optics_ray_spec_inner(panel.spec)
        if op is None:
            return None
        return PracticeCompositePanelOpticsRay(
            subtitle=(panel.subtitle or "")[:80],
            spec=op,
        )
    if isinstance(panel, PracticeCompositePanelDirectedGraph):
        dg = _clamp_directed_graph_spec_inner(panel.spec)
        if dg is None:
            return None
        return PracticeCompositePanelDirectedGraph(
            subtitle=(panel.subtitle or "")[:80],
            spec=dg,
        )
    return None


def _sanitize_practice_figures(ps: PracticeSet) -> None:
    for q in ps.questions:
        if q.figure_kind == "plot" and q.figure_spec is not None:
            spec = q.figure_spec
            clamped = _clamp_plot_spec_model(spec, q.stem)
            if clamped is None:
                logger.info(
                    "practice_clamp: dropped plot (sanitize or smooth-curve rule, order_index=%s)",
                    q.order_index,
                )
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = clamped
            continue

        if q.figure_kind == "bar" and q.figure_spec is not None:
            spec = q.figure_spec
            if len(spec.categories) > _MAX_BAR_ITEMS or len(spec.values) != len(spec.categories):
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            cats = [(c or "")[:_MAX_BAR_CAT_LEN] for c in spec.categories]
            if not any(cats):
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeBarSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
                y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                categories=cats,
                values=list(spec.values),
            )
            continue

        if q.figure_kind == "grouped_bar" and q.figure_spec is not None:
            spec = q.figure_spec
            if (
                len(spec.categories) > _MAX_BAR_ITEMS
                or len(spec.series) > _MAX_FIG_SERIES
            ):
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            cats = [(c or "")[:_MAX_BAR_CAT_LEN] for c in spec.categories]
            if not any(cats):
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            n = len(cats)
            new_series: list[PracticeGroupedBarSeries] = []
            for s in spec.series[:_MAX_FIG_SERIES]:
                if len(s.values) != n:
                    q.figure_kind = "none"
                    q.figure_spec = None
                    new_series = []
                    break
                new_series.append(
                    PracticeGroupedBarSeries(
                        label=(s.label or "")[:_MAX_FIG_SERIES_LABEL],
                        values=list(s.values),
                    )
                )
            if not new_series:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeGroupedBarSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
                y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                categories=cats,
                series=new_series,
                show_legend=bool(spec.show_legend),
            )
            continue

        if q.figure_kind == "pie" and q.figure_spec is not None:
            spec = q.figure_spec
            if len(spec.labels) > _MAX_PIE_SLICES or len(spec.values) != len(spec.labels):
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            labs = [(lb or "")[:_MAX_PIE_LABEL_LEN] for lb in spec.labels]
            q.figure_spec = PracticePieSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                labels=labs,
                values=list(spec.values),
            )
            continue

        if q.figure_kind == "table" and q.figure_spec is not None:
            spec = q.figure_spec
            rows = spec.rows[:_MAX_TABLE_ROWS]
            if not rows:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            ncol = min(max(len(r) for r in rows), _MAX_TABLE_COLS)
            pad_rows: list[list[str]] = []
            for r in rows:
                cells = [(c or "")[:_MAX_TABLE_CELL] for c in r[:ncol]]
                while len(cells) < ncol:
                    cells.append("")
                pad_rows.append(cells[:ncol])
            hdr: list[str] = []
            if spec.headers:
                hdr = [(h or "")[:_MAX_TABLE_CELL] for h in spec.headers[:ncol]]
                while len(hdr) < ncol:
                    hdr.append("")
                hdr = hdr[:ncol]
            q.figure_spec = PracticeTableSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                headers=hdr,
                rows=pad_rows,
            )
            continue

        if q.figure_kind == "histogram" and q.figure_spec is not None:
            spec = q.figure_spec
            if len(spec.edges) > _MAX_HIST_BINS + 1 or len(spec.counts) != len(spec.edges) - 1:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            if any(c < 0 for c in spec.counts):
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeHistogramSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                x_label=(spec.x_label or "")[:_MAX_FIG_AXIS_LABEL],
                y_label=(spec.y_label or "")[:_MAX_FIG_AXIS_LABEL],
                edges=list(spec.edges),
                counts=list(spec.counts),
            )
            continue

        if q.figure_kind == "timeline" and q.figure_spec is not None:
            spec = q.figure_spec
            items = [
                PracticeTimelineItem(label=(it.label or "")[:80], t=float(it.t))
                for it in spec.items[:_MAX_TIMELINE_ITEMS]
            ]
            if not items:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeTimelineSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                t_min=spec.t_min,
                t_max=spec.t_max,
                items=items,
                connect=bool(spec.connect),
            )
            continue

        if q.figure_kind == "number_line" and q.figure_spec is not None:
            spec = q.figure_spec
            marks = [
                PracticeNumberLineMark(x=m.x, label=(m.label or "")[:40])
                for m in spec.marks[:_MAX_NL_MARKS]
            ]
            intervals: list[PracticeNumberLineInterval] = []
            for iv in spec.intervals[:_MAX_NL_INTERVALS]:
                intervals.append(
                    PracticeNumberLineInterval(
                        a=iv.a,
                        b=iv.b,
                        open_left=bool(iv.open_left),
                        open_right=bool(iv.open_right),
                    )
                )
            q.figure_spec = PracticeNumberLineSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                x_min=spec.x_min,
                x_max=spec.x_max,
                marks=marks,
                intervals=intervals,
            )
            continue

        if q.figure_kind == "venn" and q.figure_spec is not None:
            spec = q.figure_spec
            q.figure_spec = PracticeVennSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                n_sets=spec.n_sets,
                label_a=(spec.label_a or "")[:20],
                label_b=(spec.label_b or "")[:20],
                label_c=(spec.label_c or "")[:20],
                only_a=(spec.only_a or "")[:120],
                only_b=(spec.only_b or "")[:120],
                only_c=(spec.only_c or "")[:120],
                ab=(spec.ab or "")[:120],
                ac=(spec.ac or "")[:120],
                bc=(spec.bc or "")[:120],
                abc=(spec.abc or "")[:120],
            )
            continue

        if q.figure_kind == "composite" and q.figure_spec is not None:
            spec = q.figure_spec
            new_panels: list[PracticeCompositePanel] = []
            for p in spec.panels[:_MAX_COMPOSITE_PANELS]:
                np = _clamp_composite_panel(p, stem=q.stem)
                if np is not None:
                    new_panels.append(np)
            if not new_panels:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeCompositeSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                ncols=min(3, max(1, spec.ncols)),
                panels=new_panels,
            )
            continue

        if q.figure_kind == "geometry" and q.figure_spec is not None:
            spec = q.figure_spec
            pts = spec.points[:_MAX_GEOM_POINTS]
            segs = spec.segments[:_MAX_GEOM_SEGMENTS]
            labs = spec.labels[:_MAX_GEOM_LABELS]
            geom = _clamp_geometry_spec_inner(spec, pts, segs, labs)
            if geom is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = geom
            continue

        if q.figure_kind == "flowchart" and q.figure_spec is not None:
            spec = q.figure_spec
            nodes: list[PracticeFlowchartNode] = []
            for n in spec.nodes[:_MAX_FLOW_NODES]:
                mx = _MAX_FLOW_TEXT_MATH if n.use_mathtext else _MAX_FLOW_TEXT
                nodes.append(
                    PracticeFlowchartNode(
                        id=(n.id or "")[:32],
                        text=(n.text or "")[:mx],
                        use_mathtext=bool(n.use_mathtext),
                    )
                )
            edges: list[PracticeFlowchartEdge] = []
            for e in spec.edges[:_MAX_FLOW_EDGES]:
                edges.append(
                    PracticeFlowchartEdge(
                        source=(e.source or "")[:32],
                        target=(e.target or "")[:32],
                    )
                )
            if not nodes:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            lay = spec.layout if spec.layout in ("circular", "layered") else "circular"
            q.figure_spec = PracticeFlowchartSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                layout=lay,
                nodes=nodes,
                edges=edges,
            )
            continue

        if q.figure_kind == "force_diagram" and q.figure_spec is not None:
            spec = q.figure_spec
            forces: list[PracticeForceItem] = []
            for f in spec.forces[:_MAX_FORCE_ITEMS]:
                mx = _MAX_FORCE_LABEL_MATH if f.use_mathtext else _MAX_FORCE_LABEL
                forces.append(
                    PracticeForceItem(
                        x0=float(f.x0),
                        y0=float(f.y0),
                        x1=float(f.x1),
                        y1=float(f.y1),
                        label=(f.label or "")[:mx],
                        use_mathtext=bool(f.use_mathtext),
                        color=(f.color or "")[:_MAX_GEOM_COLOR_STR],
                        zorder=int(f.zorder),
                    )
                )
            if not forces:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeForceDiagramSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                forces=forces,
                object_dot=bool(spec.object_dot),
                object_x=float(spec.object_x),
                object_y=float(spec.object_y),
            )
            continue

        if q.figure_kind == "circuit_simple" and q.figure_spec is not None:
            spec = q.figure_spec
            nodes: list[PracticeCircuitNode] = []
            seen: set[str] = set()
            for n in spec.nodes[:_MAX_CIRCUIT_NODES]:
                nid = (n.id or "").strip()
                if not nid or nid in seen:
                    continue
                seen.add(nid)
                nodes.append(
                    PracticeCircuitNode(id=nid[:32], x=float(n.x), y=float(n.y))
                )
            id_set = {n.id for n in nodes}
            edges: list[PracticeCircuitEdge] = []
            for e in spec.edges[:_MAX_CIRCUIT_EDGES]:
                s = (e.source or "").strip()
                t = (e.target or "").strip()
                if s not in id_set or t not in id_set:
                    continue
                vias = [
                    PracticeCircuitVia(x=float(v.x), y=float(v.y))
                    for v in e.via[:8]
                    if math.isfinite(float(v.x)) and math.isfinite(float(v.y))
                ]
                el = e.element if e.element in (
                    "wire",
                    "resistor",
                    "cell",
                    "lamp",
                    "switch",
                    "ammeter",
                    "voltmeter",
                    "generic",
                ) else "wire"
                edges.append(
                    PracticeCircuitEdge(source=s[:32], target=t[:32], element=el, via=vias)
                )
            if len(nodes) < 2 or not edges:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeCircuitSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                nodes=nodes,
                edges=edges,
            )
            continue

        if q.figure_kind == "svg" and q.figure_spec is not None:
            spec = q.figure_spec
            clean = sanitize_practice_svg(spec.svg, max_bytes=_MAX_SVG_BYTES)
            if clean is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = PracticeSvgSpec(
                title=(spec.title or "")[:_MAX_FIG_TITLE],
                caption=(spec.caption or "")[:_MAX_FIG_CAPTION],
                svg=clean,
            )
            continue

        if q.figure_kind == "solid_wireframe" and q.figure_spec is not None:
            cw = _clamp_solid_wireframe_spec_inner(q.figure_spec)
            if cw is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = cw
            continue

        if q.figure_kind == "field_lines" and q.figure_spec is not None:
            cf = _clamp_field_lines_spec_inner(q.figure_spec)
            if cf is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = cf
            continue

        if q.figure_kind == "probability_tree" and q.figure_spec is not None:
            cp = _clamp_probability_tree_spec_inner(q.figure_spec)
            if cp is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = cp
            continue

        if q.figure_kind == "pedigree" and q.figure_spec is not None:
            pp = _clamp_pedigree_spec_inner(q.figure_spec)
            if pp is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = pp
            continue

        if q.figure_kind == "energy_profile" and q.figure_spec is not None:
            ep = _clamp_energy_profile_spec_inner(q.figure_spec)
            if ep is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = ep
            continue

        if q.figure_kind == "electrochemical_cell" and q.figure_spec is not None:
            q.figure_spec = _clamp_electrochemical_cell_spec_inner(q.figure_spec)
            continue

        if q.figure_kind == "unit_circle_trig" and q.figure_spec is not None:
            q.figure_spec = _clamp_unit_circle_trig_spec_inner(q.figure_spec)
            continue

        if q.figure_kind == "optics_ray" and q.figure_spec is not None:
            op = _clamp_optics_ray_spec_inner(q.figure_spec)
            if op is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = op
            continue

        if q.figure_kind == "directed_graph" and q.figure_spec is not None:
            dg = _clamp_directed_graph_spec_inner(q.figure_spec)
            if dg is None:
                q.figure_kind = "none"
                q.figure_spec = None
                continue
            q.figure_spec = dg
            continue


def _sanitize_paper_image_refs(ps: PracticeSet) -> None:
    for q in ps.questions:
        if not q.paper_image_ref:
            continue
        p = resolve_under_data_dir(q.paper_image_ref)
        if p is None or not p.is_file():
            logger.info(
                "practice_clamp: cleared invalid paper_image_ref for order_index=%s",
                q.order_index,
            )
            q.paper_image_ref = None


def clamp_practice_set(ps: PracticeSet, *, include_figures: bool = True) -> PracticeSet:
    if not include_figures:
        for q in ps.questions:
            q.figure_kind = "none"
            q.figure_spec = None
            q.use_paper_figure = False
            q.paper_image_ref = None

    before_figure = [q.figure_kind for q in ps.questions]
    for q in ps.questions:
        if len(q.stem) > _MAX_STEM:
            q.stem = q.stem[:_MAX_STEM] + "…（题干过长已截断）"
        if len(q.answer_outline) > _MAX_OUTLINE:
            q.answer_outline = q.answer_outline[:_MAX_OUTLINE] + "…（解析过长已截断）"
        if q.options:
            q.options = [
                (o[:_MAX_OPTION_LEN] + "…") if len(o) > _MAX_OPTION_LEN else o for o in q.options
            ]
    _sanitize_practice_figures(ps)
    if include_figures:
        _sanitize_paper_image_refs(ps)
    downgraded = sum(
        1
        for b, q in zip(before_figure, ps.questions)
        if b != "none" and q.figure_kind == "none"
    )
    if downgraded:
        logger.info(
            "practice_clamp: figure_kind cleared for %s question(s) (sanitize/limits)",
            downgraded,
        )
    return ps

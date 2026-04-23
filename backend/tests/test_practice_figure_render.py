from __future__ import annotations

import io

import matplotlib.image as mpimg
import pytest

from app.models.schemas import (
    PracticeBarSpec,
    PracticeCircuitEdge,
    PracticeCircuitNode,
    PracticeCircuitSpec,
    PracticeCircuitVia,
    PracticeCompositePanelBar,
    PracticeCompositePanelCircuit,
    PracticeCompositePanelPlot,
    PracticeCompositePanelSvg,
    PracticeCompositeSpec,
    PracticeDirectedGraphEdge,
    PracticeDirectedGraphNode,
    PracticeDirectedGraphSpec,
    PracticeElectrochemicalCellSpec,
    PracticeEnergyProfileSpec,
    PracticeFlowchartEdge,
    PracticeFlowchartNode,
    PracticeFlowchartSpec,
    PracticeForceDiagramSpec,
    PracticeForceItem,
    PracticeGeometryCircle,
    PracticeGeometryLabel,
    PracticeGeometryPolygon,
    PracticeGeometrySpec,
    PracticeGroupedBarSeries,
    PracticeGroupedBarSpec,
    PracticeHistogramSpec,
    PracticeNumberLineMark,
    PracticeNumberLineInterval,
    PracticeNumberLineSpec,
    PracticePedigreeDescent,
    PracticePedigreeIndividual,
    PracticePedigreeMarriage,
    PracticePedigreeSpec,
    PracticePieSpec,
    PracticeProbabilityTreeNode,
    PracticeProbabilityTreeSpec,
    PracticePlotFillBetween,
    PracticePlotSeries,
    PracticePlotSpec,
    PracticePoint2D,
    PracticeQuestion,
    PracticeSegment,
    PracticeSolidEdge,
    PracticeSolidVertex3D,
    PracticeSolidWireframeSpec,
    PracticeSvgSpec,
    PracticeTableSpec,
    PracticeTimelineItem,
    PracticeTimelineSpec,
    PracticeVennSpec,
)
from app.services.practice_figure_render import (
    render_bar_to_png_bytes,
    render_circuit_simple_to_png_bytes,
    render_composite_to_png_bytes,
    render_flowchart_to_png_bytes,
    render_force_diagram_to_png_bytes,
    render_geometry_to_png_bytes,
    render_grouped_bar_to_png_bytes,
    render_histogram_to_png_bytes,
    render_number_line_to_png_bytes,
    render_pie_to_png_bytes,
    render_pedigree_to_png_bytes,
    render_directed_graph_to_png_bytes,
    render_electrochemical_cell_to_png_bytes,
    render_energy_profile_to_png_bytes,
    render_plot_to_png_bytes,
    render_probability_tree_to_png_bytes,
    render_question_figure_to_png_bytes,
    render_question_figure_with_diag,
    render_solid_wireframe_to_png_bytes,
    render_table_to_png_bytes,
    render_timeline_to_png_bytes,
    render_venn_to_png_bytes,
)


def _load_png_float_rgb(png_bytes: bytes):
    img = mpimg.imread(io.BytesIO(png_bytes), format="png")
    if getattr(img, "dtype", None) is not None and img.dtype.kind in ("u", "i"):
        img = img.astype("float32") / 255.0
    return img[..., :3]


def test_render_plot_to_png_bytes_minimal():
    spec = PracticePlotSpec(
        series=[PracticePlotSeries(label="line", x=[0.0, 1.0, 2.0], y=[1.0, 0.0, 1.0])]
    )
    b = render_plot_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 500
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_grouped_bar_to_png_bytes_minimal():
    spec = PracticeGroupedBarSpec(
        categories=["一", "二"],
        series=[
            PracticeGroupedBarSeries(label="A", values=[1.0, 2.0]),
            PracticeGroupedBarSeries(label="B", values=[3.0, 4.0]),
        ],
    )
    b = render_grouped_bar_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 500
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_bar_to_png_bytes_minimal():
    spec = PracticeBarSpec(categories=["一", "二"], values=[3.0, 7.0])
    b = render_bar_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 500
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_pie_to_png_bytes_minimal():
    spec = PracticePieSpec(labels=["甲", "乙"], values=[40.0, 60.0])
    b = render_pie_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 500
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_pie_merges_small_slices():
    labels = ["a", "b", "c", "d", "main"]
    values = [1.0, 1.0, 1.0, 1.0, 96.0]
    spec = PracticePieSpec(labels=labels, values=values)
    b = render_pie_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_geometry_to_png_bytes_minimal():
    spec = PracticeGeometrySpec(
        title="△",
        points=[
            PracticePoint2D(id="A", x=0, y=0),
            PracticePoint2D(id="B", x=1, y=0),
            PracticePoint2D(id="C", x=0.5, y=0.8),
        ],
        segments=[
            PracticeSegment(a="A", b="B"),
            PracticeSegment(a="B", b="C"),
            PracticeSegment(a="C", b="A"),
        ],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_flowchart_to_png_bytes_minimal():
    spec = PracticeFlowchartSpec(
        title="流程",
        nodes=[
            PracticeFlowchartNode(id="a", text="开始"),
            PracticeFlowchartNode(id="b", text="结束"),
        ],
        edges=[PracticeFlowchartEdge(source="a", target="b")],
    )
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_geometry_empty_returns_none():
    spec = PracticeGeometrySpec(points=[], segments=[], labels=[])
    assert render_geometry_to_png_bytes(spec) is None


def test_render_geometry_single_point_no_segments():
    spec = PracticeGeometrySpec(points=[PracticePoint2D(id="P", x=2.0, y=2.0)])
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_geometry_long_label_truncated_still_png():
    long_t = "长" * 80
    spec = PracticeGeometrySpec(
        points=[PracticePoint2D(id="A", x=0, y=0)],
        labels=[PracticeGeometryLabel(text=long_t, x=0.5, y=0.5)],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_geometry_skips_bad_segment_endpoints():
    spec = PracticeGeometrySpec(
        points=[
            PracticePoint2D(id="A", x=0, y=0),
            PracticePoint2D(id="B", x=1, y=0),
        ],
        segments=[
            PracticeSegment(a="A", b="missing"),
            PracticeSegment(a="A", b="B"),
        ],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_geometry_duplicate_point_ids_renamed():
    spec = PracticeGeometrySpec(
        points=[
            PracticePoint2D(id="A", x=0, y=0),
            PracticePoint2D(id="A", x=1, y=1),
        ],
        segments=[PracticeSegment(a="A", b="_p1_A")],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_geometry_all_non_finite_points_returns_none():
    spec = PracticeGeometrySpec(
        points=[
            PracticePoint2D(id="X", x=float("nan"), y=0.0),
            PracticePoint2D(id="Y", x=0.0, y=float("inf")),
        ],
    )
    assert render_geometry_to_png_bytes(spec) is None


def test_render_flowchart_single_node_no_edges():
    spec = PracticeFlowchartSpec(
        nodes=[PracticeFlowchartNode(id="only", text="单步")],
        edges=[],
    )
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_flowchart_duplicate_node_id_keeps_first():
    spec = PracticeFlowchartSpec(
        nodes=[
            PracticeFlowchartNode(id="x", text="first"),
            PracticeFlowchartNode(id="x", text="dup"),
            PracticeFlowchartNode(id="y", text="other"),
        ],
        edges=[PracticeFlowchartEdge(source="x", target="y")],
    )
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_flowchart_many_nodes_smoke():
    nodes = [
        PracticeFlowchartNode(id=f"n{i}", text=f"步{i}")
        for i in range(16)
    ]
    edges = [
        PracticeFlowchartEdge(source=f"n{i}", target=f"n{i + 1}")
        for i in range(15)
    ]
    spec = PracticeFlowchartSpec(title="多节点", nodes=nodes, edges=edges)
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_flowchart_all_edges_unknown_still_png():
    spec = PracticeFlowchartSpec(
        nodes=[
            PracticeFlowchartNode(id="a", text="A"),
            PracticeFlowchartNode(id="b", text="B"),
        ],
        edges=[
            PracticeFlowchartEdge(source="ghost", target="a"),
            PracticeFlowchartEdge(source="b", target="void"),
        ],
    )
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_flowchart_self_loop_does_not_crash():
    spec = PracticeFlowchartSpec(
        nodes=[PracticeFlowchartNode(id="s", text="自环")],
        edges=[PracticeFlowchartEdge(source="s", target="s")],
    )
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_question_figure_geometry_dispatch():
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="s",
        options=[],
        answer_outline="a",
        figure_kind="geometry",
        figure_spec=PracticeGeometrySpec(points=[PracticePoint2D(id="P", x=0, y=0)]),
    )
    b = render_question_figure_to_png_bytes(q)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_plot_log_y_and_no_legend():
    spec = PracticePlotSpec(
        series=[PracticePlotSeries(label="a", x=[1.0, 2.0, 3.0], y=[10.0, 100.0, 1000.0])],
        log_y=True,
        show_legend=False,
    )
    b = render_plot_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_plot_with_fill_between():
    spec = PracticePlotSpec(
        series=[PracticePlotSeries(label="y", x=[0.0, 1.0, 2.0], y=[0.0, 1.0, 0.0])],
        show_legend=False,
        fill_between=[
            PracticePlotFillBetween(
                x=[0.0, 1.0, 2.0],
                y_lower=[0.0, 0.0, 0.0],
                y_upper=[0.0, 1.0, 0.0],
                alpha=0.35,
            )
        ],
    )
    b = render_plot_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_table_to_png_bytes_minimal():
    spec = PracticeTableSpec(
        headers=["列1", "列2"],
        rows=[["a", "b"], ["1", "2"]],
    )
    b = render_table_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_timeline_to_png_bytes_minimal():
    spec = PracticeTimelineSpec(
        items=[
            PracticeTimelineItem(label="T1", t=0.0),
            PracticeTimelineItem(label="T2", t=2.0),
        ],
        connect=True,
    )
    b = render_timeline_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_number_line_to_png_bytes_minimal():
    spec = PracticeNumberLineSpec(
        x_min=-1.0,
        x_max=3.0,
        marks=[PracticeNumberLineMark(x=0.0, label="0"), PracticeNumberLineMark(x=2.0, label="2")],
    )
    b = render_number_line_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_venn_two_sets():
    spec = PracticeVennSpec(
        n_sets=2,
        only_a="仅A",
        only_b="仅B",
        ab="交",
    )
    b = render_venn_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_histogram_to_png_bytes_minimal():
    spec = PracticeHistogramSpec(edges=[0.0, 1.0, 2.0, 3.0], counts=[2.0, 5.0, 1.0])
    b = render_histogram_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 100


def test_render_composite_two_panels():
    spec = PracticeCompositeSpec(
        title="组合",
        ncols=2,
        panels=[
            PracticeCompositePanelPlot(
                spec=PracticePlotSpec(
                    series=[PracticePlotSeries(label="l", x=[0.0, 1.0], y=[0.0, 1.0])],
                    show_legend=False,
                ),
                subtitle="甲",
            ),
            PracticeCompositePanelBar(
                spec=PracticeBarSpec(categories=["一", "二"], values=[1.0, 2.0]),
                subtitle="乙",
            ),
        ],
    )
    b = render_composite_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_question_figure_composite_dispatch():
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="s",
        options=[],
        answer_outline="a",
        figure_kind="composite",
        figure_spec=PracticeCompositeSpec(
            ncols=1,
            panels=[
                PracticeCompositePanelPlot(
                    spec=PracticePlotSpec(
                        series=[PracticePlotSeries(label="l", x=[0.0, 1.0], y=[1.0, 0.0])],
                        show_legend=False,
                    )
                )
            ],
        ),
    )
    b = render_question_figure_to_png_bytes(q)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_geometry_circle_and_polygon():
    spec = PracticeGeometrySpec(
        points=[
            PracticePoint2D(id="A", x=0, y=0),
            PracticePoint2D(id="B", x=2, y=0),
            PracticePoint2D(id="C", x=1, y=1.5),
        ],
        circles=[PracticeGeometryCircle(cx=1.0, cy=0.6, r=0.45, fill=False)],
        polygons=[
            PracticeGeometryPolygon(vertex_ids=["A", "B", "C"], fill=True, alpha=0.15),
        ],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_force_diagram_minimal():
    spec = PracticeForceDiagramSpec(
        forces=[
            PracticeForceItem(x0=0, y0=0, x1=1, y1=0.5, label="F"),
            PracticeForceItem(x0=0, y0=0, x1=-0.5, y1=0.8, label="G"),
        ],
        object_dot=True,
        object_x=0,
        object_y=0,
    )
    b = render_force_diagram_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_force_diagram_block_normalize_axes_hint():
    spec = PracticeForceDiagramSpec(
        forces=[
            PracticeForceItem(x0=0, y0=0, x1=0.3, y1=0, label="F1"),
            PracticeForceItem(x0=0, y0=0, x1=0, y1=0.9, label="F2"),
        ],
        object_style="block",
        object_x=0,
        object_y=0,
        normalize_force_lengths=True,
        show_axes_hint=True,
    )
    b = render_force_diagram_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_solid_wireframe_oblique():
    spec = PracticeSolidWireframeSpec(
        title="斜二测",
        projection="oblique",
        vertices=[
            PracticeSolidVertex3D(id="A", x=0, y=0, z=0),
            PracticeSolidVertex3D(id="B", x=1.2, y=0, z=0),
            PracticeSolidVertex3D(id="C", x=1.2, y=0, z=0.8),
            PracticeSolidVertex3D(id="D", x=0, y=0, z=0.8),
        ],
        edges=[
            PracticeSolidEdge(a="A", b="B"),
            PracticeSolidEdge(a="B", b="C"),
            PracticeSolidEdge(a="C", b="D"),
            PracticeSolidEdge(a="D", b="A"),
        ],
    )
    b = render_solid_wireframe_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_pedigree_proband_legend():
    spec = PracticePedigreeSpec(
        individuals=[
            PracticePedigreeIndividual(id="p1", generation=0, sex="male", carrier=True),
            PracticePedigreeIndividual(id="p2", generation=0, sex="female", deceased=True),
            PracticePedigreeIndividual(id="c1", generation=1, sex="male", affected=True),
        ],
        marriages=[PracticePedigreeMarriage(left="p1", right="p2")],
        descents=[PracticePedigreeDescent(mother="p2", father="p1", child="c1")],
        proband_id="c1",
        show_legend=True,
    )
    b = render_pedigree_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_circuit_simple_series():
    spec = PracticeCircuitSpec(
        title="串联",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=1, y=0),
            PracticeCircuitNode(id="c", x=2, y=0),
        ],
        edges=[
            PracticeCircuitEdge(source="a", target="b", element="cell"),
            PracticeCircuitEdge(source="b", target="c", element="resistor"),
        ],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_circuit_capacitor_branch():
    spec = PracticeCircuitSpec(
        title="电容",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=1.2, y=0),
        ],
        edges=[PracticeCircuitEdge(source="a", target="b", element="capacitor")],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 150
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_circuit_parallel_resistors_smoke():
    spec = PracticeCircuitSpec(
        title="并联示意",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=2, y=0),
            PracticeCircuitNode(id="m1", x=1, y=0.6),
            PracticeCircuitNode(id="m2", x=1, y=-0.6),
        ],
        edges=[
            PracticeCircuitEdge(source="a", target="m1", element="wire"),
            PracticeCircuitEdge(source="m1", target="b", element="resistor"),
            PracticeCircuitEdge(source="a", target="m2", element="wire"),
            PracticeCircuitEdge(source="m2", target="b", element="resistor"),
        ],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_circuit_via_polyline_smoke():
    spec = PracticeCircuitSpec(
        title="折线",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=2, y=0),
        ],
        edges=[
            PracticeCircuitEdge(
                source="a",
                target="b",
                element="wire",
                via=[PracticeCircuitVia(x=1.0, y=0.7)],
            ),
        ],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 150


def test_render_circuit_ammeter_voltmeter_series_smoke():
    spec = PracticeCircuitSpec(
        title="表计",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=1, y=0),
            PracticeCircuitNode(id="c", x=2, y=0),
        ],
        edges=[
            PracticeCircuitEdge(source="a", target="b", element="ammeter"),
            PracticeCircuitEdge(source="b", target="c", element="voltmeter"),
        ],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_circuit_star_hub_degree3_junction():
    """中心节点度≥3 时应渲染实心结点（教材 T 型汇点）。"""
    spec = PracticeCircuitSpec(
        title="星形",
        nodes=[
            PracticeCircuitNode(id="hub", x=1.0, y=1.0),
            PracticeCircuitNode(id="A", x=0.0, y=1.0),
            PracticeCircuitNode(id="B", x=1.0, y=0.0),
            PracticeCircuitNode(id="C", x=2.0, y=1.0),
        ],
        edges=[
            PracticeCircuitEdge(source="hub", target="A", element="wire"),
            PracticeCircuitEdge(source="hub", target="B", element="resistor"),
            PracticeCircuitEdge(source="hub", target="C", element="wire"),
        ],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 400
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_circuit_resistor_keeps_center_body_clear_of_wire():
    """完整器件电阻应有引脚与本体，中心不应被整根导线贯穿。"""
    spec = PracticeCircuitSpec(
        title="完整电阻",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=2.4, y=0),
        ],
        edges=[PracticeCircuitEdge(source="a", target="b", element="resistor")],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    img = _load_png_float_rgb(b)
    h, w = img.shape[:2]
    center_half_w = max(20, w // 10)
    center_cols = img[:, w // 2 - center_half_w : w // 2 + center_half_w, :]
    dark_mask = (1.0 - center_cols.mean(axis=2)) > 0.25
    wire_row = int(dark_mask.sum(axis=1).argmax())
    center_span = dark_mask[wire_row, center_half_w - 20 : center_half_w + 21]
    assert int(center_span.sum()) <= 12


def test_render_circuit_extended_components_smoke():
    spec = PracticeCircuitSpec(
        title="扩展元件",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=1.2, y=0),
            PracticeCircuitNode(id="c", x=2.4, y=0),
            PracticeCircuitNode(id="d", x=3.6, y=0),
            PracticeCircuitNode(id="e", x=4.8, y=0),
        ],
        edges=[
            PracticeCircuitEdge(source="a", target="b", element="battery"),
            PracticeCircuitEdge(source="b", target="c", element="rheostat"),
            PracticeCircuitEdge(source="c", target="d", element="fuse"),
            PracticeCircuitEdge(source="d", target="e", element="diode"),
        ],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 220
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_circuit_switch_open_closed_states_differ():
    open_spec = PracticeCircuitSpec(
        title="开关状态",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=1.4, y=0),
        ],
        edges=[
            PracticeCircuitEdge(source="a", target="b", element="switch", switch_state="open"),
        ],
    )
    closed_spec = PracticeCircuitSpec(
        title="开关状态",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=1.4, y=0),
        ],
        edges=[
            PracticeCircuitEdge(source="a", target="b", element="switch", switch_state="closed"),
        ],
    )
    open_png = render_circuit_simple_to_png_bytes(open_spec)
    closed_png = render_circuit_simple_to_png_bytes(closed_spec)
    assert open_png is not None and closed_png is not None
    assert open_png != closed_png


def test_render_circuit_rheostat_slider_position_changes_symbol():
    left_spec = PracticeCircuitSpec(
        title="滑动变阻器",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=2.2, y=0),
        ],
        edges=[
            PracticeCircuitEdge(
                source="a",
                target="b",
                element="rheostat",
                slider_position=0.2,
            ),
        ],
    )
    right_spec = PracticeCircuitSpec(
        title="滑动变阻器",
        nodes=[
            PracticeCircuitNode(id="a", x=0, y=0),
            PracticeCircuitNode(id="b", x=2.2, y=0),
        ],
        edges=[
            PracticeCircuitEdge(
                source="a",
                target="b",
                element="rheostat",
                slider_position=0.8,
            ),
        ],
    )
    left_png = render_circuit_simple_to_png_bytes(left_spec)
    right_png = render_circuit_simple_to_png_bytes(right_spec)
    assert left_png is not None and right_png is not None
    assert left_png != right_png


def test_render_circuit_dual_meter_parallel_series_layout_smoke():
    spec = PracticeCircuitSpec(
        title="双电表标准布局",
        nodes=[
            PracticeCircuitNode(id="lt", x=0.0, y=1.0),
            PracticeCircuitNode(id="mt", x=1.3, y=1.0),
            PracticeCircuitNode(id="rt", x=2.6, y=1.0),
            PracticeCircuitNode(id="lb", x=0.0, y=0.0),
            PracticeCircuitNode(id="rb", x=2.6, y=0.0),
        ],
        edges=[
            PracticeCircuitEdge(source="lt", target="mt", element="ammeter"),
            PracticeCircuitEdge(source="mt", target="rt", element="resistor"),
            PracticeCircuitEdge(source="rt", target="rb", element="wire"),
            PracticeCircuitEdge(source="rb", target="lb", element="wire"),
            PracticeCircuitEdge(source="lb", target="lt", element="battery"),
            PracticeCircuitEdge(source="mt", target="rb", element="voltmeter"),
        ],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 260
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_probability_tree_smoke():
    spec = PracticeProbabilityTreeSpec(
        nodes=[
            PracticeProbabilityTreeNode(id="r", text="根", parent_id=""),
            PracticeProbabilityTreeNode(id="l", text="叶", parent_id="r", edge_label="0.5"),
        ],
    )
    b = render_probability_tree_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_directed_graph_layered_smoke():
    spec = PracticeDirectedGraphSpec(
        layout="layered",
        nodes=[
            PracticeDirectedGraphNode(id="a", text="A", layer=0),
            PracticeDirectedGraphNode(id="b", text="B", layer=1),
        ],
        edges=[PracticeDirectedGraphEdge(source="a", target="b", label="→")],
    )
    b = render_directed_graph_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_flowchart_layered_chain():
    spec = PracticeFlowchartSpec(
        layout="layered",
        nodes=[
            PracticeFlowchartNode(id="1", text="开始"),
            PracticeFlowchartNode(id="2", text="处理"),
            PracticeFlowchartNode(id="3", text="结束"),
        ],
        edges=[
            PracticeFlowchartEdge(source="1", target="2"),
            PracticeFlowchartEdge(source="2", target="3"),
        ],
    )
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_plot_twin_axis_and_scatter():
    spec = PracticePlotSpec(
        series=[
            PracticePlotSeries(label="v", x=[0.0, 1.0, 2.0], y=[0.0, 2.0, 1.0], draw_as="scatter"),
        ],
        series_right=[PracticePlotSeries(label="i", x=[0.0, 1.0, 2.0], y=[10.0, 8.0, 6.0])],
        y_label="v",
        y_label_right="i",
        show_legend=True,
    )
    b = render_plot_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_geometry_mathtext_label_smoke():
    spec = PracticeGeometrySpec(
        points=[PracticePoint2D(id="P", x=0, y=0)],
        labels=[
            PracticeGeometryLabel(
                text=r"$\theta$",
                x=0.5,
                y=0.5,
                use_mathtext=True,
            )
        ],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_geometry_dollar_wrapped_label_without_use_mathtext_smoke():
    """未设 use_mathtext 但写了 $A$ 时仍按 mathtext 渲染，避免画出字面量 $。"""
    spec = PracticeGeometrySpec(
        points=[PracticePoint2D(id="P", x=0, y=0)],
        labels=[
            PracticeGeometryLabel(
                text=r"$A$",
                x=0.5,
                y=0.5,
                use_mathtext=False,
            )
        ],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_geometry_mixed_dollar_chinese_label_without_use_mathtext_smoke():
    """$20$ 米 等「公式 + 汉字」混排，整段不以 $ 结尾，仍须走 mathtext。"""
    spec = PracticeGeometrySpec(
        points=[PracticePoint2D(id="P", x=0, y=0)],
        labels=[
            PracticeGeometryLabel(
                text=r"$20$ 米",
                x=0.5,
                y=0.5,
                use_mathtext=False,
            )
        ],
    )
    b = render_geometry_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_composite_with_svg_panel():
    from app.services.practice_svg_safe import rasterize_svg_to_png

    svg_inner = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="40">'
        '<rect width="50" height="30" fill="#228822"/>'
        "</svg>"
    )
    if rasterize_svg_to_png(svg_inner) is None:
        pytest.skip("cairosvg 或系统 cairo 不可用，跳过 composite SVG 栅格化用例")
    spec = PracticeCompositeSpec(
        title="组合",
        ncols=2,
        panels=[
            PracticeCompositePanelSvg(subtitle="矢", spec=PracticeSvgSpec(svg=svg_inner)),
            PracticeCompositePanelPlot(
                subtitle="线",
                spec=PracticePlotSpec(
                    series=[PracticePlotSeries(x=[0, 1], y=[0, 1])],
                ),
            ),
        ],
    )
    b = render_composite_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 200


def test_render_question_figure_with_diag_kind_spec_mismatch():
    q = PracticeQuestion.model_construct(
        order_index=1,
        qtype="填空",
        stem="x",
        options=[],
        figure_kind="plot",
        figure_spec=PracticeBarSpec(categories=["一"], values=[1.0]),
    )
    png, reason = render_question_figure_with_diag(q)
    assert png is None
    assert "kind_spec_mismatch" in reason


def test_render_number_line_open_closed_interval_schema_fields():
    spec = PracticeNumberLineSpec(
        x_min=-2.0,
        x_max=3.0,
        auto_ticks=False,
        show_axis_arrows=True,
        intervals=[PracticeNumberLineInterval(a=-1.0, b=2.0, open_left=True, open_right=False)],
        marks=[PracticeNumberLineMark(x=-1.0, label="-1"), PracticeNumberLineMark(x=2.0, label="2")],
    )
    b = render_number_line_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 120


def test_render_flowchart_shapes_and_edge_labels_smoke():
    spec = PracticeFlowchartSpec(
        layout="layered",
        nodes=[
            PracticeFlowchartNode(id="s", text="开始", shape="start_end"),
            PracticeFlowchartNode(id="q", text="判断", shape="decision"),
            PracticeFlowchartNode(id="d", text="数据", shape="data"),
        ],
        edges=[
            PracticeFlowchartEdge(source="s", target="q", label="进入"),
            PracticeFlowchartEdge(source="q", target="d", label="是"),
        ],
    )
    b = render_flowchart_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_energy_profile_custom_endpoint_labels():
    spec = PracticeEnergyProfileSpec(
        x=[0.0, 1.0, 2.2],
        y=[0.2, 1.1, 0.5],
        barrier_i=0,
        barrier_j=1,
        barrier_label="Ea",
        reactants_label="R",
        products_label="P",
    )
    b = render_energy_profile_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 120


def test_render_electrochemical_with_half_reactions():
    spec = PracticeElectrochemicalCellSpec(
        left_label="Zn",
        right_label="Cu",
        electrolyte_label="ZnSO4 / CuSO4",
        mode="galvanic",
        salt_bridge_u=True,
        half_reaction_left="Zn -> Zn2+ + 2e-",
        half_reaction_right="Cu2+ + 2e- -> Cu",
    )
    b = render_electrochemical_cell_to_png_bytes(spec)
    assert b is not None
    assert b[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_circuit_edge_label_smoke():
    spec = PracticeCircuitSpec(
        nodes=[PracticeCircuitNode(id="a", x=0, y=0), PracticeCircuitNode(id="b", x=2.0, y=0)],
        edges=[PracticeCircuitEdge(source="a", target="b", element="resistor", label="R1=10Ω")],
    )
    b = render_circuit_simple_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 140


def test_render_pedigree_individual_note_smoke():
    spec = PracticePedigreeSpec(
        individuals=[
            PracticePedigreeIndividual(id="p1", generation=0, sex="female", note="母亲"),
            PracticePedigreeIndividual(id="p2", generation=0, sex="male", note="父亲"),
            PracticePedigreeIndividual(id="c1", generation=1, sex="male", affected=True, note="先证者"),
        ],
        marriages=[PracticePedigreeMarriage(left="p2", right="p1")],
        descents=[PracticePedigreeDescent(mother="p1", father="p2", child="c1")],
    )
    b = render_pedigree_to_png_bytes(spec)
    assert b is not None
    assert len(b) > 120

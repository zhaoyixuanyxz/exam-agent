"""Phase 11：field_lines presets、optics 扩展、solid 辅助边、directed_graph 等烟测。"""

from __future__ import annotations

import pytest

from app.models.schemas import (
    PracticeDirectedGraphEdge,
    PracticeDirectedGraphNode,
    PracticeDirectedGraphSpec,
    PracticeFieldLinesSpec,
    PracticeFieldPresetLongStraightWire,
    PracticeFieldPresetPointCharge,
    PracticeFieldPresetSolenoid,
    PracticeOpticsRaySegment,
    PracticeOpticsRaySpec,
    PracticeQuestion,
    PracticeSolidAuxiliaryEdge,
    PracticeSolidEdge,
    PracticeSolidVertex3D,
    PracticeSolidWireframeSpec,
)
from app.services.practice_figure_render import (
    render_directed_graph_to_png_bytes,
    render_field_lines_to_png_bytes,
    render_optics_ray_to_png_bytes,
    render_solid_wireframe_to_png_bytes,
)


def _png_ok(b: bytes | None) -> None:
    assert b is not None and b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) > 400


def test_field_lines_preset_point_charge():
    spec = PracticeFieldLinesSpec(
        presets=[
            PracticeFieldPresetPointCharge(cx=0, cy=0, sign=1, n_lines=10, r_max=1.4, r_min=0.12),
        ],
    )
    _png_ok(render_field_lines_to_png_bytes(spec))


def test_field_lines_preset_solenoid():
    spec = PracticeFieldLinesSpec(
        presets=[PracticeFieldPresetSolenoid(x0=-0.5, y0=-0.8, w=1.6, h=2.0, b_direction="right", nx=3, ny=4)],
    )
    _png_ok(render_field_lines_to_png_bytes(spec))


def test_field_lines_preset_long_wire():
    spec = PracticeFieldLinesSpec(
        presets=[PracticeFieldPresetLongStraightWire(cx=0, cy=0, n_circles=5, r_max=1.6, current_out_of_page=True)],
    )
    _png_ok(render_field_lines_to_png_bytes(spec))


def test_field_lines_manual_plus_preset():
    spec = PracticeFieldLinesSpec(
        lines=[],
        presets=[PracticeFieldPresetPointCharge(sign=-1, n_lines=8)],
        uniform_field=None,
    )
    _png_ok(render_field_lines_to_png_bytes(spec))


@pytest.mark.parametrize(
    "orientation,kwargs",
    [
        ("horizontal", {}),
        ("vertical", {"interface_x": 0.2}),
        ("angled", {"interface_pivot_x": 0.0, "interface_pivot_y": 0.0, "interface_angle_deg": 35.0}),
    ],
)
def test_optics_ray_interface_variants(orientation: str, kwargs: dict):
    spec = PracticeOpticsRaySpec(
        interface_orientation=orientation,
        interface_y=0.0,
        **kwargs,
        rays=[
            PracticeOpticsRaySegment(x0=-1, y0=0.4, x1=0, y1=0),
            PracticeOpticsRaySegment(x0=0, y0=0, x1=1, y1=-0.3),
        ],
    )
    _png_ok(render_optics_ray_to_png_bytes(spec))


def test_optics_ray_principal_axis_and_thin_lens():
    spec = PracticeOpticsRaySpec(
        interface_orientation="vertical",
        interface_x=-0.3,
        principal_axis={"x0": -1.5, "y0": 0, "x1": 1.5, "y1": 0},
        thin_lens={"center_x": 0.5, "center_y": 0, "diameter": 1.0, "convex_toward_right": True},
        rays=[PracticeOpticsRaySegment(x0=-1.2, y0=0.2, x1=0.4, y1=0)],
        show_normal=True,
    )
    _png_ok(render_optics_ray_to_png_bytes(spec))


def test_solid_wireframe_auxiliary_edges():
    spec = PracticeSolidWireframeSpec(
        projection="isometric",
        vertices=[
            PracticeSolidVertex3D(id="A", x=0, y=0, z=0),
            PracticeSolidVertex3D(id="B", x=1.5, y=0, z=0),
            PracticeSolidVertex3D(id="C", x=1.5, y=1.2, z=0),
        ],
        edges=[
            PracticeSolidEdge(a="A", b="B"),
            PracticeSolidEdge(a="B", b="C"),
        ],
        auxiliary_edges=[
            PracticeSolidAuxiliaryEdge(a="A", b="C", style="dashed", label="辅助"),
        ],
    )
    _png_ok(render_solid_wireframe_to_png_bytes(spec))


def test_directed_graph_layered_png():
    spec = PracticeDirectedGraphSpec(
        layout="layered",
        nodes=[
            PracticeDirectedGraphNode(id="sun", text="光", layer=0),
            PracticeDirectedGraphNode(id="grass", text="草", layer=1),
            PracticeDirectedGraphNode(id="rabbit", text="兔", layer=2),
        ],
        edges=[
            PracticeDirectedGraphEdge(source="sun", target="grass"),
            PracticeDirectedGraphEdge(source="grass", target="rabbit"),
        ],
    )
    _png_ok(render_directed_graph_to_png_bytes(spec))


def test_directed_graph_question_dispatch():
    from app.services.practice_figure_render import render_question_figure_to_png_bytes

    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="链",
        options=[],
        answer_outline="",
        figure_kind="directed_graph",
        figure_spec=PracticeDirectedGraphSpec(
            layout="layered",
            nodes=[
                PracticeDirectedGraphNode(id="a", text="A", layer=0),
                PracticeDirectedGraphNode(id="b", text="B", layer=1),
            ],
            edges=[PracticeDirectedGraphEdge(source="a", target="b")],
        ),
    )
    _png_ok(render_question_figure_to_png_bytes(q))

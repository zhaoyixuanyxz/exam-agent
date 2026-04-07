"""Phase 10 新 figure_kind：渲染与 PDF 非像素级烟测。"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.models.schemas import (
    PracticeCompositePanelFieldLines,
    PracticeCompositePanelSolidWireframe,
    PracticeCompositePanelUnitCircleTrig,
    PracticeCompositeSpec,
    PracticeElectrochemicalCellSpec,
    PracticeEnergyProfileSpec,
    PracticeFieldLine,
    PracticeFieldLinesSpec,
    PracticePedigreeDescent,
    PracticePedigreeIndividual,
    PracticePedigreeMarriage,
    PracticePedigreeSpec,
    PracticeProbabilityTreeNode,
    PracticeProbabilityTreeSpec,
    PracticeQuestion,
    PracticeSet,
    PracticeSolidEdge,
    PracticeSolidFace,
    PracticeSolidVertex3D,
    PracticeSolidWireframeSpec,
    PracticeOpticsRaySegment,
    PracticeOpticsRaySpec,
    PracticeUnitCircleTrigSpec,
)
from app.services.fonts import resolve_kaiti_font
from app.services.pdf_render import render_practice_pdf
from app.services.practice_figure_render import (
    render_composite_to_png_bytes,
    render_question_figure_to_png_bytes,
)

_MIN_PNG = 400
_MIN_PDF = 1200


def _assert_png(b: bytes | None) -> None:
    assert b is not None and b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= _MIN_PNG


def test_solid_wireframe_png():
    spec = PracticeSolidWireframeSpec(
        title="棱锥",
        projection="isometric",
        vertices=[
            PracticeSolidVertex3D(id="A", x=0, y=0, z=0),
            PracticeSolidVertex3D(id="B", x=2, y=0, z=0),
            PracticeSolidVertex3D(id="C", x=2, y=2, z=0),
            PracticeSolidVertex3D(id="D", x=0, y=2, z=0),
            PracticeSolidVertex3D(id="S", x=1, y=1, z=1.8),
        ],
        edges=[
            PracticeSolidEdge(a="A", b="B"),
            PracticeSolidEdge(a="B", b="C"),
            PracticeSolidEdge(a="C", b="D"),
            PracticeSolidEdge(a="D", b="A"),
            PracticeSolidEdge(a="S", b="A"),
            PracticeSolidEdge(a="S", b="B"),
            PracticeSolidEdge(a="S", b="C"),
            PracticeSolidEdge(a="S", b="D"),
        ],
        faces=[
            PracticeSolidFace(vertex_ids=["A", "B", "C", "D"], alpha=0.4),
        ],
    )
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="立体",
        options=[],
        answer_outline="",
        figure_kind="solid_wireframe",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_field_lines_png():
    spec = PracticeFieldLinesSpec(
        title="电场线",
        lines=[
            PracticeFieldLine(x=[-1, 0, 1], y=[0.5, 0, -0.5], arrow="end"),
            PracticeFieldLine(x=[-1, 0, 1], y=[-0.5, 0, 0.5], arrow="end"),
        ],
    )
    q = PracticeQuestion(
        order_index=1,
        qtype="单选",
        stem="场线",
        options=["A"],
        answer_outline="",
        figure_kind="field_lines",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_probability_tree_png():
    spec = PracticeProbabilityTreeSpec(
        nodes=[
            PracticeProbabilityTreeNode(id="r", text="开始", parent_id="", edge_label=""),
            PracticeProbabilityTreeNode(id="a", text="A", parent_id="r", edge_label="0.5"),
            PracticeProbabilityTreeNode(id="b", text="B", parent_id="r", edge_label="0.5"),
        ],
    )
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="树",
        options=[],
        answer_outline="",
        figure_kind="probability_tree",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_pedigree_png():
    spec = PracticePedigreeSpec(
        individuals=[
            PracticePedigreeIndividual(id="p1", generation=0, sex="male"),
            PracticePedigreeIndividual(id="p2", generation=0, sex="female"),
            PracticePedigreeIndividual(id="c1", generation=1, sex="male", affected=True),
        ],
        marriages=[PracticePedigreeMarriage(left="p1", right="p2")],
        descents=[PracticePedigreeDescent(mother="p2", father="p1", child="c1")],
    )
    q = PracticeQuestion(
        order_index=1,
        qtype="简答",
        stem="系谱",
        options=[],
        answer_outline="",
        figure_kind="pedigree",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_energy_profile_png():
    spec = PracticeEnergyProfileSpec(
        x=[0.0, 0.3, 0.7, 1.0],
        y=[0.0, 2.0, 0.5, 0.2],
        barrier_i=1,
        barrier_j=2,
        barrier_label="Ea",
    )
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="能垒",
        options=[],
        answer_outline="",
        figure_kind="energy_profile",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_electrochemical_cell_png():
    spec = PracticeElectrochemicalCellSpec(
        left_label="Zn",
        right_label="Cu",
        electrolyte_label="CuSO4",
        mode="galvanic",
    )
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="电池",
        options=[],
        answer_outline="",
        figure_kind="electrochemical_cell",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_unit_circle_trig_png():
    spec = PracticeUnitCircleTrigSpec(angle_deg=60, show_sin=True, show_cos=True, show_tan=False)
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="单位圆",
        options=[],
        answer_outline="",
        figure_kind="unit_circle_trig",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_optics_ray_png():
    spec = PracticeOpticsRaySpec(
        interface_y=0.0,
        medium_top_label="空气",
        medium_bottom_label="水",
        rays=[
            PracticeOpticsRaySegment(x0=-1, y0=0.5, x1=0, y1=0, label="入射"),
            PracticeOpticsRaySegment(x0=0, y0=0, x1=1, y1=-0.4, label="折射"),
        ],
    )
    q = PracticeQuestion(
        order_index=1,
        qtype="填空",
        stem="光路",
        options=[],
        answer_outline="",
        figure_kind="optics_ray",
        figure_spec=spec,
    )
    _assert_png(render_question_figure_to_png_bytes(q))


def test_composite_field_lines_and_unit_circle_png():
    comp = PracticeCompositeSpec(
        ncols=2,
        panels=[
            PracticeCompositePanelFieldLines(
                subtitle="场",
                spec=PracticeFieldLinesSpec(
                    lines=[PracticeFieldLine(x=[0, 1, 2], y=[0, 0.3, 0])],
                ),
            ),
            PracticeCompositePanelUnitCircleTrig(
                subtitle="圆",
                spec=PracticeUnitCircleTrigSpec(angle_deg=30),
            ),
        ],
    )
    b = render_composite_to_png_bytes(comp)
    _assert_png(b)


def test_pdf_embeds_phase10_kinds(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体")

    ps = PracticeSet(
        knowledge_point_key="p10_mix",
        knowledge_point_name="Phase10",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="题1",
                options=[],
                answer_outline="",
                figure_kind="field_lines",
                figure_spec=PracticeFieldLinesSpec(
                    lines=[PracticeFieldLine(x=[0.0, 1.0], y=[0.0, 0.5])],
                ),
            ),
            PracticeQuestion(
                order_index=2,
                qtype="填空",
                stem="题2",
                options=[],
                answer_outline="",
                figure_kind="probability_tree",
                figure_spec=PracticeProbabilityTreeSpec(
                    nodes=[
                        PracticeProbabilityTreeNode(id="r", text="Ω", parent_id=""),
                        PracticeProbabilityTreeNode(id="l", text="尾", parent_id="r", edge_label="1/2"),
                    ],
                ),
            ),
        ],
    )
    out = tmp_path / "p10.pdf"
    render_practice_pdf(ps, out, title="P10", include_answers=False)
    assert out.is_file() and out.stat().st_size >= _MIN_PDF
    doc = fitz.open(out.as_posix())
    try:
        assert doc.page_count >= 1
    finally:
        doc.close()

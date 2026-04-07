"""Phase 9 轻量黄金样张：PNG/PDF 存在、大小与页数；不做像素对比。"""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.models.schemas import (
    PracticeCompositePanelPlot,
    PracticeCompositeSpec,
    PracticeGeometryPolygon,
    PracticeGeometrySpec,
    PracticePlotSeries,
    PracticePlotSpec,
    PracticePoint2D,
    PracticeQuestion,
    PracticeSet,
)
from app.services.fonts import resolve_kaiti_font
from app.services.pdf_render import render_practice_pdf
from app.services.practice_figure_render import (
    render_geometry_to_png_bytes,
    render_plot_to_png_bytes,
    render_question_figure_to_png_bytes,
)


def _min_pdf_bytes() -> int:
    return 1200


def _min_png_bytes() -> int:
    return 450


@pytest.fixture
def practice_set_plot_only() -> PracticeSet:
    spec = PracticePlotSpec(
        series=[PracticePlotSeries(label="L", x=[0.0, 1.0, 2.0], y=[1.0, 0.0, 1.0])],
    )
    return PracticeSet(
        knowledge_point_key="p9_plot",
        knowledge_point_name="Phase9 plot",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="看图",
                options=[],
                answer_outline="",
                figure_kind="plot",
                figure_spec=spec,
            ),
        ],
    )


@pytest.fixture
def practice_set_geometry_only() -> PracticeSet:
    spec = PracticeGeometrySpec(
        points=[
            PracticePoint2D(id="A", x=0, y=0),
            PracticePoint2D(id="B", x=2, y=0),
            PracticePoint2D(id="C", x=1, y=1.5),
        ],
        polygons=[
            PracticeGeometryPolygon(vertex_ids=["A", "B", "C"], fill=True, alpha=0.4),
        ],
    )
    return PracticeSet(
        knowledge_point_key="p9_geom",
        knowledge_point_name="Phase9 geometry",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="三角形",
                options=[],
                answer_outline="",
                figure_kind="geometry",
                figure_spec=spec,
            ),
        ],
    )


@pytest.fixture
def practice_set_composite_two_plots() -> PracticeSet:
    spec = PracticeCompositeSpec(
        title="两格",
        ncols=2,
        panels=[
            PracticeCompositePanelPlot(
                subtitle="甲",
                spec=PracticePlotSpec(
                    series=[PracticePlotSeries(x=[0.0, 1.0], y=[0.0, 1.0])],
                    show_legend=False,
                ),
            ),
            PracticeCompositePanelPlot(
                subtitle="乙",
                spec=PracticePlotSpec(
                    series=[PracticePlotSeries(x=[0.0, 1.0], y=[1.0, 0.0])],
                    show_legend=False,
                ),
            ),
        ],
    )
    return PracticeSet(
        knowledge_point_key="p9_comp",
        knowledge_point_name="Phase9 composite",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="组合",
                options=[],
                answer_outline="",
                figure_kind="composite",
                figure_spec=spec,
            ),
        ],
    )


def test_golden_png_plot_and_geometry(
    practice_set_plot_only: PracticeSet,
    practice_set_geometry_only: PracticeSet,
):
    q_plot = practice_set_plot_only.questions[0]
    q_geom = practice_set_geometry_only.questions[0]
    b1 = render_question_figure_to_png_bytes(q_plot)
    b2 = render_question_figure_to_png_bytes(q_geom)
    assert b1 is not None and b1[:8] == b"\x89PNG\r\n\x1a\n"
    assert b2 is not None and b2[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(b1) >= _min_png_bytes()
    assert len(b2) >= _min_png_bytes()


def test_golden_pdf_plot_geometry_composite(
    tmp_path: Path,
    practice_set_plot_only: PracticeSet,
    practice_set_geometry_only: PracticeSet,
    practice_set_composite_two_plots: PracticeSet,
):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 黄金样张（部署时请配置 KAITI_FONT_PATH）")

    sets = (
        ("plot.pdf", practice_set_plot_only),
        ("geom.pdf", practice_set_geometry_only),
        ("comp.pdf", practice_set_composite_two_plots),
    )
    for name, ps in sets:
        out = tmp_path / name
        render_practice_pdf(ps, out, title="Phase9", include_answers=False)
        assert out.is_file()
        assert out.stat().st_size >= _min_pdf_bytes()
        doc = fitz.open(out.as_posix())
        try:
            assert doc.page_count >= 1
        finally:
            doc.close()


def test_golden_direct_render_functions_smoke():
    p = render_plot_to_png_bytes(
        PracticePlotSpec(series=[PracticePlotSeries(x=[0.0, 1.0], y=[0.0, 1.0])]),
    )
    g = render_geometry_to_png_bytes(
        PracticeGeometrySpec(points=[PracticePoint2D(id="P", x=0, y=0)]),
    )
    assert p is not None and len(p) >= _min_png_bytes()
    assert g is not None and len(g) >= _min_png_bytes()

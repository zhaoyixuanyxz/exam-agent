from __future__ import annotations

import logging

from app.models.schemas import (
    PracticeCompositePanelPlot,
    PracticeCompositeSpec,
    PracticeForceDiagramSpec,
    PracticeGeometryLabel,
    PracticeGeometrySpec,
    PracticeGroupedBarSeries,
    PracticeGroupedBarSpec,
    PracticePieSpec,
    PracticePlotSeries,
    PracticePlotSpec,
    PracticeQuestion,
    PracticeSet,
    PracticeSvgSpec,
    PracticeTableSpec,
)
from app.services.practice_clamp import clamp_practice_set


def test_clamp_pie_too_many_slices_clears_figure():
    labels = [f"L{i}" for i in range(20)]
    values = [1.0] * 20
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="题干",
                options=[],
                answer_outline="略",
                figure_kind="pie",
                figure_spec=PracticePieSpec(labels=labels, values=values),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "none"
    assert ps.questions[0].figure_spec is None


def test_clamp_logs_downgrade(caplog):
    caplog.set_level(logging.INFO)
    labels = [f"L{i}" for i in range(20)]
    values = [1.0] * 20
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="题干",
                options=[],
                answer_outline="略",
                figure_kind="pie",
                figure_spec=PracticePieSpec(labels=labels, values=values),
            )
        ],
    )
    clamp_practice_set(ps)
    assert "figure_kind cleared" in caplog.text


def test_clamp_grouped_bar_ok():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="s",
                options=[],
                answer_outline="a",
                figure_kind="grouped_bar",
                figure_spec=PracticeGroupedBarSpec(
                    categories=["a", "b"],
                    series=[
                        PracticeGroupedBarSeries(label="s1", values=[1.0, 2.0]),
                        PracticeGroupedBarSeries(label="s2", values=[3.0, 4.0]),
                    ],
                ),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "grouped_bar"


def test_clamp_plot_sparse_under_smooth_context_stripped():
    """题干像连续函数图但 plot 点数过少 → 整题去图。"""
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="单选",
                stem="已知二次函数 $y=ax^2+bx+c$ 的图象如图所示。",
                options=["A", "B"],
                answer_outline="略",
                figure_kind="plot",
                figure_spec=PracticePlotSpec(
                    series=[PracticePlotSeries(label="y", x=[0.0, 1.0, 2.0], y=[0.0, 1.0, 0.0])]
                ),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "none"
    assert ps.questions[0].figure_spec is None


def test_clamp_plot_sparse_ok_when_not_smooth_context():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="根据表格数据画折线。",
                options=[],
                answer_outline="略",
                figure_kind="plot",
                figure_spec=PracticePlotSpec(
                    series=[PracticePlotSeries(label="s", x=[0.0, 1.0, 2.0], y=[1.0, 2.0, 3.0])]
                ),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "plot"


def test_clamp_include_figures_false_strips_all():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="s",
                options=[],
                answer_outline="a",
                figure_kind="plot",
                figure_spec=PracticePlotSpec(
                    series=[PracticePlotSeries(label="L", x=[0.0, 1.0], y=[1.0, 2.0])]
                ),
                use_paper_figure=True,
                paper_image_ref="uploads/x.png",
            )
        ],
    )
    clamp_practice_set(ps, include_figures=False)
    assert ps.questions[0].figure_kind == "none"
    assert ps.questions[0].use_paper_figure is False
    assert ps.questions[0].paper_image_ref is None


def test_clamp_composite_keeps_panels():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="题干无光滑曲线关键词",
                options=[],
                answer_outline="略",
                figure_kind="composite",
                figure_spec=PracticeCompositeSpec(
                    ncols=2,
                    panels=[
                        PracticeCompositePanelPlot(
                            spec=PracticePlotSpec(
                                series=[
                                    PracticePlotSeries(label="l", x=[0.0, 1.0, 2.0], y=[0.0, 1.0, 0.0])
                                ],
                                show_legend=False,
                            )
                        ),
                    ],
                ),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "composite"
    assert len(ps.questions[0].figure_spec.panels) == 1


def test_clamp_table_ok():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="s",
                options=[],
                answer_outline="a",
                figure_kind="table",
                figure_spec=PracticeTableSpec(
                    headers=["h1", "h2"],
                    rows=[["a", "b"], ["1", "2"]],
                ),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "table"


def test_clamp_force_diagram_empty_forces_cleared():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="s",
                options=[],
                answer_outline="a",
                figure_kind="force_diagram",
                figure_spec=PracticeForceDiagramSpec(forces=[]),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "none"


def test_clamp_geometry_labels_only_keeps_figure():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="标注说明。",
                options=[],
                answer_outline="略",
                figure_kind="geometry",
                figure_spec=PracticeGeometrySpec(
                    labels=[PracticeGeometryLabel(text="说明文字", x=0.5, y=0.5)],
                ),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "geometry"
    assert ps.questions[0].figure_spec is not None


def test_clamp_svg_with_script_clears_figure():
    ps = PracticeSet(
        knowledge_point_key="k",
        knowledge_point_name="n",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="题干",
                options=[],
                answer_outline="略",
                figure_kind="svg",
                figure_spec=PracticeSvgSpec(
                    svg=(
                        '<svg xmlns="http://www.w3.org/2000/svg">'
                        "<script>alert(1)</script>"
                        '<rect width="10" height="10"/></svg>'
                    ),
                ),
            )
        ],
    )
    clamp_practice_set(ps)
    assert ps.questions[0].figure_kind == "none"
    assert ps.questions[0].figure_spec is None

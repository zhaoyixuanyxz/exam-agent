from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pytest

from app.models.schemas import (
    PracticeBarSpec,
    PracticeCompositePanelPlot,
    PracticeCompositeSpec,
    PracticeFlowchartEdge,
    PracticeFlowchartNode,
    PracticeFlowchartSpec,
    PracticeGeometrySpec,
    PracticePieSpec,
    PracticePlotSeries,
    PracticePlotSpec,
    PracticePoint2D,
    PracticeQuestion,
    PracticeSegment,
    PracticeSet,
    PracticeSvgSpec,
)
from app.services.fonts import resolve_kaiti_font
from app.services.pdf_render import (
    _flatten_math_to_text,
    _stem_strip_trailing_inline_options,
    _strip_all_option_label_prefixes,
    _strip_duplicate_option_label,
    render_answer_pdf,
    render_practice_pdf,
)


def test_strip_duplicate_option_label():
    assert _strip_duplicate_option_label("A. 选项一", 0) == "选项一"
    assert _strip_duplicate_option_label("B、选项二", 1) == "选项二"
    assert _strip_duplicate_option_label("仅正文无标记", 0) == "仅正文无标记"


def test_strip_all_option_label_prefixes_double_a():
    assert _strip_all_option_label_prefixes("A. A. AB = DE", 0) == "AB = DE"


def test_flatten_math_cong_symbol():
    t = _flatten_math_to_text(r"$\triangle ABC \cong \triangle DEF$")
    assert "≅" in t
    assert "cong" not in t.lower()


def test_flatten_math_wrong_degree_wedge_circ():
    t = _flatten_math_to_text(r"$\angle$ ACB = $90^{\wedge}\circ$，$\angle$ A = $30^{\wedge}\circ$")
    assert "°" in t
    assert "wedge" not in t.lower()
    assert "circ" not in t.lower()


def test_flatten_math_broken_frac_sqrt_option():
    t = _flatten_math_to_text(r"B. frac $\sqrt{}$ 22")
    assert "√2/2" in t.replace(" ", "")
    assert "frac" not in t.lower()


def test_stem_strip_trailing_inline_options():
    stem = "如图，已知条件？\nA. 甲\nB. 乙\nC. 丙\nD. 丁"
    opts = ["甲", "乙", "丙", "丁"]
    assert _stem_strip_trailing_inline_options(stem, opts) == "如图，已知条件？"
    opts2 = ["A. 甲", "B. 乙", "C. 丙", "D. 丁"]
    assert _stem_strip_trailing_inline_options(stem, opts2) == "如图，已知条件？"


def test_render_practice_pdf_minimal(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem=r"若 $x^2=4$，则 $x=\pm 2$。",
                options=[],
                answer_outline="开平方即得。",
            )
        ],
    )
    out = tmp_path / "out.pdf"
    render_practice_pdf(ps, out, title="测试卷", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 500


def test_render_practice_pdf_with_svg_figure(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
        '<circle cx="40" cy="40" r="28" fill="#4477cc"/>'
        "</svg>"
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="观察矢量图。",
                options=[],
                answer_outline="略。",
                figure_kind="svg",
                figure_spec=PracticeSvgSpec(svg=svg, caption="示意图"),
            )
        ],
    )
    out = tmp_path / "svg.pdf"
    render_practice_pdf(ps, out, title="SVG 测试", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 500


def test_render_practice_pdf_with_plot_figure(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    spec = PracticePlotSpec(
        title="演示图",
        caption="图注一行",
        series=[PracticePlotSeries(label="y", x=[0, 1, 2], y=[0, 1, 4])],
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="观察折线图，$y$ 在 $x=2$ 处的值约为多少？",
                options=[],
                answer_outline="读图得 $y=4$。",
                figure_kind="plot",
                figure_spec=spec,
            )
        ],
    )
    out = tmp_path / "with_fig.pdf"
    render_practice_pdf(ps, out, title="测试卷含图", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 2000

    ans = tmp_path / "answers.pdf"
    render_answer_pdf(ps, ans, title="测试卷含图")
    assert ans.is_file()
    assert ans.stat().st_size > 1500


def test_render_practice_pdf_with_bar_figure(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    spec = PracticeBarSpec(
        title="对比",
        caption="图注",
        categories=["A", "B"],
        values=[1.0, 2.0],
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="哪项更高？",
                options=[],
                answer_outline="B 更高。",
                figure_kind="bar",
                figure_spec=spec,
            )
        ],
    )
    out = tmp_path / "bar.pdf"
    render_practice_pdf(ps, out, title="柱状测试", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 2000


def test_render_practice_pdf_with_geometry_figure(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    spec = PracticeGeometrySpec(
        points=[
            PracticePoint2D(id="A", x=0, y=0),
            PracticePoint2D(id="B", x=1, y=0),
        ],
        segments=[PracticeSegment(a="A", b="B")],
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="几何题。",
                options=[],
                answer_outline="略。",
                figure_kind="geometry",
                figure_spec=spec,
            )
        ],
    )
    out = tmp_path / "geo.pdf"
    render_practice_pdf(ps, out, title="几何测试", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 2000


def test_render_practice_pdf_with_flowchart_figure(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    spec = PracticeFlowchartSpec(
        title="流程示意",
        nodes=[
            PracticeFlowchartNode(id="s", text="开始"),
            PracticeFlowchartNode(id="e", text="结束"),
        ],
        edges=[PracticeFlowchartEdge(source="s", target="e")],
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="流程题。",
                options=[],
                answer_outline="略。",
                figure_kind="flowchart",
                figure_spec=spec,
            )
        ],
    )
    out = tmp_path / "flow.pdf"
    render_practice_pdf(ps, out, title="流程图测试", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 2000


def test_render_practice_pdf_with_composite_figure(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    spec = PracticeCompositeSpec(
        title="甲乙图",
        ncols=2,
        panels=[
            PracticeCompositePanelPlot(
                subtitle="甲",
                spec=PracticePlotSpec(
                    series=[PracticePlotSeries(label="a", x=[0.0, 1.0, 2.0], y=[0.0, 1.0, 0.0])],
                    show_legend=False,
                ),
            ),
            PracticeCompositePanelPlot(
                subtitle="乙",
                spec=PracticePlotSpec(
                    series=[PracticePlotSeries(label="b", x=[0.0, 1.0], y=[1.0, 0.0])],
                    show_legend=False,
                ),
            ),
        ],
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="看图作答。",
                options=[],
                answer_outline="略。",
                figure_kind="composite",
                figure_spec=spec,
            )
        ],
    )
    out = tmp_path / "composite.pdf"
    render_practice_pdf(ps, out, title="组合图测试", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 2000


def test_render_practice_pdf_with_force_diagram(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    from app.models.schemas import PracticeForceDiagramSpec, PracticeForceItem

    spec = PracticeForceDiagramSpec(
        forces=[
            PracticeForceItem(x0=0, y0=0, x1=1, y1=0.3, label="F"),
            PracticeForceItem(x0=0, y0=0, x1=-0.4, y1=0.6, label="N"),
        ],
        object_dot=True,
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="受力分析。",
                options=[],
                answer_outline="略。",
                figure_kind="force_diagram",
                figure_spec=spec,
            )
        ],
    )
    out = tmp_path / "force.pdf"
    render_practice_pdf(ps, out, title="受力图测试", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 2000


def test_render_practice_pdf_with_pie_figure(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    spec = PracticePieSpec(labels=["x", "y"], values=[25.0, 75.0])
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="占比较大的是？",
                options=[],
                answer_outline="y。",
                figure_kind="pie",
                figure_spec=spec,
            )
        ],
    )
    out = tmp_path / "pie.pdf"
    render_practice_pdf(ps, out, title="饼图测试", include_answers=False)
    assert out.is_file()
    assert out.stat().st_size > 2000


def test_figure_embed_log_skip_no_include_figures(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    caplog.set_level(logging.INFO)
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="无图",
                options=[],
                answer_outline="",
            )
        ],
    )
    out = tmp_path / "nofig.pdf"
    render_practice_pdf(ps, out, title="测", include_answers=False, include_figures=False)
    assert "practice_figure_embed order_index=1" in caplog.text
    assert "skipped_include_figures_false" in caplog.text


def test_figure_embed_log_skip_no_figure_spec(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    caplog.set_level(logging.INFO)
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=2,
                qtype="填空",
                stem="无图",
                options=[],
                answer_outline="",
            )
        ],
    )
    out = tmp_path / "nofspec.pdf"
    render_practice_pdf(ps, out, title="测", include_answers=True)
    assert "practice_figure_embed order_index=2" in caplog.text
    assert "skipped_no_figure" in caplog.text


def test_figure_embed_inline_svg_sanitize_failed(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    caplog.set_level(logging.INFO)
    bad_svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=3,
                qtype="填空",
                stem="坏 SVG",
                options=[],
                answer_outline="",
                figure_kind="svg",
                figure_spec=PracticeSvgSpec(svg=bad_svg, caption=""),
            )
        ],
    )
    out = tmp_path / "badsvg.pdf"
    render_practice_pdf(ps, out, title="测", include_answers=False)
    assert "practice_figure_embed order_index=3" in caplog.text
    assert "inline_svg_sanitize_failed" in caplog.text
    assert "sanitize_none" in caplog.text


def test_collect_figure_diagnostics(tmp_path: Path):
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
    from app.services.practice_figure_diagnostics import FigureEmbedRecord

    spec = PracticePlotSpec(
        series=[PracticePlotSeries(label="L", x=[0.0, 1.0, 2.0], y=[1.0, 0.0, 1.0])]
    )
    ps = PracticeSet(
        knowledge_point_key="demo",
        knowledge_point_name="演示考点",
        questions=[
            PracticeQuestion(
                order_index=1,
                qtype="填空",
                stem="有图",
                options=[],
                answer_outline="",
                figure_kind="plot",
                figure_spec=spec,
            )
        ],
    )
    sink: list[FigureEmbedRecord] = []
    out = tmp_path / "diag.pdf"
    render_practice_pdf(
        ps,
        out,
        title="测",
        include_answers=False,
        collect_figure_diagnostics=sink,
    )
    assert len(sink) == 1
    assert sink[0].outcome == "embedded_rendered_png"
    assert sink[0].figure_kind == "plot"

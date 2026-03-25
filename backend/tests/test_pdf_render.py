from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pytest

from app.models.schemas import PracticeQuestion, PracticeSet
from app.services.fonts import resolve_kaiti_font
from app.services.pdf_render import (
    _flatten_math_to_text,
    _stem_strip_trailing_inline_options,
    _strip_all_option_label_prefixes,
    _strip_duplicate_option_label,
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

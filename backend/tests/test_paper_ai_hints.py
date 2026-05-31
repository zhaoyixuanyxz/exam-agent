from app.prompts.teacher_style import (
    _answer_outline_template,
    _few_shot_excerpt,
    _is_senior_high,
    _subject_difficulty_hints,
    chunk_size_for_practice_batch,
    difficulty_temperature,
    practice_style_prompt_block,
)
from app.services.paper_ai import _subject_figure_hints, build_practice_system_prompt


def test_subject_figure_hints_math():
    h = _subject_figure_hints("高中数学")
    assert "数学" in h or "number_line" in h or "histogram" in h


def test_subject_figure_hints_generic_when_unknown():
    h = _subject_figure_hints("")
    assert "通用" in h or "table" in h


def test_subject_difficulty_hints_math_easy():
    h = _subject_difficulty_hints("初中数学", "easy", grade_range="初二")
    assert "数学" in h
    assert "思维转换" in h or "基础知识点" in h
    assert "初二" in h


def test_subject_difficulty_hints_chemistry_medium():
    h = _subject_difficulty_hints("化学", "medium")
    assert "化学" in h
    assert "情境" in h or "信息提取" in h or "中档" in h


def test_subject_difficulty_hints_physics_hard():
    h = _subject_difficulty_hints("物理", "hard")
    assert "物理" in h
    assert "浮力" in h or "计算量" in h or "情境" in h


def test_answer_outline_template_has_three_sections():
    t = _answer_outline_template()
    assert "【思路】" in t
    assert "【解答】" in t
    assert "【相关知识点】" in t
    assert "800" in t or "1500" in t


def test_few_shot_excerpt_math_medium():
    ex = _few_shot_excerpt("数学", "medium")
    assert "【思路】" in ex
    assert "圆周角" in ex or "圆内接" in ex


def test_practice_style_prompt_block_combines_all():
    block = practice_style_prompt_block("初中化学", "easy", grade_range="初三")
    assert "【朱老师解析格式】" in block
    assert "【解析示范" in block


def test_difficulty_temperature_defaults():
    assert difficulty_temperature("easy") == 0.15
    assert difficulty_temperature("medium") == 0.25
    assert difficulty_temperature("hard") == 0.30
    assert difficulty_temperature("简单") == 0.15
    assert difficulty_temperature("困难") == 0.30


def test_chunk_size_for_practice_batch():
    assert chunk_size_for_practice_batch(5) is None
    assert chunk_size_for_practice_batch(6) == 3
    assert chunk_size_for_practice_batch(10) == 3
    assert chunk_size_for_practice_batch(15) == 3


def test_build_practice_system_prompt_snapshot_math_hard():
    sys = build_practice_system_prompt(
        knowledge_point_name="二次函数",
        n_use=3,
        subject="初中数学",
        grade_range="初三",
        difficulty="hard",
        qtype_constraint="单选、多选、填空",
        allowed_qtypes=None,
        include_figures=False,
        no_fig_rule="本题集**禁止任何配图**",
        paper_ctx="",
    )
    assert "朱老师" in sys
    assert "【数学·难题" in sys
    assert "【朱老师解析格式】" in sys
    assert "800–1500" in sys
    assert "二次函数" in sys
    assert "禁止任何配图" in sys


def test_build_practice_system_prompt_snapshot_chemistry_easy():
    sys = build_practice_system_prompt(
        knowledge_point_name="化学式",
        n_use=2,
        subject="化学",
        grade_range="初二",
        difficulty="easy",
        qtype_constraint="单选",
        allowed_qtypes=["单选"],
        include_figures=True,
        no_fig_rule="",
        paper_ctx="",
    )
    assert "【化学·简单" in sys
    assert "直接应用" in sys or "基础题" in sys
    assert "figure_kind" in sys


def test_build_practice_system_prompt_snapshot_physics_medium():
    sys = build_practice_system_prompt(
        knowledge_point_name="电功率",
        n_use=4,
        subject="物理",
        grade_range="初三",
        difficulty="medium",
        qtype_constraint="填空、简答",
        allowed_qtypes=["填空", "简答"],
        include_figures=False,
        no_fig_rule="",
        paper_ctx="",
    )
    assert "【物理·中等" in sys
    assert "情境建模" in sys or "信息提取" in sys or "中档" in sys


def test_is_senior_high_detection():
    assert _is_senior_high("高三", "数学") is True
    assert _is_senior_high("高中", "") is True
    assert _is_senior_high("初三", "高中数学") is True
    assert _is_senior_high("初二", "数学") is False


def test_subject_difficulty_hints_highschool_math_hard():
    h = _subject_difficulty_hints("高中数学", "hard", grade_range="高三")
    assert "高中数学·难题" in h or "反套路" in h or "新定义" in h
    assert "高中" in h or "高考" in h


def test_build_practice_system_prompt_snapshot_highschool_math_hard():
    sys = build_practice_system_prompt(
        knowledge_point_name="新定义数列",
        n_use=2,
        subject="高中数学",
        grade_range="高三",
        difficulty="hard",
        qtype_constraint="简答",
        allowed_qtypes=["简答"],
        include_figures=False,
        no_fig_rule="",
        paper_ctx="",
    )
    assert "高中数学·难题" in sys or "反套路" in sys
    assert "高三" in sys or "高中" in sys

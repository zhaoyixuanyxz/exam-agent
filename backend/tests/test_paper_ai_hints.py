from app.services.paper_ai import _subject_figure_hints


def test_subject_figure_hints_math():
    h = _subject_figure_hints("高中数学")
    assert "数学" in h or "number_line" in h or "histogram" in h


def test_subject_figure_hints_generic_when_unknown():
    h = _subject_figure_hints("")
    assert "通用" in h or "table" in h

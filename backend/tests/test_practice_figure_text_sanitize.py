from __future__ import annotations

import pytest

from app.services.practice_figure_text_sanitize import figure_matplotlib_plain_text


@pytest.mark.parametrize(
    "raw,expect_substr",
    [
        (r"水（含少量 $\ce{H2SO4}$）", "H₂SO₄"),
        (r"水（含少量 $\\ce {H2SO4}$）", "H₂SO₄"),
        (r"水（含少量 $\\\\ce {H2SO4}$）", "H₂SO₄"),
        (r"\ce{H2O}", "H₂O"),
        (r"稀 $\mathrm{HNO_3}$ 溶液", "HNO₃"),
        (r"A\xrightarrow{酶}B", "→（酶）"),
    ],
)
def test_figure_matplotlib_plain_text_chemistry(raw: str, expect_substr: str) -> None:
    out = figure_matplotlib_plain_text(raw)
    assert expect_substr in out
    assert "\\ce" not in out
    assert "$" not in out

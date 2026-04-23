from __future__ import annotations

import pytest

from app.services.practice_circuit_display_labels import circuit_node_label_for_display


@pytest.mark.parametrize(
    "nid,expected",
    [
        ("cell_minus", "电源负极"),
        ("cell_plus", "电源正极"),
        ("R1_bot", "R1下"),
        ("R2_top", "R2上"),
        ("V1_bot", "V1下"),
        ("V2_top", "V2上"),
        ("A_bottom", "A下"),
        ("A_top", "A上"),
        ("A1_bottom", "A1下"),
        ("n1", "节点1"),
        ("node_3", "节点3"),
        ("S", "开关"),
        ("已含中文锚点", "已含中文锚点"),
    ],
)
def test_circuit_node_label_for_display(nid: str, expected: str) -> None:
    assert circuit_node_label_for_display(nid) == expected

from __future__ import annotations

import pytest

from app.services.practice_circuit_display_labels import circuit_node_label_for_display


@pytest.mark.parametrize(
    "nid,expected",
    [
        ("cell_minus", "电源负极"),
        ("cell_plus", "电源正极"),
        ("R1_bot", "电阻1（下）"),
        ("R2_top", "电阻2（上）"),
        ("V1_bot", "电压1（下）"),
        ("V2_top", "电压2（上）"),
        ("A_bottom", "电流表（下）"),
        ("A_top", "电流表（上）"),
        ("A1_bottom", "电流表1（下）"),
        ("n1", "节点1"),
        ("node_3", "节点3"),
        ("S", "开关"),
        ("已含中文锚点", "已含中文锚点"),
    ],
)
def test_circuit_node_label_for_display(nid: str, expected: str) -> None:
    assert circuit_node_label_for_display(nid) == expected

"""电路图节点 id（模型常用英文）→ 卷面友好中文短标签，仅影响配图显示，不改 JSON。"""

from __future__ import annotations

import re


def circuit_node_label_for_display(nid: str) -> str:
    """
    将 practice circuit_simple 的 node id 转为简短中文。
    已含汉字的 id 原样返回；无法识别时做轻量替换（_top/_bot 等）后返回。
    """
    s = (nid or "").strip()
    if not s:
        return s
    if re.search(r"[\u4e00-\u9fff]", s):
        return s

    key = s.lower().replace(" ", "")

    exact: dict[str, str] = {
        "cell_minus": "电源负极",
        "cell_plus": "电源正极",
        "battery_minus": "电源负极",
        "battery_plus": "电源正极",
        "b_minus": "负极",
        "b_plus": "正极",
        "gnd": "接地",
        "ground": "接地",
        "neg": "负极",
        "pos": "正极",
    }
    if key in exact:
        return exact[key]

    if key in ("s", "sw", "switch", "k"):
        return "开关"

    # n1、node_3 → 节点1
    m = re.match(r"^n(\d+)$", key)
    if m:
        return f"节点{m.group(1)}"
    m = re.match(r"^node_?(\d+)$", key)
    if m:
        return f"节点{m.group(1)}"

    def _pos_zh(pos: str) -> str:
        return "下" if pos in ("bot", "bottom") else "上"

    # R1_bot、R2_top
    m = re.match(r"^r(\d+)_(bot|bottom|top)$", key)
    if m:
        return f"电阻{m.group(1)}（{_pos_zh(m.group(2))}）"

    # V1_bot（电压表支路节点）
    m = re.match(r"^v(\d+)_(bot|bottom|top)$", key)
    if m:
        return f"电压{m.group(1)}（{_pos_zh(m.group(2))}）"

    # A1_bottom、A2_top
    m = re.match(r"^a(\d+)_(bot|bottom|top)$", key)
    if m:
        return f"电流表{m.group(1)}（{_pos_zh(m.group(2))}）"
    # A_top、A_bottom
    m = re.match(r"^a_(bot|bottom|top)$", key)
    if m:
        return f"电流表（{_pos_zh(m.group(1))}）"

    # 单独 R3、V2
    m = re.match(r"^r(\d+)$", key)
    if m:
        return f"电阻{m.group(1)}"
    m = re.match(r"^v(\d+)$", key)
    if m:
        return f"电压{m.group(1)}"

    # 含 cell_minus 等子串的复合 id
    t = s
    t = re.sub(r"(?i)cell_minus", "负极", t)
    t = re.sub(r"(?i)cell_plus", "正极", t)
    t = re.sub(r"(?i)battery_minus", "负极", t)
    t = re.sub(r"(?i)battery_plus", "正极", t)
    t = re.sub(r"(?i)_bot\b", "·下", t)
    t = re.sub(r"(?i)_bottom\b", "·下", t)
    t = re.sub(r"(?i)_top\b", "·上", t)
    t = re.sub(r"_+", "·", t)
    return t.strip("·") or s

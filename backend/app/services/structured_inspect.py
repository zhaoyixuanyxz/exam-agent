"""结构化结果摘要与异常检测（V2.0 确认中心）。"""

from __future__ import annotations

from typing import Any

from app.models.schemas import StructuredPaper


def build_summary_from_parsed(parsed: dict) -> dict[str, Any] | None:
    """为前端卡片生成轻量摘要；解析失败时返回 None。"""
    try:
        sp = StructuredPaper.model_validate(parsed)
    except Exception:
        return None
    n_sec = len(sp.sections)
    n_q = 0
    by_type: dict[str, int] = {}
    for sec in sp.sections:
        for q in sec.questions:
            n_q += 1
            qt = (q.qtype or "未知").strip() or "未知"
            by_type[qt] = by_type.get(qt, 0) + 1
    return {
        "title": sp.title or "",
        "section_count": n_sec,
        "question_count": n_q,
        "qtype_counts": by_type,
    }


def list_anomalies(parsed: dict | None) -> list[str]:
    """返回可展示的中文提示列表。"""
    if not parsed:
        return []
    try:
        sp = StructuredPaper.model_validate(parsed)
    except Exception as e:
        return [f"结构化数据无法通过校验：{e!s}"]

    out: list[str] = []
    order_seen: set[int] = set()
    dup: list[int] = []
    for sec in sp.sections:
        for q in sec.questions:
            oi = int(q.order_index)
            if oi in order_seen:
                dup.append(oi)
            order_seen.add(oi)
            if not (q.stem or "").strip():
                out.append(f"第 {q.order_index} 题题干为空，请检查。")
    if dup:
        out.insert(0, f"题号 order_index 重复：{sorted(set(dup))}。")
    n_q = _n_q_in_sp(sp)
    if sp.sections and n_q == 0:
        out.append("所有大题下小题为空，请检查结构化结果。")
    return out


def _n_q_in_sp(sp: StructuredPaper) -> int:
    return sum(len(sec.questions) for sec in sp.sections)

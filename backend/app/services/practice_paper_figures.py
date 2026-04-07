"""Map structured exam questions to image paths for practice PDF embedding."""

from __future__ import annotations

from app.models.schemas import StructuredPaper


def collect_order_index_to_image_paths(sp: StructuredPaper) -> dict[int, list[str]]:
    """
    按原卷题号 order_index 收集 blocks 中 image_ref 的路径（可能多图）。
    LLM 结构化若未填 blocks，则返回空字典。
    """
    out: dict[int, list[str]] = {}
    for sec in sp.sections:
        for q in sec.questions:
            paths: list[str] = []
            for b in q.blocks:
                if b.type == "image_ref" and (b.ref or "").strip():
                    paths.append(b.ref.strip())
            if paths:
                out.setdefault(q.order_index, []).extend(paths)
    return out

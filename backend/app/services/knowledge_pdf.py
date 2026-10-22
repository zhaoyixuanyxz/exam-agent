"""Color knowledge-point explanation PDF from an existing analysis."""

from __future__ import annotations

from app.models.schemas import KnowledgeAnalysisResult


def knowledge_pdf_blocks(ka: KnowledgeAnalysisResult, alignment: dict) -> dict:
    g1 = alignment.get("grade_min", "")
    g2 = alignment.get("grade_max", "")
    sub = alignment.get("subject", "")
    title = f"{g1}～{g2} · {sub} · {ka.theme_title}"
    orders_by_key: dict[str, list[int]] = {}
    for mapping in ka.mappings:
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        orders_by_key.setdefault(key, []).append(int(mapping.question_order))
    points = []
    for point in ka.knowledge_points:
        points.append(
            {
                "name": point.name,
                "summary": point.summary,
                "orders": orders_by_key.get(point.key, []),
            }
        )
    return {"title": title, "points": points}

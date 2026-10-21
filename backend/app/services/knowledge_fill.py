"""Fill knowledge-point gaps one question at a time."""

from __future__ import annotations

from app.models.schemas import KnowledgeAnalysisResult, StructuredPaper


def question_orders(paper: StructuredPaper) -> list[int]:
    orders: list[int] = []
    for sec in paper.sections:
        for q in sec.questions:
            orders.append(int(q.order_index))
    return orders


def missing_orders(paper: StructuredPaper, analysis: KnowledgeAnalysisResult) -> list[int]:
    covered: set[int] = set()
    for mapping in analysis.mappings:
        if (mapping.knowledge_point_key or "").strip():
            covered.add(int(mapping.question_order))
    return [order for order in question_orders(paper) if order not in covered]

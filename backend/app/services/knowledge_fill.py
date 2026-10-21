"""Fill knowledge-point gaps one question at a time."""

from __future__ import annotations

from collections.abc import Callable

from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    QuestionKnowledgeMapping,
    StructuredPaper,
)

AskOne = Callable[[int, str], KnowledgeAnalysisResult]


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


def _stem_for(paper: StructuredPaper, order: int) -> str:
    for sec in paper.sections:
        for q in sec.questions:
            if int(q.order_index) == order:
                return q.stem
    return ""


def merge_fill(
    base: KnowledgeAnalysisResult,
    extra: KnowledgeAnalysisResult,
    only_order: int,
) -> KnowledgeAnalysisResult:
    points = list(base.knowledge_points)
    known = {p.key for p in points}
    for point in extra.knowledge_points:
        if point.key not in known and (point.key or "").strip():
            points.append(point)
            known.add(point.key)
    mappings = list(base.mappings)
    for mapping in extra.mappings:
        if int(mapping.question_order) != only_order:
            continue
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        mappings.append(
            QuestionKnowledgeMapping(question_order=only_order, knowledge_point_key=key)
        )
    return base.model_copy(
        update={"knowledge_points": points, "mappings": mappings}
    )


def fill_missing_knowledge(
    paper: StructuredPaper,
    analysis: KnowledgeAnalysisResult,
    ask_one: AskOne,
) -> KnowledgeAnalysisResult:
    while True:
        missing = missing_orders(paper, analysis)
        if not missing:
            return analysis
        order = missing[0]
        extra = ask_one(order, _stem_for(paper, order))
        analysis = merge_fill(analysis, extra, order)

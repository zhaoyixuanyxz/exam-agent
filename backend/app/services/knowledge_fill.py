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

TIMEOUT_MESSAGE = "连接超时建议重试"


class KnowledgeFillTimeout(Exception):
    """The model call timed out while filling one question."""

    def __init__(self, analysis: KnowledgeAnalysisResult):
        self.analysis = analysis
        super().__init__(TIMEOUT_MESSAGE)


def is_connection_timeout(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "timeout" in name or "timed out" in text or "timeout" in text


UNREADABLE_PAGE = "这一页无法识别"


def is_unreadable_page(raw_text: str) -> bool:
    text = (raw_text or "").strip()
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return cjk < 4 and letters < 4


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
        try:
            extra = ask_one(order, _stem_for(paper, order))
        except KnowledgeFillTimeout:
            raise KnowledgeFillTimeout(analysis) from None
        analysis = merge_fill(analysis, extra, order)

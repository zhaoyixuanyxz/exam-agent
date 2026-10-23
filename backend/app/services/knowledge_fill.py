"""Fill knowledge-point gaps one question at a time."""

from __future__ import annotations

from collections.abc import Callable

from app.models.schemas import (
    KnowledgeAnalysisResult,
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


class KnowledgeFillFailed(Exception):
    """A non-timeout failure while filling; keeps points merged so far."""

    def __init__(self, analysis: KnowledgeAnalysisResult, cause: BaseException):
        self.analysis = analysis
        self.cause = cause
        super().__init__(str(cause))


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
    # ask_one is always for one concrete order; remap whatever order the model wrote.
    for mapping in extra.mappings:
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        mappings.append(
            QuestionKnowledgeMapping(question_order=only_order, knowledge_point_key=key)
        )
    if not any(int(m.question_order) == only_order and (m.knowledge_point_key or "").strip() for m in mappings):
        for point in extra.knowledge_points:
            key = (point.key or "").strip()
            if key:
                mappings.append(
                    QuestionKnowledgeMapping(question_order=only_order, knowledge_point_key=key)
                )
                break
    return base.model_copy(
        update={"knowledge_points": points, "mappings": mappings}
    )


def fill_missing_knowledge(
    paper: StructuredPaper,
    analysis: KnowledgeAnalysisResult,
    ask_one: AskOne,
) -> KnowledgeAnalysisResult:
    # The operator required re-asking until a point exists, so there is no attempt cap
    # for empty replies. Wrong question_order from the model is remapped in merge_fill.
    while True:
        missing = missing_orders(paper, analysis)
        if not missing:
            return analysis
        order = missing[0]
        try:
            extra = ask_one(order, _stem_for(paper, order))
        except KnowledgeFillTimeout:
            raise KnowledgeFillTimeout(analysis) from None
        except Exception as exc:
            raise KnowledgeFillFailed(analysis, exc) from exc
        analysis = merge_fill(analysis, extra, order)


def question_point_names(analysis: KnowledgeAnalysisResult) -> list[dict]:
    by_order: dict[int, list[str]] = {}
    names = {point.key: point.name for point in analysis.knowledge_points}
    for mapping in analysis.mappings:
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        name = (names.get(key) or "").strip()
        if not name:
            continue
        by_order.setdefault(int(mapping.question_order), []).append(name)
    return [
        {"order_index": order, "names": by_order[order]}
        for order in sorted(by_order)
    ]

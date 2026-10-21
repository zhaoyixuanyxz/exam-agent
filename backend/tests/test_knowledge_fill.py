from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    PaperSection,
    QuestionItem,
    QuestionKnowledgeMapping,
    StructuredPaper,
)
from app.services.knowledge_fill import missing_orders


def _paper() -> StructuredPaper:
    return StructuredPaper(
        title="t",
        sections=[
            PaperSection(
                title="一",
                questions=[
                    QuestionItem(order_index=1, qtype="选择", stem="第一题"),
                    QuestionItem(order_index=2, qtype="填空", stem="第二题"),
                ],
            )
        ],
    )


def test_missing_orders_skips_questions_that_already_have_a_point():
    paper = _paper()
    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[
            KnowledgePointItem(key="kp_a", name="考点甲", summary="甲"),
        ],
        mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a")],
    )
    assert missing_orders(paper, analysis) == [2]


def test_fill_retries_only_the_empty_question_until_it_has_a_point():
    from app.services.knowledge_fill import fill_missing_knowledge

    paper = _paper()
    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[KnowledgePointItem(key="kp_a", name="考点甲", summary="甲")],
        mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a")],
    )
    calls: list[int] = []

    def ask_one(order: int, stem: str):
        calls.append(order)
        if len(calls) < 2:
            return KnowledgeAnalysisResult(theme_title="主题", knowledge_points=[], mappings=[])
        return KnowledgeAnalysisResult(
            theme_title="主题",
            knowledge_points=[KnowledgePointItem(key="kp_b", name="考点乙", summary="乙")],
            mappings=[QuestionKnowledgeMapping(question_order=order, knowledge_point_key="kp_b")],
        )

    filled = fill_missing_knowledge(paper, analysis, ask_one)
    assert calls == [2, 2]
    keys = [m.knowledge_point_key for m in filled.mappings if m.question_order == 1]
    assert keys == ["kp_a"]
    keys2 = [m.knowledge_point_key for m in filled.mappings if m.question_order == 2]
    assert keys2 == ["kp_b"]

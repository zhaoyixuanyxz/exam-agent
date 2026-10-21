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

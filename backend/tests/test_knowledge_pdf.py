from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    QuestionKnowledgeMapping,
)
from app.services.knowledge_pdf import knowledge_pdf_blocks


def _ka() -> KnowledgeAnalysisResult:
    return KnowledgeAnalysisResult(
        theme_title="二次函数综合",
        knowledge_points=[
            KnowledgePointItem(key="kp_a", name="顶点式", summary="配方法求顶点", book_chapter_hint="九下"),
            KnowledgePointItem(key="kp_b", name="图像性质", summary="开口与对称轴", book_chapter_hint="九下"),
        ],
        mappings=[
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a"),
            QuestionKnowledgeMapping(question_order=2, knowledge_point_key="kp_a"),
            QuestionKnowledgeMapping(question_order=3, knowledge_point_key="kp_b"),
        ],
    )


def test_knowledge_pdf_blocks_groups_questions_under_each_point():
    blocks = knowledge_pdf_blocks(_ka(), {"grade_min": "初三", "grade_max": "初三", "subject": "数学"})
    assert blocks["title"] == "初三～初三 · 数学 · 二次函数综合"
    assert [b["name"] for b in blocks["points"]] == ["顶点式", "图像性质"]
    assert blocks["points"][0]["summary"] == "配方法求顶点"
    assert blocks["points"][0]["orders"] == [1, 2]
    assert blocks["points"][1]["orders"] == [3]

from __future__ import annotations

from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    QuestionKnowledgeMapping,
)
from app.services.export_markdown import build_knowledge_markdown


def test_build_knowledge_markdown():
    ka = KnowledgeAnalysisResult(
        theme_title="二次函数综合",
        knowledge_points=[
            KnowledgePointItem(
                key="quadratic_vertex",
                name="顶点式",
                summary="配方法求顶点坐标",
                book_chapter_hint="九年级·二次函数",
            )
        ],
        mappings=[
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="quadratic_vertex")
        ],
    )
    align = {"grade_min": "初三", "grade_max": "初三", "subject": "数学"}
    md = build_knowledge_markdown(ka, align)
    assert "初三" in md
    assert "数学" in md
    assert "顶点式" in md
    assert "考点一览" in md
    assert "第 1 题" in md
    assert "二次函数综合" in md

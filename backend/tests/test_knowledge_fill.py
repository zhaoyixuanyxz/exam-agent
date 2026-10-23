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


def test_merge_fill_remaps_model_question_order_onto_asked_order():
    """Models often number the lone item as 1; that must still cover the asked order."""
    from app.services.knowledge_fill import fill_missing_knowledge, merge_fill

    base = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[KnowledgePointItem(key="kp_a", name="考点甲", summary="甲")],
        mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a")],
    )
    extra = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[KnowledgePointItem(key="kp_b", name="考点乙", summary="乙")],
        mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_b")],
    )
    merged = merge_fill(base, extra, only_order=2)
    assert missing_orders(_paper(), merged) == []
    assert [m.question_order for m in merged.mappings if m.knowledge_point_key == "kp_b"] == [2]

    paper = _paper()
    calls: list[int] = []

    def ask_one(order: int, stem: str):
        calls.append(order)
        return KnowledgeAnalysisResult(
            theme_title="主题",
            knowledge_points=[KnowledgePointItem(key="kp_b", name="考点乙", summary="乙")],
            mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_b")],
        )

    filled = fill_missing_knowledge(paper, base, ask_one)
    assert calls == [2]
    assert missing_orders(paper, filled) == []


def test_fill_non_timeout_error_keeps_points_already_merged():
    from app.services.knowledge_fill import KnowledgeFillFailed, fill_missing_knowledge

    paper = _paper()
    analysis = KnowledgeAnalysisResult(theme_title="主题", knowledge_points=[], mappings=[])
    calls: list[int] = []

    def ask_one(order: int, stem: str):
        calls.append(order)
        if order == 1:
            return KnowledgeAnalysisResult(
                theme_title="主题",
                knowledge_points=[KnowledgePointItem(key="kp_a", name="考点甲", summary="甲")],
                mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a")],
            )
        raise RuntimeError("model boom")

    try:
        fill_missing_knowledge(paper, analysis, ask_one)
        raised = False
    except KnowledgeFillFailed as exc:
        raised = True
        assert [m.knowledge_point_key for m in exc.analysis.mappings] == ["kp_a"]
    assert raised is True
    assert calls == [1, 2]


def test_unreadable_page_is_detected_without_inventing_questions():
    from app.services.knowledge_fill import UNREADABLE_PAGE, is_unreadable_page

    assert is_unreadable_page("   \n  ") is True
    assert is_unreadable_page("???") is True
    assert is_unreadable_page("1. 已知三角形ABC，求角A。") is False
    assert UNREADABLE_PAGE == "这一页无法识别"


def test_timeout_stops_without_a_fake_point_and_uses_the_fixed_sentence():
    from app.services.knowledge_fill import TIMEOUT_MESSAGE, KnowledgeFillTimeout, fill_missing_knowledge
    from app.services.llm_errors import tool_error_user_text

    paper = _paper()
    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[],
        mappings=[],
    )
    bogus = KnowledgeAnalysisResult(
        theme_title="假",
        knowledge_points=[
            KnowledgePointItem(key="bogus_key", name="假考点", summary="假"),
        ],
        mappings=[
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="bogus_key"),
        ],
    )

    def ask_one(order: int, stem: str):
        raise KnowledgeFillTimeout(bogus)

    try:
        fill_missing_knowledge(paper, analysis, ask_one)
        raised = False
    except KnowledgeFillTimeout as exc:
        raised = True
        assert exc.analysis == analysis
        assert "bogus_key" not in {m.knowledge_point_key for m in exc.analysis.mappings}
        assert "bogus_key" not in {point.key for point in exc.analysis.knowledge_points}
    assert raised is True
    assert tool_error_user_text("", KnowledgeFillTimeout(analysis)) == TIMEOUT_MESSAGE
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE


def test_is_connection_timeout_matches_timeout_errors_only():
    from app.services.knowledge_fill import is_connection_timeout

    assert is_connection_timeout(TimeoutError()) is True
    assert is_connection_timeout(ValueError("nope")) is False


def test_question_point_names_lists_every_name_on_that_question():
    from app.services.knowledge_fill import question_point_names

    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[
            KnowledgePointItem(key="kp_a", name="考点甲", summary="甲"),
            KnowledgePointItem(key="kp_b", name="考点乙", summary="乙"),
        ],
        mappings=[
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a"),
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_b"),
        ],
    )
    assert question_point_names(analysis) == [
        {"order_index": 1, "names": ["考点甲", "考点乙"]},
    ]


def test_question_point_names_skips_a_key_with_no_chinese_name():
    from app.services.knowledge_fill import question_point_names

    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[
            KnowledgePointItem(key="kp_a", name="考点甲", summary="甲"),
        ],
        mappings=[
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a"),
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_raw_english"),
            QuestionKnowledgeMapping(question_order=2, knowledge_point_key="kp_raw_english"),
        ],
    )
    assert question_point_names(analysis) == [
        {"order_index": 1, "names": ["考点甲"]},
    ]
    rendered = str(question_point_names(analysis))
    assert "kp_raw_english" not in rendered


def test_structure_exam_paper_unreadable_guard_does_not_structure():
    from unittest.mock import MagicMock, patch

    from app.agent.tools import structure_exam_paper

    paper = MagicMock()
    paper.raw_text = "???"
    mock_session = MagicMock()
    mock_session.get.return_value = paper

    class _CM:
        def __enter__(self):
            return mock_session

        def __exit__(self, *args):
            return None

    with (
        patch("app.agent.tools.sync_session", return_value=_CM()),
        patch("app.agent.tools.structure_paper_text") as structure,
    ):
        out = structure_exam_paper.invoke({"paper_id": "p1"})
    assert out == "这一页无法识别"
    structure.assert_not_called()

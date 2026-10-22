from pathlib import Path

import pymupdf

from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    QuestionKnowledgeMapping,
)
from app.services.knowledge_pdf import BLOCK_FILLS, knowledge_pdf_blocks, render_knowledge_pdf


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


def _fill_in_palette(fill) -> bool:
    if not fill:
        return False
    channels = fill[:3]
    if max(channels) <= 1:
        return any(
            all(abs(channel - expected / 255) <= 0.02 for channel, expected in zip(channels, rgb))
            for rgb in BLOCK_FILLS
        )
    rounded = tuple(round(channel) for channel in channels)
    return rounded in BLOCK_FILLS


def test_render_knowledge_pdf_has_title_blocks_and_color(tmp_path: Path):
    out = tmp_path / "考点说明.pdf"
    payload = knowledge_pdf_blocks(
        _ka(),
        {"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
    )
    render_knowledge_pdf(payload, out)
    raw = out.read_bytes()
    assert raw.startswith(b"%PDF-")
    doc = pymupdf.open(out)
    text = "".join(page.get_text() for page in doc)
    drawings = [d for page in doc for d in page.get_drawings()]
    doc.close()
    assert "初三" in text
    assert "数学" in text
    assert "二次函数综合" in text
    assert "顶点式" in text
    assert "图像性质" in text
    assert "第 1 题" in text
    assert "顶点式" in text and "图像性质" in text
    assert any(_fill_in_palette(drawing.get("fill")) for drawing in drawings)


def test_store_skips_existing_and_timeout_keeps_it():
    from app.services.knowledge_pdf import TIMEOUT_MESSAGE, KnowledgePdfTimeout, store_knowledge_pdf
    from app.services.llm_errors import tool_error_user_text

    calls = {"n": 0}

    def write_pdf():
        calls["n"] += 1
        raise KnowledgePdfTimeout(stored=True)

    out = store_knowledge_pdf(already_stored=True, write_pdf=write_pdf)
    assert out == "skip"
    assert calls["n"] == 0

    try:
        store_knowledge_pdf(already_stored=False, write_pdf=write_pdf)
        raised = False
    except KnowledgePdfTimeout as exc:
        raised = True
        assert exc.stored is False
    assert raised is True
    assert tool_error_user_text("", KnowledgePdfTimeout(stored=False)) == TIMEOUT_MESSAGE
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE

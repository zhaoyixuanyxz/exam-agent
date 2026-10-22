from pathlib import Path
from unittest.mock import patch

import pymupdf
import pytest
from sqlalchemy import select

from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    QuestionKnowledgeMapping,
)
from app.services.fonts import resolve_kaiti_font
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
    try:
        resolve_kaiti_font()
    except FileNotFoundError:
        pytest.skip("本机未找到楷体，跳过 PDF 渲染测试（部署时请配置 KAITI_FONT_PATH）")
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


def test_artifact_category_for_knowledge_pdf_is_the_explanation_slot():
    from app.api.chat import _artifact_ui_category

    assert _artifact_ui_category("knowledge_pdf") == "knowledge_markdown"
    assert _artifact_ui_category("markdown") == "knowledge_markdown"


def test_list_artifacts_sync_prefers_knowledge_pdf_over_markdown(tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.api.chat import _list_artifacts_sync
    from app.db.models import Artifact, ExamPaper
    from app.db.sync_session import sync_session
    from app.main import app

    md = tmp_path / "考点说明.md"
    md.write_text("# 考点\n", encoding="utf-8")
    pdf = tmp_path / "考点说明.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        with sync_session() as s:
            p = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_markdown_path=md.as_posix(),
            )
            s.add(p)
            s.commit()
            s.add(
                Artifact(
                    paper_id=p.id,
                    kind="knowledge_pdf",
                    display_name="考点说明",
                    path=pdf.as_posix(),
                    source_tool="run_knowledge_analysis",
                )
            )
            s.commit()

        items = _list_artifacts_sync(cid)

    slot = [i for i in items if i["category"] == "knowledge_markdown"]
    assert len(slot) == 1
    assert slot[0]["path"].endswith(".pdf")
    assert slot[0]["kind"] == "knowledge_pdf"
    assert not any(
        i["category"] == "knowledge_markdown" and str(i["path"]).endswith(".md")
        for i in items
    )


def _parsed_and_alignment():
    parsed = {
        "title": "测",
        "sections": [
            {
                "title": "第一大题",
                "questions": [
                    {
                        "order_index": 1,
                        "qtype": "填空",
                        "stem": "题1",
                        "options": [],
                        "blocks": [],
                    }
                ],
            }
        ],
    }
    alignment = {"grade_min": "初三", "grade_max": "初三", "subject": "数学"}
    return parsed, alignment


def _write_fake_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")


def test_list_artifacts_sync_markdown_when_no_knowledge_pdf(tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.api.chat import _list_artifacts_sync
    from app.db.models import ExamPaper
    from app.db.sync_session import sync_session
    from app.main import app

    md = tmp_path / "考点说明.md"
    md.write_text("# 考点\n", encoding="utf-8")

    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        with sync_session() as s:
            p = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_markdown_path=md.as_posix(),
            )
            s.add(p)
            s.commit()

        items = _list_artifacts_sync(cid)

    slot = [i for i in items if i["category"] == "knowledge_markdown"]
    assert len(slot) == 1
    assert slot[0]["kind"] == "markdown"
    assert slot[0]["path"].endswith(".md")


def test_run_knowledge_analysis_skips_pdf_when_row_and_file_exist(tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.agent.tools import run_knowledge_analysis
    from app.db.models import Artifact, ExamPaper
    from app.db.sync_session import sync_session
    from app.main import app

    existing = tmp_path / "existing.pdf"
    _write_fake_pdf(existing)
    parsed, alignment = _parsed_and_alignment()

    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        with sync_session() as s:
            p = ExamPaper(
                conversation_id=cid,
                source_type="test",
                structured_confirm_status="confirmed",
                structured_version=1,
                parsed_json=parsed,
                alignment_json=alignment,
            )
            s.add(p)
            s.commit()
            pid = p.id
            s.add(
                Artifact(
                    paper_id=pid,
                    kind="knowledge_pdf",
                    display_name="考点说明",
                    path=existing.as_posix(),
                    source_tool="run_knowledge_analysis",
                )
            )
            s.commit()

        with (
            patch("app.agent.tools.analyze_knowledge", return_value=_ka()),
            patch("app.agent.tools.render_knowledge_pdf") as render_mock,
        ):
            out = run_knowledge_analysis.invoke({"paper_id": pid})

    assert "成功" in out
    render_mock.assert_not_called()
    with sync_session() as s:
        rows = list(
            s.execute(
                select(Artifact).where(
                    Artifact.paper_id == pid, Artifact.kind == "knowledge_pdf"
                )
            ).scalars()
        )
        paper = s.get(ExamPaper, pid)
    assert len(rows) == 1
    assert Path(rows[0].path).is_file()
    assert rows[0].path == existing.as_posix()
    assert paper is not None
    assert paper.knowledge_markdown_path
    assert Path(paper.knowledge_markdown_path).is_file()


def test_run_knowledge_analysis_rewrites_pdf_when_row_file_missing(tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.agent.tools import run_knowledge_analysis
    from app.api.chat import _list_artifacts_sync
    from app.db.models import Artifact, ExamPaper
    from app.db.sync_session import sync_session
    from app.main import app

    missing = tmp_path / "gone.pdf"
    parsed, alignment = _parsed_and_alignment()

    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        with sync_session() as s:
            p = ExamPaper(
                conversation_id=cid,
                source_type="test",
                structured_confirm_status="confirmed",
                structured_version=1,
                parsed_json=parsed,
                alignment_json=alignment,
            )
            s.add(p)
            s.commit()
            pid = p.id
            s.add(
                Artifact(
                    paper_id=pid,
                    kind="knowledge_pdf",
                    display_name="考点说明",
                    path=missing.as_posix(),
                    source_tool="run_knowledge_analysis",
                )
            )
            s.commit()

        def fake_render(_payload, path: Path) -> None:
            _write_fake_pdf(path)

        with (
            patch("app.agent.tools.analyze_knowledge", return_value=_ka()),
            patch("app.agent.tools.render_knowledge_pdf", side_effect=fake_render),
        ):
            out = run_knowledge_analysis.invoke({"paper_id": pid})

        assert "成功" in out
        with sync_session() as s:
            rows = list(
                s.execute(
                    select(Artifact).where(
                        Artifact.paper_id == pid, Artifact.kind == "knowledge_pdf"
                    )
                ).scalars()
            )
        assert len(rows) == 1
        assert Path(rows[0].path).is_file()
        assert rows[0].path != missing.as_posix()
        assert not any(not Path(a.path).is_file() for a in rows)

        items = _list_artifacts_sync(cid)
        slot = [i for i in items if i["category"] == "knowledge_markdown"]
        assert len(slot) == 1
        assert slot[0]["kind"] == "knowledge_pdf"
        assert Path(slot[0]["path"]).is_file()


def test_run_knowledge_analysis_timeout_unlinks_partial_keeps_markdown():
    from fastapi.testclient import TestClient

    from app.agent.tools import run_knowledge_analysis
    from app.db.models import Artifact, ExamPaper
    from app.db.sync_session import sync_session
    from app.main import app

    parsed, alignment = _parsed_and_alignment()
    written: dict[str, Path] = {}

    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        with sync_session() as s:
            p = ExamPaper(
                conversation_id=cid,
                source_type="test",
                structured_confirm_status="confirmed",
                structured_version=1,
                parsed_json=parsed,
                alignment_json=alignment,
            )
            s.add(p)
            s.commit()
            pid = p.id

        def fake_render(_payload, path: Path) -> None:
            written["pdf"] = path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-partial")
            raise TimeoutError("read timed out")

        with (
            patch("app.agent.tools.analyze_knowledge", return_value=_ka()),
            patch("app.agent.tools.render_knowledge_pdf", side_effect=fake_render),
        ):
            out = run_knowledge_analysis.invoke({"paper_id": pid})

    assert out == "连接超时建议重试"
    assert "技术说明" not in out
    assert written["pdf"].exists() is False
    with sync_session() as s:
        rows = list(
            s.execute(
                select(Artifact).where(
                    Artifact.paper_id == pid, Artifact.kind == "knowledge_pdf"
                )
            ).scalars()
        )
        paper = s.get(ExamPaper, pid)
    assert rows == []
    assert paper is not None
    assert paper.knowledge_markdown_path
    assert Path(paper.knowledge_markdown_path).is_file()

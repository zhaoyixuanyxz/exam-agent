import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select

from app.agent.tools import generate_chunk_practice_pdf, generate_chunk_practice_pdfs_batch
from app.db.models import Artifact, ExamPaper
from app.db.sync_session import sync_session
from app.main import app
from app.services.layout_timeout import (
    TIMEOUT_MESSAGE,
    assistant_text_after_layout_timeout,
    is_connection_timeout,
    run_layout_write,
    user_text_for_layout_timeout,
)
from app.services.storage import export_dir_for_conversation


def test_timeout_message_is_exact_sentence_without_secrets():
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE
    assert "Traceback" not in TIMEOUT_MESSAGE
    assert "sk-" not in TIMEOUT_MESSAGE


def test_is_connection_timeout_matches_interrupts_only():
    assert is_connection_timeout(TimeoutError()) is True
    assert is_connection_timeout(TimeoutError("timed out")) is True
    assert is_connection_timeout(ConnectionResetError()) is True
    assert is_connection_timeout(ConnectionError("Connection refused")) is True
    assert is_connection_timeout(Exception("ConnectError: failed")) is True
    assert is_connection_timeout(ValueError("nope")) is False
    assert is_connection_timeout(ValueError("KaiTi missing")) is False


def test_user_text_for_layout_timeout_is_sentence_or_none():
    assert user_text_for_layout_timeout(TimeoutError("timed out")) == TIMEOUT_MESSAGE
    assert user_text_for_layout_timeout(ValueError("KaiTi missing")) is None


def test_run_layout_write_timeout_keeps_existing_file(tmp_path: Path):
    kept = tmp_path / "考点说明.pdf"
    kept.write_bytes(b"%PDF-1.4 color")

    def boom() -> None:
        raise ConnectionResetError("reset")

    assert run_layout_write(boom) == TIMEOUT_MESSAGE
    assert kept.read_bytes() == b"%PDF-1.4 color"


def test_run_layout_write_other_errors_still_raise():
    def boom() -> None:
        raise ValueError("KaiTi missing")

    try:
        run_layout_write(boom)
    except ValueError as exc:
        assert "KaiTi" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_assistant_text_after_layout_timeout_overrides_paraphrase():
    msgs = [
        HumanMessage(content="出练习"),
        AIMessage(content=""),
        ToolMessage(content=TIMEOUT_MESSAGE, tool_call_id="1"),
        AIMessage(content="网络好像不太好，我们换个说法再试。"),
    ]
    assert assistant_text_after_layout_timeout(msgs) == TIMEOUT_MESSAGE


def test_assistant_text_after_layout_timeout_none_when_success():
    msgs = [
        ToolMessage(content="成功：练习已生成，请在界面「生成文件」中下载。", tool_call_id="1"),
        AIMessage(content="练习卷已经在生成文件里了。"),
    ]
    assert assistant_text_after_layout_timeout(msgs) is None


def test_assistant_text_after_layout_timeout_ignores_prior_turn():
    msgs = [
        HumanMessage(content="出练习"),
        ToolMessage(content=TIMEOUT_MESSAGE, tool_call_id="1"),
        AIMessage(content=TIMEOUT_MESSAGE),
        HumanMessage(content="再试一次"),
        ToolMessage(content="成功：练习已生成，请在界面「生成文件」中下载。", tool_call_id="2"),
        AIMessage(content="练习卷已经在生成文件里了。"),
    ]
    assert assistant_text_after_layout_timeout(msgs) is None


def _ka_two_points() -> dict:
    return {
        "theme_title": "测",
        "knowledge_points": [
            {"key": "kp_a", "name": "一次函数", "summary": "s", "book_chapter_hint": "通用"},
            {"key": "kp_b", "name": "几何", "summary": "s", "book_chapter_hint": "通用"},
        ],
        "mappings": [{"question_order": 1, "knowledge_point_key": "kp_a"}],
    }


def _seed_paper_with_stored_practice(cid: str) -> tuple[str, Path]:
    pdf = export_dir_for_conversation(cid) / "practice_kp_a.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 stored-a")
    with sync_session() as session:
        paper = ExamPaper(
            conversation_id=cid,
            source_type="test",
            knowledge_analysis_json=_ka_two_points(),
        )
        session.add(paper)
        session.flush()
        session.add(
            Artifact(
                paper_id=paper.id,
                kind="pdf_question",
                path=pdf.as_posix(),
                knowledge_point_key="kp_a",
                display_name="一次函数练习卷",
            )
        )
        session.commit()
        return paper.id, pdf


def test_practice_timeout_returns_exact_sentence_keeps_stored_pdf():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        with patch(
            "app.agent.tools.generate_practice_set",
            side_effect=TimeoutError("timed out"),
        ):
            out = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert out == TIMEOUT_MESSAGE
        assert "技术说明" not in str(out)
        assert pdf.is_file()
        with sync_session() as session:
            rows = list(
                session.scalars(select(Artifact).where(Artifact.paper_id == paper_id))
            )
            assert len(rows) == 1
            assert rows[0].knowledge_point_key == "kp_a"


def test_practice_render_timeout_returns_sentence_not_font_copy():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        with (
            patch(
                "app.agent.tools.generate_practice_set",
                return_value=MagicMock(),
            ),
            patch(
                "app.agent.tools.render_practice_pdf",
                side_effect=ConnectionError("Connection refused"),
            ),
        ):
            out = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert out == TIMEOUT_MESSAGE
        assert "楷体" not in str(out)
        assert pdf.is_file()


def test_practice_render_font_error_keeps_kaiti_copy():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, _pdf = _seed_paper_with_stored_practice(cid)
        with (
            patch(
                "app.agent.tools.generate_practice_set",
                return_value=MagicMock(),
            ),
            patch(
                "app.agent.tools.render_practice_pdf",
                side_effect=ValueError("KaiTi missing"),
            ),
        ):
            out = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert out != TIMEOUT_MESSAGE
        assert "楷体" in str(out)


def test_batch_timeout_returns_only_the_sentence_and_stops():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        calls: list[str] = []

        def fake_gen(session, paper, kp, *args, **kwargs):
            calls.append(kp.key)
            if kp.key == "kp_a":
                return None
            return TIMEOUT_MESSAGE

        items = json.dumps(
            [
                {"knowledge_point_key": "kp_a"},
                {"knowledge_point_key": "kp_b"},
            ]
        )
        with patch(
            "app.agent.tools._generate_chunk_practice_pdf_for_kp",
            side_effect=fake_gen,
        ):
            out = generate_chunk_practice_pdfs_batch.invoke(
                {"paper_id": paper_id, "items_json": items}
            )
        assert out == TIMEOUT_MESSAGE
        assert "批量结果" not in str(out)
        assert calls == ["kp_a", "kp_b"]
        assert pdf.is_file()


def test_retry_unfinished_point_does_not_clear_stored_pdf():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        with patch(
            "app.agent.tools.generate_practice_set",
            side_effect=TimeoutError("timed out"),
        ):
            first = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert first == TIMEOUT_MESSAGE
        with (
            patch(
                "app.agent.tools.generate_practice_set",
                return_value=MagicMock(),
            ),
            patch("app.agent.tools.render_practice_pdf"),
            patch("app.agent.tools.render_answer_pdf"),
        ):
            second = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert "成功" in str(second)
        assert pdf.is_file()
        with sync_session() as session:
            rows = list(
                session.scalars(select(Artifact).where(Artifact.paper_id == paper_id))
            )
            keys = {row.knowledge_point_key for row in rows}
            assert "kp_a" in keys
            assert "kp_b" in keys


def test_chat_runner_imports_layout_timeout_relay():
    import inspect

    from app.api import chat as chat_mod

    source = inspect.getsource(chat_mod)
    assert "assistant_text_after_layout_timeout" in source

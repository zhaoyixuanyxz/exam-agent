from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import ExamPaper
from app.db.sync_session import sync_session
from app.main import app
from app.services.conversation_delete import collect_conversation_file_paths
from app.services.exam_ingest import MIXED_UPLOAD_MESSAGE, extract_exam_text
from app.services.page_text import EMPTY_PAPER_MESSAGE


def _pdf_with_text(path: Path, text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    # Helvetica cannot encode CJK, so the text layer would be dots and look sparse.
    page.insert_text((72, 72), text, fontname="china-s")
    doc.save(path.as_posix())
    doc.close()
    return path


def _pdf_blank(path: Path) -> Path:
    doc = fitz.open()
    doc.new_page()
    doc.save(path.as_posix())
    doc.close()
    return path


def test_extract_exam_text_uses_pdf_text_layer_without_vision(tmp_path: Path):
    pdf = _pdf_with_text(tmp_path / "e.pdf", "第一题 二次函数顶点坐标")
    calls = {"n": 0}

    def vision(_data: bytes) -> str:
        calls["n"] += 1
        return "should-not-run"

    out = extract_exam_text([pdf], read_image_text=vision)
    assert "二次函数" in out
    assert calls["n"] == 0


def test_extract_exam_text_visions_blank_pdf_page_and_merges(tmp_path: Path):
    pdf = _pdf_blank(tmp_path / "scan.pdf")
    calls = {"n": 0}

    def vision(_data: bytes) -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TimeoutError("timed out")
        return "扫描第1题 几何面积"

    out = extract_exam_text([pdf], read_image_text=vision)
    assert "几何面积" in out
    assert calls["n"] == 2


def test_extract_exam_text_scraps_page_keeps_other_pages(tmp_path: Path):
    img_a = tmp_path / "a.png"
    img_b = tmp_path / "b.png"
    img_a.write_bytes(b"\x89PNG\r\n\x1a\n")
    img_b.write_bytes(b"\x89PNG\r\n\x1a\n")
    n = {"i": 0}

    def vision(_data: bytes) -> str:
        n["i"] += 1
        if n["i"] <= 3:
            return ""
        return "第二页 选择题"

    out = extract_exam_text([img_a, img_b], read_image_text=vision)
    assert "选择题" in out
    assert n["i"] == 4


def test_extract_exam_text_all_scrap_is_empty(tmp_path: Path):
    img = tmp_path / "blank.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    def vision(_data: bytes) -> str:
        return ""

    assert extract_exam_text([img], read_image_text=vision) == ""


def test_extract_exam_text_rejects_pdf_mixed_with_images(tmp_path: Path):
    pdf = _pdf_with_text(tmp_path / "e.pdf", "第一题")
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError, match="请分开交"):
        extract_exam_text([pdf, img], read_image_text=lambda _b: "x")
    assert MIXED_UPLOAD_MESSAGE == "请分开交"


def test_extract_exam_text_rejects_multiple_pdfs(tmp_path: Path):
    a = _pdf_with_text(tmp_path / "a.pdf", "第一题")
    b = _pdf_with_text(tmp_path / "b.pdf", "第二题")
    with pytest.raises(ValueError, match="请分开交"):
        extract_exam_text([a, b], read_image_text=lambda _b: "x")


def test_extract_exam_text_rejects_doc(tmp_path: Path):
    p = tmp_path / "old.doc"
    p.write_bytes(b"x")
    with pytest.raises(ValueError, match="docx"):
        extract_exam_text([p], read_image_text=lambda _b: "x")


def test_chat_stream_accepts_two_pngs_as_one_paper():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with patch(
            "app.api.chat.extract_exam_text",
            return_value="第一题 一次函数\n\n第二题 几何",
        ) as ingest:
            r = client.post(
                "/api/chat/stream",
                data={"conversation_id": cid, "message": "", "source_type": "pdf"},
                files=[
                    ("files", ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")),
                    ("files", ("b.png", b"\x89PNG\r\n\x1a\n", "image/png")),
                ],
            )
        assert r.status_code == 200
        assert ingest.called
        paths = ingest.call_args.args[0]
        assert [p.name.endswith(".png") for p in paths] == [True, True]
        with sync_session() as session:
            papers = list(
                session.scalars(select(ExamPaper).where(ExamPaper.conversation_id == cid))
            )
            assert len(papers) == 1
            assert papers[0].source_type == "image"
            assert "一次函数" in (papers[0].raw_text or "")
            stored = [Path(line) for line in (papers[0].raw_path or "").split("\n") if line.strip()]
            assert len(stored) == 2
            assert all(p.suffix.lower() == ".png" for p in stored)
            assert all(p.is_file() for p in stored)
        found, _export = collect_conversation_file_paths(cid)
        assert set(stored) <= found


def test_chat_stream_rejects_mixed_pdf_and_png():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        r = client.post(
            "/api/chat/stream",
            data={"conversation_id": cid, "message": "", "source_type": "pdf"},
            files=[
                ("files", ("e.pdf", b"%PDF-1.4", "application/pdf")),
                ("files", ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")),
            ],
        )
        assert r.status_code == 400
        assert "请分开交" in r.json()["detail"]


def test_chat_stream_empty_vision_still_stores_paper():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with patch("app.api.chat.extract_exam_text", return_value=""):
            r = client.post(
                "/api/chat/stream",
                data={"conversation_id": cid, "message": "", "source_type": "pdf"},
                files=[("files", ("a.png", b"\x89PNG\r\n\x1a\n", "image/png"))],
            )
        assert r.status_code == 200
        with sync_session() as session:
            papers = list(
                session.scalars(select(ExamPaper).where(ExamPaper.conversation_id == cid))
            )
            assert len(papers) == 1
            assert papers[0].raw_text == ""
            assert papers[0].source_type == "image"
            paper_id = papers[0].id
        from app.agent.tools import structure_exam_paper

        out = structure_exam_paper.invoke({"paper_id": paper_id})
        assert out == EMPTY_PAPER_MESSAGE
        assert "连接超时建议重试" not in str(out)


def test_chat_stream_pdf_and_docx_keep_their_source_types():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with patch("app.api.chat.extract_exam_text", return_value="第一题 正文"):
            pdf_r = client.post(
                "/api/chat/stream",
                data={"conversation_id": cid, "message": "", "source_type": "text"},
                files=[("files", ("Exam.PDF", b"%PDF-1.4", "application/pdf"))],
            )
            docx_r = client.post(
                "/api/chat/stream",
                data={"conversation_id": cid, "message": "", "source_type": "text"},
                files=[
                    (
                        "files",
                        (
                            "notes.docx",
                            b"PK\x03\x04",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        ),
                    )
                ],
            )
        assert pdf_r.status_code == 200
        assert docx_r.status_code == 200
        with sync_session() as session:
            papers = list(
                session.scalars(
                    select(ExamPaper)
                    .where(ExamPaper.conversation_id == cid)
                    .order_by(ExamPaper.created_at)
                )
            )
            by_type = {p.source_type: p for p in papers}
            assert set(by_type) == {"pdf", "docx"}
            assert (by_type["pdf"].raw_path or "").lower().endswith(".pdf")
            assert "\n" not in (by_type["pdf"].raw_path or "")
            assert (by_type["docx"].raw_path or "").lower().endswith(".docx")


def test_chat_stream_value_error_is_400_without_parse_prefix():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with patch(
            "app.api.chat.extract_exam_text",
            side_effect=ValueError("DEEPSEEK_API_KEY_MISSING"),
        ):
            r = client.post(
                "/api/chat/stream",
                data={"conversation_id": cid, "message": "", "source_type": "pdf"},
                files=[("files", ("a.png", b"\x89PNG\r\n\x1a\n", "image/png"))],
            )
        assert r.status_code == 400
        assert r.json()["detail"] == "DEEPSEEK_API_KEY_MISSING"


def test_chat_stream_extract_exception_is_400_parse_failure():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with patch(
            "app.api.chat.extract_exam_text",
            side_effect=RuntimeError("fitz boom"),
        ):
            r = client.post(
                "/api/chat/stream",
                data={"conversation_id": cid, "message": "", "source_type": "pdf"},
                files=[("files", ("bad.pdf", b"%PDF-1.4", "application/pdf"))],
            )
        assert r.status_code == 400
        assert r.json()["detail"] == "解析失败: fitz boom"

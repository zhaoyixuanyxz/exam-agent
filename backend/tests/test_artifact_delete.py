from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models import Artifact, ExamPaper, QuestionAsset
from app.db.sync_session import sync_session
from app.main import app
from app.services.artifact_delete import PDF_KINDS, delete_stored_pdf
from app.services.storage import export_dir_for_conversation


def _write_pdf(cid: str, name: str, body: bytes = b"%PDF-1.4") -> Path:
    path = export_dir_for_conversation(cid) / name
    path.write_bytes(body)
    return path


def test_delete_stored_pdf_unlinks_file_keeps_questions():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _write_pdf(cid, "practice_kp_a.pdf", b"%PDF-1.4 keep-me")
        other = _write_pdf(cid, "practice_kp_a_answers.pdf", b"%PDF-1.4 other")
        with sync_session() as s:
            paper = ExamPaper(conversation_id=cid, source_type="test")
            s.add(paper)
            s.flush()
            qa = QuestionAsset(
                conversation_id=cid,
                paper_id=paper.id,
                question_order=1,
                stem="二次函数顶点",
                knowledge_point_keys_json=["kp_a"],
            )
            art = Artifact(
                paper_id=paper.id,
                kind="pdf_question",
                path=pdf.as_posix(),
                knowledge_point_key="kp_a",
                display_name="练习卷",
            )
            other_art = Artifact(
                paper_id=paper.id,
                kind="pdf_answer",
                path=other.as_posix(),
                knowledge_point_key="kp_a",
                display_name="参考答案",
            )
            s.add_all([qa, art, other_art])
            s.commit()
            paper_id = paper.id
            art_id = art.id
            other_id = other_art.id
            qa_id = qa.id
        with sync_session() as s:
            row = s.get(Artifact, art_id)
            delete_stored_pdf(s, row)
            s.commit()
        assert pdf.is_file() is False
        assert other.is_file() is True
        with sync_session() as s:
            assert s.get(Artifact, art_id) is None
            assert s.get(Artifact, other_id) is not None
            kept = s.get(QuestionAsset, qa_id)
            assert kept is not None
            assert kept.stem == "二次函数顶点"
            assert s.get(ExamPaper, paper_id) is not None
    assert "pdf_question" in PDF_KINDS
    assert "pdf_answer" in PDF_KINDS
    assert "knowledge_pdf" in PDF_KINDS

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agent.tools import _generate_chunk_practice_pdf_for_kp
from app.api.chat import _list_artifacts_sync
from app.db.models import Artifact, ExamPaper, QuestionAsset
from app.db.sync_session import sync_session
from app.main import app
from app.models.schemas import KnowledgePointItem
from app.services.artifact_delete import PDF_KINDS, delete_stored_pdf, hide_knowledge_explanation
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


def test_hide_knowledge_explanation_keeps_markdown_file():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        out = export_dir_for_conversation(cid)
        md = out / "考点说明_x.md"
        md.write_text("# 说明", encoding="utf-8")
        pdf = _write_pdf(cid, "考点说明_x.pdf")
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_markdown_path=md.as_posix(),
            )
            s.add(paper)
            s.flush()
            art = Artifact(
                paper_id=paper.id,
                kind="knowledge_pdf",
                path=pdf.as_posix(),
                display_name="考点说明",
            )
            s.add(art)
            s.commit()
            paper_id = paper.id
            art_id = art.id
        with sync_session() as s:
            hide_knowledge_explanation(s, s.get(ExamPaper, paper_id))
            delete_stored_pdf(s, s.get(Artifact, art_id))
            s.commit()
        assert md.is_file() is True
        assert pdf.is_file() is False
        items = _list_artifacts_sync(cid)
        kinds = [i["kind"] for i in items]
        assert "markdown" not in kinds
        assert "knowledge_pdf" not in kinds


def test_delete_missing_file_still_drops_artifact():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        missing = export_dir_for_conversation(cid) / "gone.pdf"
        with sync_session() as s:
            paper = ExamPaper(conversation_id=cid, source_type="test")
            s.add(paper)
            s.flush()
            art = Artifact(
                paper_id=paper.id,
                kind="pdf_answer",
                path=missing.as_posix(),
                knowledge_point_key="kp_a",
            )
            s.add(art)
            s.commit()
            art_id = art.id
        with sync_session() as s:
            delete_stored_pdf(s, s.get(Artifact, art_id))
            s.commit()
        with sync_session() as s:
            assert s.get(Artifact, art_id) is None


def test_delete_artifact_endpoint_removes_list_item():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _write_pdf(cid, "q.pdf")
        with sync_session() as s:
            paper = ExamPaper(conversation_id=cid, source_type="test")
            s.add(paper)
            s.flush()
            qa = QuestionAsset(
                conversation_id=cid,
                paper_id=paper.id,
                question_order=1,
                stem="还在",
            )
            art = Artifact(
                paper_id=paper.id,
                kind="pdf_question",
                path=pdf.as_posix(),
                knowledge_point_key="kp_a",
            )
            s.add_all([qa, art])
            s.commit()
            art_id = art.id
            qa_id = qa.id
        listed = client.get(f"/api/conversations/{cid}/artifacts").json()["items"]
        assert any(i["id"] == art_id for i in listed)
        rd = client.delete(f"/api/conversations/{cid}/artifacts/{art_id}")
        assert rd.status_code == 200
        assert rd.json() == {"ok": True}
        assert pdf.is_file() is False
        listed2 = client.get(f"/api/conversations/{cid}/artifacts").json()["items"]
        assert all(i["id"] != art_id for i in listed2)
        with sync_session() as s:
            assert s.get(Artifact, art_id) is None
            assert s.get(QuestionAsset, qa_id) is not None


def test_delete_markdown_slot_hides_without_unlinking():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        md = export_dir_for_conversation(cid) / "考点说明_p.md"
        md.write_text("旧稿", encoding="utf-8")
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_markdown_path=md.as_posix(),
            )
            s.add(paper)
            s.commit()
            paper_id = paper.id
        rd = client.delete(f"/api/conversations/{cid}/artifacts/md:{paper_id}")
        assert rd.status_code == 200
        assert md.read_text(encoding="utf-8") == "旧稿"
        kinds = [
            i["kind"]
            for i in client.get(f"/api/conversations/{cid}/artifacts").json()["items"]
        ]
        assert "markdown" not in kinds


def test_practice_regenerate_fills_only_missing_kind(tmp_path: Path):
    q_pdf = tmp_path / "practice_kp_a.pdf"
    q_pdf.write_bytes(b"%PDF-1.4 question")
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_analysis_json={
                    "theme_title": "t",
                    "knowledge_points": [
                        {
                            "key": "kp_a",
                            "name": "顶点式",
                            "summary": "s",
                            "book_chapter_hint": "",
                        }
                    ],
                    "mappings": [],
                },
                alignment_json={"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
            )
            s.add(paper)
            s.flush()
            s.add(
                Artifact(
                    paper_id=paper.id,
                    kind="pdf_question",
                    path=q_pdf.as_posix(),
                    knowledge_point_key="kp_a",
                )
            )
            s.commit()
            paper_id = paper.id
        calls = {"q": 0, "a": 0}

        def fake_q(*_a, **_k):
            calls["q"] += 1

        def fake_a(*_a, **_k):
            calls["a"] += 1
            Path(_a[1]).write_bytes(b"%PDF-1.4 answers")

        with (
            patch("app.agent.tools.generate_practice_set") as gen,
            patch("app.agent.tools.render_practice_pdf", side_effect=fake_q),
            patch("app.agent.tools.render_answer_pdf", side_effect=fake_a),
            patch("app.agent.tools.export_dir_for_conversation", return_value=tmp_path),
        ):
            gen.return_value = type("P", (), {"knowledge_point_key": "", "knowledge_point_name": ""})()
            with sync_session() as s:
                paper = s.get(ExamPaper, paper_id)
                kp = KnowledgePointItem(key="kp_a", name="顶点式", summary="s", book_chapter_hint="")
                err = _generate_chunk_practice_pdf_for_kp(
                    s,
                    paper,
                    kp,
                    10,
                    use_original_figures=False,
                    include_figures=True,
                    difficulty="medium",
                    question_types_json="[]",
                    output_mode="questions_and_answers",
                )
                assert err is None
                s.commit()
        assert calls["q"] == 0
        assert calls["a"] == 1
        assert q_pdf.read_bytes() == b"%PDF-1.4 question"


def test_practice_regenerate_rewrites_questions_only_when_pdf_exists(tmp_path: Path):
    q_pdf = tmp_path / "practice_kp_a.pdf"
    q_pdf.write_bytes(b"%PDF-1.4 question")
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                knowledge_analysis_json={
                    "theme_title": "t",
                    "knowledge_points": [
                        {
                            "key": "kp_a",
                            "name": "顶点式",
                            "summary": "s",
                            "book_chapter_hint": "",
                        }
                    ],
                    "mappings": [],
                },
                alignment_json={"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
            )
            s.add(paper)
            s.flush()
            s.add(
                Artifact(
                    paper_id=paper.id,
                    kind="pdf_question",
                    path=q_pdf.as_posix(),
                    knowledge_point_key="kp_a",
                )
            )
            s.commit()
            paper_id = paper.id
        calls = {"q": 0, "a": 0}

        def fake_q(*_a, **_k):
            calls["q"] += 1

        def fake_a(*_a, **_k):
            calls["a"] += 1

        with (
            patch("app.agent.tools.generate_practice_set") as gen,
            patch("app.agent.tools.render_practice_pdf", side_effect=fake_q),
            patch("app.agent.tools.render_answer_pdf", side_effect=fake_a),
            patch("app.agent.tools.export_dir_for_conversation", return_value=tmp_path),
        ):
            gen.return_value = type("P", (), {"knowledge_point_key": "", "knowledge_point_name": ""})()
            with sync_session() as s:
                paper = s.get(ExamPaper, paper_id)
                kp = KnowledgePointItem(key="kp_a", name="顶点式", summary="s", book_chapter_hint="")
                err = _generate_chunk_practice_pdf_for_kp(
                    s,
                    paper,
                    kp,
                    10,
                    use_original_figures=False,
                    include_figures=True,
                    difficulty="medium",
                    question_types_json="[]",
                    output_mode="questions_only",
                )
                assert err is None
                s.commit()
        assert calls["q"] == 1
        assert calls["a"] == 0


def test_run_knowledge_analysis_clears_hidden_flag(monkeypatch):
    from app.agent.tools import run_knowledge_analysis
    from app.models.schemas import KnowledgeAnalysisResult, KnowledgePointItem

    def fake_analyze(_summary, _align):
        return KnowledgeAnalysisResult(
            theme_title="二次函数",
            knowledge_points=[
                KnowledgePointItem(key="kp_a", name="顶点式", summary="配方法求顶点", book_chapter_hint=""),
            ],
            mappings=[],
        )

    monkeypatch.setattr("app.agent.tools.analyze_knowledge", fake_analyze)
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="test",
                parsed_json={
                    "title": "卷",
                    "sections": [
                        {
                            "title": "一",
                            "questions": [
                                {
                                    "order_index": 1,
                                    "qtype": "填空",
                                    "stem": "题",
                                    "options": [],
                                    "blocks": [],
                                }
                            ],
                        }
                    ],
                },
                structured_confirm_status="confirmed",
                alignment_json={"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
                knowledge_explanation_hidden=True,
            )
            s.add(paper)
            s.commit()
            paper_id = paper.id
        msg = run_knowledge_analysis.invoke({"paper_id": paper_id})
        assert str(msg).startswith("成功")
        with sync_session() as s:
            assert s.get(ExamPaper, paper_id).knowledge_explanation_hidden is False

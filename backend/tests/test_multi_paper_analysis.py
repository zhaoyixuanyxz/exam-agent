from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.models import ExamPaper, QuestionAsset
from app.db.sync_session import sync_session
from sqlalchemy import func, select

from app.main import app


def _paper_payload(title: str, mappings: list[tuple[int, str]]) -> tuple[dict, dict]:
    questions = []
    for i, (oid, _kp) in enumerate(mappings, start=1):
        questions.append(
            {
                "order_index": oid,
                "qtype": "单选" if oid % 2 == 1 else "填空",
                "stem": f"题{oid}",
                "options": ["A", "B"] if oid % 2 == 1 else [],
                "blocks": [],
            },
        )
    parsed = {
        "title": title,
        "sections": [{"title": "第一大题", "questions": questions}],
    }
    kps = []
    seen = {kp for _, kp in mappings}
    for j, key in enumerate(sorted(seen)):
        kps.append(
            {
                "key": key,
                "name": f"名称{key}",
                "summary": "概述" * 5,
                "book_chapter_hint": f"第{j + 1}章",
            },
        )
    ka = {
        "theme_title": f"{title}考点",
        "knowledge_points": kps,
        "mappings": [{"question_order": oid, "knowledge_point_key": kp} for oid, kp in mappings],
    }
    return parsed, ka


def test_multi_paper_analysis_requires_two_papers():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        with sync_session() as s:
            p1 = ExamPaper(
                conversation_id=cid,
                source_type="test",
                structured_confirm_status="confirmed",
                structured_version=1,
                parsed_json=_paper_payload("A", [(1, "k1")])[0],
                knowledge_analysis_json=_paper_payload("A", [(1, "k1")])[1],
            )
            s.add(p1)
            s.commit()
            pid = p1.id
        bad = client.post(
            f"/api/conversations/{cid}/multi-paper-analysis",
            json={"paper_ids": [pid]},
        )
        assert bad.status_code == 422  # validation min_length=2


def test_confirm_syncs_question_assets_and_multi_paper_analysis():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        pj_a, ka_a = _paper_payload("卷甲", [(1, "kp_shared"), (2, "kp_only_a")])
        pj_b, ka_b = _paper_payload("卷乙", [(1, "kp_shared"), (2, "kp_only_b")])
        with sync_session() as s:
            pa = ExamPaper(
                conversation_id=cid,
                source_type="test",
                display_name="卷甲",
                structured_confirm_status="pending",
                structured_version=1,
                parsed_json=pj_a,
                knowledge_analysis_json=ka_a,
                alignment_json={"subject": "数学", "grade_min": "初二", "grade_max": "初二"},
            )
            pb = ExamPaper(
                conversation_id=cid,
                source_type="test",
                display_name="卷乙",
                structured_confirm_status="pending",
                structured_version=1,
                parsed_json=pj_b,
                knowledge_analysis_json=ka_b,
                alignment_json={"subject": "数学", "grade_min": "初二", "grade_max": "初二"},
            )
            s.add_all([pa, pb])
            s.commit()
            id_a, id_b = pa.id, pb.id

        ca = client.post(f"/api/conversations/{cid}/papers/{id_a}/structured/confirm")
        assert ca.status_code == 200
        assert ca.json().get("question_assets_synced") == 2
        cb = client.post(f"/api/conversations/{cid}/papers/{id_b}/structured/confirm")
        assert cb.status_code == 200
        assert cb.json().get("question_assets_synced") == 2

        with sync_session() as s:
            n = s.scalar(
                select(func.count()).select_from(QuestionAsset).where(QuestionAsset.paper_id == id_a),
            )
            assert n == 2

        rep = client.post(
            f"/api/conversations/{cid}/multi-paper-analysis",
            json={"paper_ids": [id_a, id_b]},
        )
        assert rep.status_code == 200
        data = rep.json()
        assert data["conversation_id"] == cid
        assert len(data["paper_summaries"]) == 2
        common = data["knowledge_coverage_diff"]["common_across_selected"]
        assert "kp_shared" in common
        repeated = {x["knowledge_point_key"] for x in data["repeated_knowledge_points"]}
        assert "kp_shared" in repeated

        # 幂等重建
        rb = client.post(f"/api/conversations/{cid}/papers/{id_a}/question-assets/rebuild")
        assert rb.status_code == 200
        assert rb.json().get("count") == 2
        with sync_session() as s:
            n2 = s.scalar(
                select(func.count()).select_from(QuestionAsset).where(QuestionAsset.paper_id == id_a),
            )
            assert n2 == 2


def test_multi_paper_subject_filter_excludes_paper():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        pj_a, ka_a = _paper_payload("A", [(1, "k1")])
        pj_b, ka_b = _paper_payload("B", [(1, "k2")])
        with sync_session() as s:
            pa = ExamPaper(
                conversation_id=cid,
                source_type="test",
                structured_confirm_status="pending",
                structured_version=1,
                parsed_json=pj_a,
                knowledge_analysis_json=ka_a,
                alignment_json={"subject": "数学", "grade_min": "初二", "grade_max": "初二"},
            )
            pb = ExamPaper(
                conversation_id=cid,
                source_type="test",
                structured_confirm_status="pending",
                structured_version=1,
                parsed_json=pj_b,
                knowledge_analysis_json=ka_b,
                alignment_json={"subject": "物理", "grade_min": "初二", "grade_max": "初二"},
            )
            s.add_all([pa, pb])
            s.commit()
            id_a, id_b = pa.id, pb.id
        client.post(f"/api/conversations/{cid}/papers/{id_a}/structured/confirm")
        client.post(f"/api/conversations/{cid}/papers/{id_b}/structured/confirm")
        res = client.post(
            f"/api/conversations/{cid}/multi-paper-analysis",
            json={"paper_ids": [id_a, id_b], "subject": "数学"},
        )
        assert res.status_code == 400

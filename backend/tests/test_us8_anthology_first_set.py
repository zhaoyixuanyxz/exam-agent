from fastapi.testclient import TestClient

from app.agent.tools import run_knowledge_analysis
from app.db.models import ExamPaper
from app.db.sync_session import sync_session
from app.main import app
from app.services.structured_inspect import list_anomalies

_PARSED = {
    "title": "2022套",
    "sections": [
        {
            "title": "一",
            "questions": [
                {
                    "order_index": 1,
                    "qtype": "选择",
                    "stem": "题1",
                    "options": [],
                    "blocks": [],
                }
            ],
        }
    ],
}


def test_confirm_blocked_on_parent_anthology_done():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            parent = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                anthology_split_status="done",
            )
            s.add(parent)
            s.commit()
            pid = parent.id

        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 400


def test_confirm_ok_on_child_after_split():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            child = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                anthology_split_status="none",
                display_name="2022广州中考",
            )
            s.add(child)
            s.commit()
            pid = child.id

        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 200
        assert r.json()["structured_confirm_status"] == "confirmed"


def test_knowledge_analysis_refuses_parent_anthology_done():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            parent = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                structured_confirm_status="confirmed",
                alignment_json={
                    "grade_min": "初三",
                    "grade_max": "初三",
                    "subject": "数学",
                    "type_counts": {"选择": 1},
                },
                anthology_split_status="done",
            )
            s.add(parent)
            s.commit()
            pid = parent.id

        msg = run_knowledge_analysis.invoke({"paper_id": pid})
        assert "父本" in msg or "套卷" in msg


def test_structured_anomalies_lists_duplicate_order_index():
    parsed = {
        "title": "t",
        "sections": [
            {
                "title": "一",
                "questions": [
                    {
                        "order_index": 1,
                        "qtype": "选择",
                        "stem": "a",
                        "options": [],
                        "blocks": [],
                    },
                    {
                        "order_index": 1,
                        "qtype": "选择",
                        "stem": "b",
                        "options": [],
                        "blocks": [],
                    },
                ],
            }
        ],
    }
    msgs = list_anomalies(parsed)
    assert any("重复" in m or "order_index" in m for m in msgs)
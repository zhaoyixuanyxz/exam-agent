from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_openapi_available():
    with TestClient(app) as client:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "试卷考点" in r.json().get("info", {}).get("title", "")


def test_create_conversation():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        assert r.status_code == 200
        data = r.json()
        assert "conversation_id" in data
        assert len(data["conversation_id"]) > 8


def test_artifacts_empty_conversation():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        r2 = client.get(f"/api/conversations/{cid}/artifacts")
        assert r2.status_code == 200
        assert r2.json().get("items") == []


def test_agent_run_active_false_when_idle():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        st = client.get(f"/api/conversations/{cid}/agent-run-active")
        assert st.status_code == 200
        assert st.json() == {"active": False}


def test_list_conversations():
    with TestClient(app) as client:
        r = client.get("/api/conversations")
        assert r.status_code == 200
        data = r.json()
        assert "conversations" in data
        assert isinstance(data["conversations"], list)


def test_list_conversations_has_v21_fields():
    with TestClient(app) as client:
        r = client.get("/api/conversations")
        assert r.status_code == 200
        rows = r.json().get("conversations") or []
        if not rows:
            return
        row = rows[0]
        assert "subject" in row
        assert "grade_range" in row
        assert "last_artifact_category" in row


def test_list_conversations_subject_filter():
    with TestClient(app) as client:
        r = client.get("/api/conversations", params={"subject": "__no_match_xyz__"})
        assert r.status_code == 200
        assert r.json().get("conversations") == []


def test_patch_conversation_title():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        p = client.patch(
            f"/api/conversations/{cid}",
            json={"title": "  期中复习  "},
        )
        assert p.status_code == 200
        assert p.json().get("title") == "期中复习"
        listed = client.get("/api/conversations").json()["conversations"]
        row = next((c for c in listed if c["id"] == cid), None)
        assert row is not None
        assert row.get("title") == "期中复习"
        clear = client.patch(f"/api/conversations/{cid}", json={"title": ""})
        assert clear.status_code == 200
        assert clear.json().get("title") is None


def test_messages_and_delete_conversation():
    with TestClient(app) as client:
        r = client.post("/api/conversations")
        cid = r.json()["conversation_id"]
        rm = client.get(f"/api/conversations/{cid}/messages")
        assert rm.status_code == 200
        assert rm.json().get("messages") == []
        rd = client.delete(f"/api/conversations/{cid}")
        assert rd.status_code == 200
        assert rd.json().get("ok") is True
        r404 = client.get(f"/api/conversations/{cid}/messages")
        assert r404.status_code == 404

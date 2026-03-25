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

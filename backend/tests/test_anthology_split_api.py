from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.db.models import ExamPaper
from app.db.sync_session import sync_session
from app.main import app


def _pdf(tmp: Path, pages: list[str]) -> Path:
    p = tmp / "a.pdf"
    doc = fitz.open()
    try:
        for t in pages:
            pg = doc.new_page()
            pg.insert_text((72, 72), t)
        doc.save(p.as_posix())
    finally:
        doc.close()
    return p


def test_confirm_blocked_when_needed(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(tmp_path, ["2021年中考", "x", "2022年中考", "y"])
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                raw_path=pdf.as_posix(),
                parsed_json={
                    "title": "合订",
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
                structured_confirm_status="pending",
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 400
        assert "分套" in r.json()["detail"]


def test_single_ok_allows_confirm(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
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
                structured_confirm_status="pending",
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(
            f"/api/conversations/{cid}/papers/{pid}/anthology-split/single-ok"
        )
        assert r.status_code == 200
        assert r.json()["anthology_split_status"] == "single_ok"
        r2 = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r2.status_code == 200

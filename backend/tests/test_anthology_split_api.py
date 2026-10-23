from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.db.models import ExamPaper
from app.db.sync_session import sync_session
from app.main import app
from app.services.anthology_ranges import CONFIRM_BLOCKED_NEEDED


def _pdf(tmp: Path, pages: list[str]) -> Path:
    p = tmp / "a.pdf"
    doc = fitz.open()
    try:
        for t in pages:
            pg = doc.new_page()
            pg.insert_text((72, 72), t, fontname="china-s")
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
        list_r = client.get(f"/api/conversations/{cid}/papers")
        assert list_r.status_code == 200
        papers = list_r.json()["papers"]
        assert len(papers) == 1
        assert papers[0]["id"] == pid
        assert papers[0]["anthology_split_status"] == "needed"

        struct_r = client.get(f"/api/conversations/{cid}/papers/{pid}/structured")
        assert struct_r.status_code == 200
        assert struct_r.json()["anthology_split_status"] == "needed"

        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 400
        assert CONFIRM_BLOCKED_NEEDED in r.json()["detail"]


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


def test_suggest_page_ranges_and_mark_needed(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(
            tmp_path,
            [
                "2021年广州市中考数学",
                "题",
                "2022年广州市中考数学",
                "题",
            ],
        )
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                raw_path=pdf.as_posix(),
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(
            f"/api/exam-papers/{pid}/anthology-split/mark-needed",
            json={"conversation_id": cid},
        )
        assert r.status_code == 200
        assert r.json()["anthology_split_status"] == "needed"
        sgg = client.post(
            f"/api/exam-papers/{pid}/suggest-page-ranges",
            json={"conversation_id": cid},
        )
        assert sgg.status_code == 200
        body = sgg.json()
        assert len(body["ranges"]) >= 2
        assert len(body["labels"]) == len(body["ranges"])

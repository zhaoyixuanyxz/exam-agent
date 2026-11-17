from pathlib import Path

import pymupdf
from fastapi.testclient import TestClient

from app.db.models import ExamPaper
from app.db.sync_session import sync_session
from app.main import app

_PARSED = {
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
}


def _pdf(tmp: Path, pages: list[str]) -> Path:
    p = tmp / "a.pdf"
    doc = pymupdf.open()
    try:
        for t in pages:
            pg = doc.new_page()
            try:
                pg.insert_text((72, 72), t, fontname="china-s")
            except Exception:
                pg.insert_text((72, 72), t)
        doc.save(p.as_posix())
    finally:
        doc.close()
    return p


def test_confirm_blocked_when_needed():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                structured_confirm_status="pending",
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert "分套" in detail or "合订" in detail


def test_single_ok_allows_confirm():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                structured_confirm_status="pending",
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(f"/api/conversations/{cid}/papers/{pid}/anthology-split/single-ok")
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


def test_split_sets_parent_done_and_labels(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(tmp_path, ["2021年中考 A", "a2", "2022年中考 B", "b2"])
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                raw_path=pdf.as_posix(),
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(
            f"/api/exam-papers/{pid}/split-by-pages",
            json={
                "conversation_id": cid,
                "ranges": [[1, 2], [3, 4]],
                "labels": ["2021年试卷", "2022年试卷"],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["new_papers"]) == 2
        assert body["new_papers"][0]["label"] == "2021年试卷"
        with sync_session() as s:
            parent = s.get(ExamPaper, pid)
            assert parent is not None
            assert parent.anthology_split_status == "done"
            child = s.get(ExamPaper, body["new_papers"][0]["id"])
            assert child is not None
            assert child.display_name == "2021年试卷"
            assert (child.anthology_split_status or "none") == "none"


def test_get_structured_marks_needed_on_duplicate_order_index():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                anthology_split_status="none",
                parsed_json={
                    "title": "合订",
                    "sections": [
                        {
                            "title": "一",
                            "questions": [
                                {
                                    "order_index": 1,
                                    "qtype": "填空",
                                    "stem": "a",
                                    "options": [],
                                    "blocks": [],
                                },
                                {
                                    "order_index": 1,
                                    "qtype": "填空",
                                    "stem": "b",
                                    "options": [],
                                    "blocks": [],
                                },
                            ],
                        }
                    ],
                },
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.get(f"/api/conversations/{cid}/papers/{pid}/structured")
        assert r.status_code == 200
        assert any("重复" in a for a in r.json()["anomalies"])
        assert r.json()["anthology_split_status"] == "needed"
        with sync_session() as s:
            assert s.get(ExamPaper, pid).anthology_split_status == "needed"
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
        assert body["ranges"] == [[1, 2], [3, 4]]
        assert body["labels"] == ["2021年试卷", "2022年试卷"]
        assert body["message"] == ""
        assert body["page_count"] == 4


def test_mark_needed_rejects_when_done(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(tmp_path, ["2021年中考", "x"])
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                raw_path=pdf.as_posix(),
                anthology_split_status="done",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(
            f"/api/exam-papers/{pid}/anthology-split/mark-needed",
            json={"conversation_id": cid},
        )
        assert r.status_code == 400
        assert "已切开" in r.json()["detail"]


def test_suggest_wrong_conversation_returns_404(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        other_cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(tmp_path, ["2021年广州市中考数学", "题", "2022年广州市中考数学", "题"])
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
            f"/api/exam-papers/{pid}/suggest-page-ranges",
            json={"conversation_id": other_cid},
        )
        assert r.status_code == 404


def test_split_sets_parent_done_and_labels(tmp_path: Path, monkeypatch):
    # brief 页文案 CJK < 4 会走 vision；单测不打真实 API
    monkeypatch.setattr(
        "app.services.vision_read.read_image_text",
        lambda _b: "足够中文文本一二三四",
    )
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
        # 全覆盖时 hint 可为 ""（brief 写 assert body.get(...)；空串为假，故显式比空）
        assert body.get("uncovered_pages_hint", "") == ""
        with sync_session() as s:
            parent = s.get(ExamPaper, pid)
            assert parent.anthology_split_status == "done"
            child = s.get(ExamPaper, body["new_papers"][0]["id"])
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
                                {"order_index": 1, "qtype": "填空", "stem": "a", "options": [], "blocks": []},
                                {"order_index": 1, "qtype": "填空", "stem": "b", "options": [], "blocks": []},
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

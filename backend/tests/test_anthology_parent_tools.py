# backend/tests/test_anthology_parent_tools.py
from fastapi.testclient import TestClient

from app.agent.tools import (
    generate_all_practice_pdfs,
    generate_chunk_practice_pdf,
    generate_chunk_practice_pdfs_batch,
    run_knowledge_analysis,
)
from app.db.models import ExamPaper
from app.db.sync_session import sync_session
from app.main import app
from app.services.anthology_ranges import ANTHOLOGY_PARENT_DONE_TOOLS


def _paper(cid: str, status: str, **kwargs) -> str:
    with sync_session() as s:
        p = ExamPaper(
            conversation_id=cid,
            source_type="pdf",
            anthology_split_status=status,
            parsed_json=kwargs.get("parsed_json")
            or {
                "title": "t",
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
            structured_confirm_status=kwargs.get("structured_confirm_status", "confirmed"),
            alignment_json=kwargs.get("alignment_json")
            or {"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
            knowledge_analysis_json=kwargs.get("knowledge_analysis_json"),
        )
        s.add(p)
        s.commit()
        return p.id


def test_tools_refuse_anthology_parent_done():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pid = _paper(cid, "done")
        out = run_knowledge_analysis.invoke({"paper_id": pid})
        assert out == ANTHOLOGY_PARENT_DONE_TOOLS
        out2 = generate_chunk_practice_pdf.invoke(
            {"paper_id": pid, "knowledge_point_key": "x"}
        )
        assert out2 == ANTHOLOGY_PARENT_DONE_TOOLS
        out3 = generate_chunk_practice_pdfs_batch.invoke(
            {"paper_id": pid, "items_json": "[]"}
        )
        assert out3 == ANTHOLOGY_PARENT_DONE_TOOLS
        out4 = generate_all_practice_pdfs.invoke({"paper_id": pid})
        assert out4 == ANTHOLOGY_PARENT_DONE_TOOLS


def test_tools_allow_child_none_past_gate():
    """none 子本不应被父本文案挡住；可因缺考点分析等返回其它提示。"""
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pid = _paper(cid, "none", knowledge_analysis_json=None)
        out = generate_chunk_practice_pdf.invoke(
            {"paper_id": pid, "knowledge_point_key": "x"}
        )
        assert out != ANTHOLOGY_PARENT_DONE_TOOLS
        assert "考点" in out or "分析" in out

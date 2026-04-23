"""批量出题工具：条数上限与 JSON 校验（不调用 LLM）。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.agent.tools import generate_chunk_practice_pdfs_batch
from app.config import settings


@pytest.fixture
def cap2(monkeypatch):
    monkeypatch.setattr(settings, "practice_batch_max_knowledge_points", 2)


def _ka_json():
    return {
        "theme_title": "测",
        "knowledge_points": [
            {"key": "a", "name": "A", "summary": "s", "book_chapter_hint": "通用"},
            {"key": "b", "name": "B", "summary": "s", "book_chapter_hint": "通用"},
            {"key": "c", "name": "C", "summary": "s", "book_chapter_hint": "通用"},
        ],
        "mappings": [
            {"question_order": 1, "knowledge_point_key": "a"},
        ],
    }


def test_batch_rejects_over_cap(cap2):
    paper = MagicMock()
    paper.knowledge_analysis_json = _ka_json()
    mock_session = MagicMock()
    mock_session.get.return_value = paper

    class _CM:
        def __enter__(self):
            return mock_session

        def __exit__(self, *args):
            return None

    items = json.dumps(
        [
            {"knowledge_point_key": "a"},
            {"knowledge_point_key": "b"},
            {"knowledge_point_key": "c"},
        ]
    )
    with patch("app.agent.tools.sync_session", return_value=_CM()):
        out = generate_chunk_practice_pdfs_batch.invoke(
            {"paper_id": "p1", "items_json": items}
        )
    assert "一次最多 2 个" in str(out)


def test_batch_accepts_at_cap(cap2):
    paper = MagicMock()
    paper.knowledge_analysis_json = _ka_json()
    mock_session = MagicMock()
    mock_session.get.return_value = paper

    class _CM:
        def __enter__(self):
            return mock_session

        def __exit__(self, *args):
            return None

    items = json.dumps(
        [
            {"knowledge_point_key": "a", "question_count": 1},
            {"knowledge_point_key": "b", "question_count": 1},
        ]
    )
    with (
        patch("app.agent.tools.sync_session", return_value=_CM()),
        patch(
            "app.agent.tools._generate_chunk_practice_pdf_for_kp", return_value=None
        ) as gen,
    ):
        out = generate_chunk_practice_pdfs_batch.invoke(
            {"paper_id": "p1", "items_json": items}
        )
    assert gen.call_count == 2
    assert "批量结果" in str(out)
    assert "A" in str(out) and "B" in str(out)

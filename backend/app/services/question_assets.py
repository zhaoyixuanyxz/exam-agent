"""V2.2：从已确认的结构化试卷生成题目资产行。"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ExamPaper, QuestionAsset
from app.db.sync_session import sync_session
from app.models.schemas import KnowledgeAnalysisResult, StructuredPaper
from app.db.v23_ids import DEFAULT_USER_ID
from app.services.knowledge_sync import (
    delete_links_for_asset_ids,
    link_asset_to_knowledge,
)


def knowledge_keys_by_question_order(paper: ExamPaper) -> dict[int, list[str]]:
    raw = paper.knowledge_analysis_json
    if not raw or not isinstance(raw, dict):
        return {}
    try:
        ka = KnowledgeAnalysisResult.model_validate(raw)
    except Exception:
        return {}
    out: dict[int, list[str]] = defaultdict(list)
    for m in ka.mappings:
        out[int(m.question_order)].append(str(m.knowledge_point_key))
    return {k: list(dict.fromkeys(v)) for k, v in out.items()}


def alignment_snapshot(paper: ExamPaper) -> dict[str, Any] | None:
    a = paper.alignment_json
    if not a or not isinstance(a, dict):
        return None
    return dict(a)


def _content_fingerprint(stem: str, options: list[str] | None) -> str:
    norm = f"{(stem or '').strip()}\n{json.dumps(list(options or []), ensure_ascii=True)}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def _alignment_labels(paper: ExamPaper) -> tuple[str | None, str | None]:
    a = paper.alignment_json
    if not a or not isinstance(a, dict):
        return None, None
    gmin = str(a.get("grade_min") or "").strip()
    gmax = str(a.get("grade_max") or "").strip()
    grade = f"{gmin}~{gmax}".strip("~") if (gmin or gmax) else None
    subj = str(a.get("subject") or "").strip() or None
    return grade, subj


def build_question_asset_rows_for_paper(paper: ExamPaper) -> list[dict[str, Any]]:
    """从 ExamPaper 内存字段构造待插入的题目行（不写库）。"""
    if not paper.parsed_json:
        return []
    sp = StructuredPaper.model_validate(paper.parsed_json)
    kp_by_order = knowledge_keys_by_question_order(paper)
    align_snap = alignment_snapshot(paper)
    g_lab, s_lab = _alignment_labels(paper)
    source_name = (paper.display_name or "").strip() or None
    sv = int(paper.structured_version or 0)
    rows: list[dict[str, Any]] = []
    for sec in sp.sections:
        sec_title = (sec.title or "").strip()
        for q in sec.questions:
            oid = int(q.order_index)
            opts = list(q.options) if q.options else []
            stem = (q.stem or "").strip()
            fp = _content_fingerprint(stem, opts)
            rows.append(
                {
                    "conversation_id": paper.conversation_id,
                    "paper_id": paper.id,
                    "structured_version": sv,
                    "question_order": oid,
                    "section_title": sec_title,
                    "qtype": (q.qtype or "").strip(),
                    "stem": stem,
                    "options_json": opts,
                    "knowledge_point_keys_json": kp_by_order.get(oid, []),
                    "alignment_snapshot_json": align_snap,
                    "content_fingerprint": fp,
                    "answer": (q.answer or "").strip() if q.answer is not None else None,
                    "explanation": (q.explanation or "").strip() if q.explanation is not None else None,
                    "difficulty": (q.difficulty or "").strip() if q.difficulty is not None else None,
                    "textbook_version": (q.textbook_version or "").strip()
                    if q.textbook_version is not None
                    else None,
                    "chapter_path": (q.chapter_path or "").strip() if q.chapter_path is not None else None,
                    "grade_label": g_lab,
                    "subject_label": s_lab,
                    "source_paper_name": source_name,
                },
            )
    return rows


def rebuild_question_assets_for_paper_sync(session: Session, paper: ExamPaper) -> int:
    """
    用当前 structured_version 覆盖该卷对应版本的题目资产行（幂等）。
    调用方需保证 paper 已结构化确认且 parsed_json 合法。
    """
    sv = int(paper.structured_version or 0)
    to_del = list(
        session.scalars(
            select(QuestionAsset.id).where(
                QuestionAsset.paper_id == paper.id,
                QuestionAsset.structured_version == sv,
            )
        ).all()
    )
    delete_links_for_asset_ids(session, [str(x) for x in to_del])
    session.execute(
        delete(QuestionAsset).where(
            QuestionAsset.paper_id == paper.id,
            QuestionAsset.structured_version == sv,
        ),
    )
    payloads = build_question_asset_rows_for_paper(paper)
    now = datetime.utcnow()
    for pl in payloads:
        qid = str(uuid.uuid4())
        qa = QuestionAsset(
            id=qid,
            business_id=qid,
            conversation_id=pl["conversation_id"],
            paper_id=pl["paper_id"],
            structured_version=pl["structured_version"],
            question_order=pl["question_order"],
            section_title=pl["section_title"],
            qtype=pl["qtype"],
            stem=pl["stem"],
            options_json=pl["options_json"],
            knowledge_point_keys_json=pl["knowledge_point_keys_json"],
            alignment_snapshot_json=pl["alignment_snapshot_json"],
            content_fingerprint=pl.get("content_fingerprint") or "",
            answer=pl.get("answer"),
            explanation=pl.get("explanation"),
            difficulty=pl.get("difficulty"),
            textbook_version=pl.get("textbook_version"),
            chapter_path=pl.get("chapter_path"),
            grade_label=pl.get("grade_label"),
            subject_label=pl.get("subject_label"),
            source_paper_name=pl.get("source_paper_name"),
            quality_status="pending",
            review_status="pending_review",
            owner_user_id=DEFAULT_USER_ID,
            created_at=now,
            updated_at=now,
        )
        session.add(qa)
        session.flush()
        link_asset_to_knowledge(
            session,
            qa,
            paper,
            list(pl.get("knowledge_point_keys_json") or []),
        )
    return len(payloads)


def rebuild_question_assets_for_paper_id(paper_id: str) -> int:
    """同步会话：按主键加载试卷并重建题目资产。未确认或无结构化时返回 0。"""
    with sync_session() as session:
        paper = session.get(ExamPaper, paper_id)
        if not paper:
            return 0
        if (paper.structured_confirm_status or "") != "confirmed":
            return 0
        if not paper.parsed_json:
            return 0
        try:
            StructuredPaper.model_validate(paper.parsed_json)
        except Exception:
            return 0
        n = rebuild_question_assets_for_paper_sync(session, paper)
        session.commit()
        return n


def list_question_assets_for_paper_version(
    session: Session,
    paper_id: str,
    structured_version: int,
) -> list[QuestionAsset]:
    r = session.execute(
        select(QuestionAsset)
        .where(
            QuestionAsset.paper_id == paper_id,
            QuestionAsset.structured_version == structured_version,
        )
        .order_by(QuestionAsset.question_order),
    )
    return list(r.scalars().all())


def load_question_assets_or_build(
    session: Session,
    paper: ExamPaper,
) -> list[QuestionAsset]:
    """优先读库；若无行且已确认，则当场重建并返回。"""
    sv = int(paper.structured_version or 0)
    rows = list_question_assets_for_paper_version(session, paper.id, sv)
    if rows:
        return rows
    if (paper.structured_confirm_status or "") != "confirmed" or not paper.parsed_json:
        return []
    try:
        StructuredPaper.model_validate(paper.parsed_json)
    except Exception:
        return []
    rebuild_question_assets_for_paper_sync(session, paper)
    session.commit()
    return list_question_assets_for_paper_version(session, paper.id, sv)

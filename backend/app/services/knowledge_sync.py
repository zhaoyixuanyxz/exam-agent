"""V2.3：从考点分析结果同步标准考点主数据与题目关联。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    ExamPaper,
    KnowledgeKeyMapping,
    KnowledgePointCanonical,
    QuestionAsset,
    QuestionKnowledgeLink,
)
from app.db.v23_ids import DEFAULT_USER_ID
from app.models.schemas import KnowledgeAnalysisResult


def _get_ka(paper: ExamPaper) -> KnowledgeAnalysisResult | None:
    raw = paper.knowledge_analysis_json
    if not raw or not isinstance(raw, dict):
        return None
    try:
        return KnowledgeAnalysisResult.model_validate(raw)
    except Exception:
        return None


def _kp_meta_for_key(ka: KnowledgeAnalysisResult, key: str) -> dict[str, Any]:
    for kp in ka.knowledge_points:
        if kp.key == key:
            return {
                "name": kp.name or key,
                "chapter": (kp.book_chapter_hint or "").strip(),
            }
    return {"name": key, "chapter": ""}


def ensure_knowledge_key_mapping(
    session: Session, paper: ExamPaper, raw_key: str, default_user_id: str = DEFAULT_USER_ID
) -> str:
    """将 raw key 归并到标准考点，返回 knowledge_point_id。"""
    raw_key = (raw_key or "").strip()
    if not raw_key:
        return ""
    existing = session.execute(
        select(KnowledgeKeyMapping).where(KnowledgeKeyMapping.raw_key == raw_key)
    ).scalar_one_or_none()
    if existing:
        return str(existing.knowledge_point_id)

    ka = _get_ka(paper)
    if not ka:
        # 无考点分析时仍建占位标准考点
        name = raw_key
        chapter = None
    else:
        meta = _kp_meta_for_key(ka, raw_key)
        name = str(meta.get("name") or raw_key)
        chapter = meta.get("chapter") or None

    std_key = raw_key
    kpc = session.execute(
        select(KnowledgePointCanonical).where(KnowledgePointCanonical.standard_key == std_key)
    ).scalar_one_or_none()
    if not kpc:
        a = paper.alignment_json or {}
        subj = str(a.get("subject") or "") if isinstance(a, dict) else None
        gmin = str(a.get("grade_min") or "") if isinstance(a, dict) else None
        gmax = str(a.get("grade_max") or "") if isinstance(a, dict) else None
        kpc = KnowledgePointCanonical(
            id=str(uuid.uuid4()),
            standard_key=std_key,
            name=name,
            aliases_json=[],
            chapter_path=chapter,
            subject=subj,
            grade_min=gmin,
            grade_max=gmax,
        )
        session.add(kpc)
        session.flush()
    else:
        if name and (not (kpc.name or "").strip() or (kpc.name or "").strip() == (kpc.standard_key or "").strip()):
            kpc.name = name
        if chapter and not (kpc.chapter_path or "").strip():
            kpc.chapter_path = chapter

    km = KnowledgeKeyMapping(
        id=str(uuid.uuid4()),
        raw_key=raw_key,
        knowledge_point_id=str(kpc.id),
    )
    session.add(km)
    session.flush()
    return str(kpc.id)


def delete_links_for_asset_ids(session: Session, asset_ids: list[str]) -> None:
    if not asset_ids:
        return
    session.execute(
        delete(QuestionKnowledgeLink).where(QuestionKnowledgeLink.question_asset_id.in_(asset_ids))
    )


def link_asset_to_knowledge(
    session: Session,
    asset: QuestionAsset,
    paper: ExamPaper,
    raw_keys: list[str],
) -> None:
    for rk in raw_keys:
        if not (rk or "").strip():
            continue
        kpid = ensure_knowledge_key_mapping(session, paper, str(rk).strip())
        if not kpid:
            continue
        ex = session.execute(
            select(QuestionKnowledgeLink).where(
                QuestionKnowledgeLink.question_asset_id == asset.id,
                QuestionKnowledgeLink.knowledge_point_id == kpid,
            )
        ).scalar_one_or_none()
        if ex:
            ex.raw_key = str(rk).strip()
            continue
        session.add(
            QuestionKnowledgeLink(
                id=str(uuid.uuid4()),
                question_asset_id=asset.id,
                knowledge_point_id=kpid,
                raw_key=str(rk).strip(),
            )
        )


def backfill_default_owner_for_question_assets(session: Session) -> None:
    if not session.get(AppUser, DEFAULT_USER_ID):
        return
    for row in session.execute(
        select(QuestionAsset).where(QuestionAsset.owner_user_id.is_(None))
    ).scalars():
        row.owner_user_id = DEFAULT_USER_ID

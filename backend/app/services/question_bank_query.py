"""V2.3：题库列表、详情与更新。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, QuestionAsset, QuestionKnowledgeLink
from app.models.schemas import QuestionAssetDTO


def _dt_iso(t: datetime | None) -> str | None:
    if t is None:
        return None
    if hasattr(t, "isoformat"):
        return t.isoformat()
    return str(t)


def load_kp_ids_for_assets(session: Session, asset_ids: list[str]) -> dict[str, list[str]]:
    if not asset_ids:
        return {}
    r = session.execute(
        select(
            QuestionKnowledgeLink.question_asset_id,
            QuestionKnowledgeLink.knowledge_point_id,
        ).where(QuestionKnowledgeLink.question_asset_id.in_(asset_ids))
    )
    out: dict[str, list[str]] = {i: [] for i in asset_ids}
    for aid, kpid in r.all():
        out.setdefault(str(aid), []).append(str(kpid))
    return out


def question_asset_to_dto(session: Session, row: QuestionAsset) -> QuestionAssetDTO:
    kp_map = load_kp_ids_for_assets(session, [str(row.id)])
    kp_ids = kp_map.get(str(row.id), [])
    return QuestionAssetDTO(
        id=row.id,
        business_id=row.business_id or row.id,
        paper_id=row.paper_id,
        conversation_id=row.conversation_id,
        structured_version=int(row.structured_version or 0),
        question_order=int(row.question_order),
        section_title=row.section_title or "",
        qtype=row.qtype or "",
        stem=row.stem or "",
        options=list(row.options_json or []),
        knowledge_point_keys=list(row.knowledge_point_keys_json or []),
        knowledge_point_ids=kp_ids,
        alignment_snapshot=row.alignment_snapshot_json,
        content_fingerprint=row.content_fingerprint or "",
        answer=row.answer,
        explanation=row.explanation,
        difficulty=row.difficulty,
        textbook_version=row.textbook_version,
        chapter_path=row.chapter_path,
        grade_label=row.grade_label,
        subject_label=row.subject_label,
        source_paper_name=row.source_paper_name,
        quality_status=row.quality_status or "pending",
        review_status=row.review_status or "pending_review",
        created_at=_dt_iso(row.created_at),
        updated_at=_dt_iso(row.updated_at),
    )


def _scope_filter(user: AppUser) -> Any:
    if (user.role or "") == "admin":
        return None
    return or_(
        QuestionAsset.owner_user_id == str(user.id),
        QuestionAsset.owner_user_id.is_(None),
        QuestionAsset.visibility == "public",
    )


def _build_list_stmt(
    user: AppUser,
    q: str | None = None,
    subject: str | None = None,
    grade: str | None = None,
    qtype: str | None = None,
    knowledge_point_id: str | None = None,
    chapter: str | None = None,
    source: str | None = None,
    quality: str | None = None,
    review: str | None = None,
    conversation_id: str | None = None,
    sort: str = "created_desc",
) -> Any:
    stmt = select(QuestionAsset)
    sf = _scope_filter(user)
    if sf is not None:
        stmt = stmt.where(sf)
    if conversation_id:
        stmt = stmt.where(QuestionAsset.conversation_id == conversation_id)
    if q and str(q).strip():
        t = f"%{str(q).strip()}%"
        stmt = stmt.where(
            (QuestionAsset.stem.ilike(t)) | (QuestionAsset.stem.like(t))  # type: ignore[operator]
        )
    if subject and str(subject).strip():
        stmt = stmt.where(QuestionAsset.subject_label == str(subject).strip())
    if grade and str(grade).strip():
        g = f"%{str(grade).strip()}%"
        stmt = stmt.where(
            (QuestionAsset.grade_label.ilike(g)) | (QuestionAsset.grade_label.like(g))  # type: ignore[operator]
        )
    if qtype and str(qtype).strip():
        stmt = stmt.where(QuestionAsset.qtype == str(qtype).strip())
    if quality and str(quality).strip():
        stmt = stmt.where(QuestionAsset.quality_status == str(quality).strip())
    if review and str(review).strip():
        stmt = stmt.where(QuestionAsset.review_status == str(review).strip())
    if chapter and str(chapter).strip():
        c = f"%{str(chapter).strip()}%"
        stmt = stmt.where(
            (QuestionAsset.chapter_path.ilike(c)) | (QuestionAsset.chapter_path.like(c))  # type: ignore[operator]
        )
    if source and str(source).strip():
        c = f"%{str(source).strip()}%"
        stmt = stmt.where(
            (QuestionAsset.source_paper_name.ilike(c))  # type: ignore[operator]
            | (QuestionAsset.source_paper_name.like(c))  # type: ignore[operator]
        )
    if knowledge_point_id and str(knowledge_point_id).strip():
        kid = str(knowledge_point_id).strip()
        sub = select(QuestionKnowledgeLink.question_asset_id).where(
            QuestionKnowledgeLink.knowledge_point_id == kid
        )
        stmt = stmt.where(QuestionAsset.id.in_(sub))

    if sort == "created_asc":
        stmt = stmt.order_by(QuestionAsset.created_at.asc().nulls_last(), QuestionAsset.id.asc())
    elif sort == "updated_desc":
        stmt = stmt.order_by(QuestionAsset.updated_at.desc().nulls_last(), QuestionAsset.id.desc())
    else:
        stmt = stmt.order_by(QuestionAsset.created_at.desc().nulls_last(), QuestionAsset.id.desc())
    return stmt


def list_questions(
    session: Session,
    *,
    user: AppUser,
    page: int = 1,
    page_size: int = 20,
    **filters: Any,
) -> tuple[list[QuestionAsset], int]:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 20)))
    stmt = _build_list_stmt(
        user,
        q=filters.get("q"),
        subject=filters.get("subject"),
        grade=filters.get("grade"),
        qtype=filters.get("qtype"),
        knowledge_point_id=filters.get("knowledge_point_id"),
        chapter=filters.get("chapter"),
        source=filters.get("source"),
        quality=filters.get("quality"),
        review=filters.get("review"),
        conversation_id=filters.get("conversation_id"),
        sort=filters.get("sort") or "created_desc",
    )
    all_rows = list(session.execute(stmt).scalars().all())
    total = len(all_rows)
    start = (page - 1) * page_size
    return all_rows[start : start + page_size], total

"""V2.3 标准考点主数据只读/归并。"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeKeyMapping, KnowledgePointCanonical, QuestionKnowledgeLink
from app.db.sync_session import sync_session
from app.db.v23_ids import DEFAULT_USER_ID
from app.models.schemas import KnowledgePointCanonicalDTO, KnowledgePointListResponse
from app.services.audit_log import log_action

router = APIRouter(prefix="/api", tags=["knowledge-master"])


@router.get("/knowledge-master", response_model=KnowledgePointListResponse)
def list_knowledge_points(
    subject: str | None = None,
    page: int = 1,
    page_size: int = 200,
) -> KnowledgePointListResponse:
    with sync_session() as s:
        stmt = select(KnowledgePointCanonical)
        if subject and str(subject).strip():
            subj = str(subject).strip()
            stmt = stmt.where(
                (KnowledgePointCanonical.subject == subj) | (KnowledgePointCanonical.subject.is_(None))  # type: ignore[operator]
            )
        all_rows = list(
            s.execute(stmt.order_by(KnowledgePointCanonical.name.asc().nulls_last())).scalars().all()
        )
        total = len(all_rows)
        page = max(1, page)
        ps = min(200, max(1, page_size))
        chunk = all_rows[(page - 1) * ps : (page - 1) * ps + ps]
        items = [
            KnowledgePointCanonicalDTO(
                id=str(r.id),
                standard_key=r.standard_key,
                name=r.name or "",
                aliases=list(r.aliases_json or []),
                chapter_path=r.chapter_path,
                subject=r.subject,
                grade_min=r.grade_min,
                grade_max=r.grade_max,
            )
            for r in chunk
        ]
    return KnowledgePointListResponse(items=items, total=total)


class MergeKpBody(BaseModel):
    from_raw_key: str = Field(..., min_length=1, description="原始 LLM 考点 key")
    to_knowledge_point_id: str = Field(..., min_length=1, description="目标标准考点 id")


@router.post("/knowledge-master/merge-alias")
def merge_alias(
    body: MergeKpBody,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> dict:
    uid = (x_user_id or DEFAULT_USER_ID).strip()
    with sync_session() as s:
        kpc = s.get(KnowledgePointCanonical, body.to_knowledge_point_id)
        if not kpc:
            raise HTTPException(400, "target canonical not found")
        raw = body.from_raw_key.strip()
        m = s.execute(
            select(KnowledgeKeyMapping).where(KnowledgeKeyMapping.raw_key == raw)
        ).scalar_one_or_none()
        if m:
            m.knowledge_point_id = str(kpc.id)
        else:
            s.add(
                KnowledgeKeyMapping(
                    id=str(uuid.uuid4()),
                    raw_key=raw,
                    knowledge_point_id=str(kpc.id),
                )
            )
        links = list(
            s.execute(
                select(QuestionKnowledgeLink).where(
                    QuestionKnowledgeLink.raw_key == raw,
                )
            ).scalars().all()
        )
        for ln in links:
            ln.knowledge_point_id = str(kpc.id)
        log_action(
            s,
            user_id=uid,
            action="knowledge.merge",
            resource_type="knowledge_point",
            resource_id=str(kpc.id),
            detail={"from_raw_key": raw},
        )
        s.commit()
        kpid = str(kpc.id)
    return {"ok": True, "knowledge_point_id": kpid}

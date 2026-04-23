"""人工纠错、审核字段更新。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import KnowledgePointCanonical, QuestionAsset, QuestionKnowledgeLink
from app.models.schemas import QuestionAssetPatchRequest
from app.services.audit_log import log_action


def apply_question_patch(
    session: Session,
    *,
    qa: QuestionAsset,
    body: QuestionAssetPatchRequest,
    actor_user_id: str,
) -> None:
    if body.qtype is not None:
        qa.qtype = str(body.qtype)
    if body.difficulty is not None:
        qa.difficulty = body.difficulty
    if body.chapter_path is not None:
        qa.chapter_path = body.chapter_path
    if body.quality_status is not None:
        qa.quality_status = str(body.quality_status)
    if body.review_status is not None:
        qa.review_status = str(body.review_status)
    if body.answer is not None:
        qa.answer = body.answer
    if body.explanation is not None:
        qa.explanation = body.explanation
    if body.knowledge_point_ids is not None:
        session.execute(
            delete(QuestionKnowledgeLink).where(QuestionKnowledgeLink.question_asset_id == qa.id)
        )
        for kpid in body.knowledge_point_ids:
            kpc = session.get(KnowledgePointCanonical, str(kpid).strip())
            if not kpc:
                continue
            session.add(
                QuestionKnowledgeLink(
                    id=str(uuid.uuid4()),
                    question_asset_id=qa.id,
                    knowledge_point_id=str(kpc.id),
                    raw_key="manual",
                )
            )
    qa.updated_at = datetime.utcnow()
    log_action(
        session,
        user_id=actor_user_id,
        action="question.patch",
        resource_type="question_asset",
        resource_id=qa.id,
        detail=body.model_dump(exclude_unset=True),
    )

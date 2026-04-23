"""V2.3 题库列表、详情、纠错。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Header, Query

from app.api.deps import get_or_ensure_user
from app.db.models import AppUser, QuestionAsset
from app.db.v23_ids import DEFAULT_USER_ID
from app.db.sync_session import sync_session
from app.models.schemas import (
    QuestionAssetDTO,
    QuestionAssetPatchRequest,
    QuestionBankListResponse,
)
from app.services.question_bank_query import list_questions, question_asset_to_dto
from app.services.question_patch import apply_question_patch

router = APIRouter(prefix="/api", tags=["question-bank"])


@router.get("/question-bank", response_model=QuestionBankListResponse)
def get_question_bank(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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
) -> QuestionBankListResponse:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        user: AppUser = get_or_ensure_user(s, uid)
        rows, total = list_questions(
            s,
            user=user,
            page=page,
            page_size=page_size,
            q=q,
            subject=subject,
            grade=grade,
            qtype=qtype,
            knowledge_point_id=knowledge_point_id,
            chapter=chapter,
            source=source,
            quality=quality,
            review=review,
            conversation_id=conversation_id,
            sort=sort,
        )
        items = [question_asset_to_dto(s, r) for r in rows]
    return QuestionBankListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/question-bank/{asset_id}", response_model=QuestionAssetDTO)
def get_question_detail(
    asset_id: str,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> QuestionAssetDTO:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        user: AppUser = get_or_ensure_user(s, uid)
        row = s.get(QuestionAsset, asset_id)
        if not row:
            raise HTTPException(404, "not found")
        if (user.role or "") != "admin" and (row.visibility or "own") != "public":
            if row.owner_user_id and str(row.owner_user_id) not in (str(user.id), str(DEFAULT_USER_ID)):
                raise HTTPException(403, "forbidden")
        return question_asset_to_dto(s, row)


@router.patch("/question-bank/{asset_id}", response_model=QuestionAssetDTO)
def patch_question(
    asset_id: str,
    body: QuestionAssetPatchRequest,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> QuestionAssetDTO:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        user: AppUser = get_or_ensure_user(s, uid)
        qa = s.get(QuestionAsset, asset_id)
        if not qa:
            raise HTTPException(404, "not found")
        if (user.role or "") not in ("admin", "researcher"):
            o = qa.owner_user_id
            if o and str(o) not in (str(user.id), str(DEFAULT_USER_ID)):
                raise HTTPException(403, "forbidden")
        apply_question_patch(s, qa=qa, body=body, actor_user_id=uid)
        s.commit()
        s.refresh(qa)
        return question_asset_to_dto(s, qa)

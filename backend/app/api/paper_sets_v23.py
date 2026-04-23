"""V2.3 题单/组卷篮/组卷起步。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException

from app.api.deps import get_or_ensure_user
from app.db.models import AppUser, Conversation, PaperSet
from app.db.v23_ids import DEFAULT_USER_ID
from app.db.sync_session import sync_session
from app.models.schemas import (
    CompilePaperRequest,
    CompilePaperResponse,
    PaperSetAddItemsRequest,
    PaperSetCreateRequest,
    PaperSetDetailDTO,
    PaperSetDTO,
)
from app.services.audit_log import log_action
from app.services.paper_set_ops import (
    add_items,
    compile_paper,
    create_paper_set,
    get_detail,
    list_paper_sets,
    paper_set_to_dto,
)

router = APIRouter(prefix="/api", tags=["paper-sets"])


@router.get("/conversations/{conversation_id}/paper-sets", response_model=list[PaperSetDTO])
def list_sets(
    conversation_id: str,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> list[PaperSetDTO]:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        user: AppUser = get_or_ensure_user(s, uid)
        if not s.get(Conversation, conversation_id):
            raise HTTPException(404, "conversation not found")
        pss = list_paper_sets(s, conversation_id, user)
        return [paper_set_to_dto(s, ps) for ps in pss]


@router.post("/conversations/{conversation_id}/paper-sets", response_model=PaperSetDTO)
def create_set(
    conversation_id: str,
    body: PaperSetCreateRequest,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> PaperSetDTO:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        user = get_or_ensure_user(s, uid)
        if not s.get(Conversation, conversation_id):
            raise HTTPException(404, "conversation not found")
        ps = create_paper_set(
            s, conversation_id, body.name, user, body.config_json or {}
        )
        return paper_set_to_dto(s, ps)


@router.get(
    "/conversations/{conversation_id}/paper-sets/{set_id}",
    response_model=PaperSetDetailDTO,
)
def get_set(
    conversation_id: str,
    set_id: str,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> PaperSetDetailDTO:
    _ = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        ps = s.get(PaperSet, set_id)
        if not ps or str(ps.conversation_id) != str(conversation_id):
            raise HTTPException(404, "not found")
        d = get_detail(s, set_id)
        if not d:
            raise HTTPException(404, "not found")
    return d


@router.post("/paper-sets/{set_id}/items", response_model=dict)
def add_to_set(
    set_id: str,
    body: PaperSetAddItemsRequest,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> dict:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        user = get_or_ensure_user(s, uid)
        ps = s.get(PaperSet, set_id)
        if not ps:
            raise HTTPException(404, "set not found")
        if (user.role or "") != "admin" and ps.owner_user_id and str(ps.owner_user_id) not in (
            str(user.id),
            str(DEFAULT_USER_ID),
        ):
            raise HTTPException(403, "forbidden")
        n = add_items(s, set_id, body)
        log_action(
            s,
            user_id=uid,
            action="paper_set.add_items",
            resource_type="paper_set",
            resource_id=set_id,
            detail={"count": n},
        )
        s.commit()
    return {"added": n}


@router.post("/compile-paper", response_model=CompilePaperResponse)
def post_compile_paper(
    body: CompilePaperRequest,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> CompilePaperResponse:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        user = get_or_ensure_user(s, uid)
        return compile_paper(s, user, body)

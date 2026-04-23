"""V2.3 用户与审计日志。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from app.api.deps import get_or_ensure_user
from app.db.models import AppUser, AuditLog
from app.db.v23_ids import DEFAULT_USER_ID
from app.db.sync_session import sync_session
from app.models.schemas import AppUserDTO, AuditLogEntryDTO

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=AppUserDTO)
def get_me(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> AppUserDTO:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        u: AppUser = get_or_ensure_user(s, uid)
        return AppUserDTO(
            id=u.id,
            display_name=u.display_name or "",
            role=str(u.role or "teacher"),
            data_scope=str(u.data_scope_default or "own"),
        )


@router.get("/audit-logs", response_model=list[AuditLogEntryDTO])
def list_audit(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    limit: int = 200,
) -> list[AuditLogEntryDTO]:
    uid = (x_user_id or "").strip() or DEFAULT_USER_ID
    with sync_session() as s:
        u = get_or_ensure_user(s, uid)
        if (u.role or "") != "admin":
            raise HTTPException(403, "admin only")
        q = list(
            s.execute(
                select(AuditLog)
                .order_by(AuditLog.created_at.desc().nulls_last())
                .limit(min(1000, max(1, int(limit or 200))))
            )
            .scalars()
            .all()
        )
    out: list[AuditLogEntryDTO] = []
    for a in q:
        out.append(
            AuditLogEntryDTO(
                id=a.id,
                user_id=a.user_id,
                action=a.action,
                resource_type=a.resource_type,
                resource_id=a.resource_id or "",
                detail_json=a.detail_json or {},
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
        )
    return out

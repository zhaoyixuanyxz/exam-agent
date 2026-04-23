"""V2.3：用户与同步会话辅助。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser
from app.db.v23_ids import DEFAULT_USER_ID
from app.db.sync_session import sync_session


def header_user_id(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    return (x_user_id or "").strip() or DEFAULT_USER_ID


def get_user_by_id_str(session: Session, user_id: str) -> AppUser | None:
    r = session.execute(select(AppUser).where(AppUser.id == str(user_id).strip()))
    return r.scalars().first()


def get_or_ensure_user(session: Session, user_id: str) -> AppUser:
    u = get_user_by_id_str(session, user_id)
    if u:
        return u
    u = AppUser(
        id=str(user_id).strip(),
        display_name="用户",
        role="teacher",
        data_scope_default="own",
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def load_user_for_request(user_id_str: str) -> AppUser:
    with sync_session() as s:
        u = get_user_by_id_str(s, user_id_str)
        if u:
            return u
    raise HTTPException(401, "user not found; use default or create user first")

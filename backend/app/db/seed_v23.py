"""V2.3 启动种子：默认用户等。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.models import AppUser
from app.db.session import SessionLocal
from app.db.sync_session import sync_session
from app.db.v23_ids import DEFAULT_USER_ID


async def ensure_v23_seed_data(db_engine: AsyncEngine | None = None) -> None:
    _ = db_engine
    async with SessionLocal() as session:
        await _ensure_default_user(session)
    from app.services.knowledge_sync import backfill_default_owner_for_question_assets

    with sync_session() as s:
        backfill_default_owner_for_question_assets(s)
        s.commit()


async def _ensure_default_user(session: AsyncSession) -> None:
    r = await session.execute(select(AppUser).where(AppUser.id == DEFAULT_USER_ID))
    if r.scalar_one_or_none() is not None:
        return
    session.add(
        AppUser(
            id=DEFAULT_USER_ID,
            display_name="默认用户",
            role="admin",
            data_scope_default="own",
        )
    )
    await session.commit()

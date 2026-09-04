import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


def _normalize_database_url(url: str) -> str:
    """Accept postgres:// / postgresql:// and force the asyncpg driver."""
    u = url.strip()
    if u.startswith("postgres://"):
        u = "postgresql+asyncpg://" + u[len("postgres://") :]
    elif u.startswith("postgresql://"):
        u = "postgresql+asyncpg://" + u[len("postgresql://") :]
    elif u.startswith("postgresql+psycopg2://"):
        u = "postgresql+asyncpg://" + u[len("postgresql+psycopg2://") :]
    return u


def _database_url() -> str:
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if raw:
        return _normalize_database_url(raw)
    test_db = os.getenv("EXAM_AGENT_TEST_DB_PATH")
    if test_db:
        return f"sqlite+aiosqlite:///{test_db}"
    return f"sqlite+aiosqlite:///{settings.db_path.as_posix()}"


DATABASE_URL = _database_url()
_IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# Serverless (Vercel/Neon): NullPool avoids holding connections across frozen instances.
_engine_kwargs: dict = {"echo": False}
if _IS_POSTGRES:
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

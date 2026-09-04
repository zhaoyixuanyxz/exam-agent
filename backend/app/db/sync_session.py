import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def _normalize_sync_url(url: str) -> str:
    u = url.strip()
    if u.startswith("postgres://"):
        u = "postgresql+psycopg2://" + u[len("postgres://") :]
    elif u.startswith("postgresql://"):
        u = "postgresql+psycopg2://" + u[len("postgresql://") :]
    elif u.startswith("postgresql+asyncpg://"):
        u = "postgresql+psycopg2://" + u[len("postgresql+asyncpg://") :]
    elif u.startswith("postgresql+psycopg://"):
        u = "postgresql+psycopg2://" + u[len("postgresql+psycopg://") :]
    return u


def _sync_database_url() -> str:
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if raw:
        return _normalize_sync_url(raw)
    test_db = os.getenv("EXAM_AGENT_TEST_DB_PATH")
    if test_db:
        return f"sqlite:///{test_db}"
    return f"sqlite:///{settings.db_path.as_posix()}"


_sync_url = _sync_database_url()
_is_postgres = _sync_url.startswith("postgresql")

if _is_postgres:
    sync_engine = create_engine(_sync_url, poolclass=NullPool, pool_pre_ping=True, echo=False)
else:
    sync_engine = create_engine(
        _sync_url, connect_args={"check_same_thread": False}, echo=False
    )

SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def sync_session() -> Session:
    return SyncSessionLocal()

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

_test_db = os.getenv("EXAM_AGENT_TEST_DB_PATH")
if _test_db:
    DATABASE_URL = f"sqlite+aiosqlite:///{_test_db}"
else:
    DATABASE_URL = f"sqlite+aiosqlite:///{settings.db_path.as_posix()}"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

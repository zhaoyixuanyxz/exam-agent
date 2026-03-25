import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_test_db = os.getenv("EXAM_AGENT_TEST_DB_PATH")
if _test_db:
    _sync_url = f"sqlite:///{_test_db}"
else:
    _sync_url = f"sqlite:///{settings.db_path.as_posix()}"
sync_engine = create_engine(_sync_url, connect_args={"check_same_thread": False}, echo=False)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def sync_session() -> Session:
    return SyncSessionLocal()

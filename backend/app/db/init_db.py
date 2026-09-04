from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.migrate import (
    apply_sqlite_artifact_v21_columns,
    apply_sqlite_exam_paper_practice_config_column,
    apply_sqlite_exam_paper_v2_columns,
    apply_sqlite_question_assets_v23_columns,
)
from app.db.models import Base
from app.db.session import engine
from app.db.seed_v23 import ensure_v23_seed_data


def _is_sqlite(eng: AsyncEngine) -> bool:
    return eng.dialect.name == "sqlite"


async def init_db(db_engine: AsyncEngine | None = None) -> None:
    eng = db_engine or engine
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight ALTER TABLE helpers are SQLite-oriented; Postgres gets full schema via create_all.
        if _is_sqlite(eng):
            await conn.run_sync(apply_sqlite_exam_paper_v2_columns)
            await conn.run_sync(apply_sqlite_exam_paper_practice_config_column)
            await conn.run_sync(apply_sqlite_artifact_v21_columns)
            await conn.run_sync(apply_sqlite_question_assets_v23_columns)
    await ensure_v23_seed_data(eng)

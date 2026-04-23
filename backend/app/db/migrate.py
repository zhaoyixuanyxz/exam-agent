"""SQLite 轻量迁移：在 create_all 之后为已有库追加 V2.0 所需列。"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


def apply_sqlite_exam_paper_v2_columns(connection: Connection) -> None:
    """为 exam_papers 表增加 V2.0 字段（若尚不存在）。"""
    insp = inspect(connection)
    if not insp.has_table("exam_papers"):
        return
    cols = {c["name"] for c in insp.get_columns("exam_papers")}
    statements: list[str] = []
    if "display_name" not in cols:
        statements.append("ALTER TABLE exam_papers ADD COLUMN display_name VARCHAR(512)")
    if "structured_confirm_status" not in cols:
        statements.append(
            "ALTER TABLE exam_papers ADD COLUMN structured_confirm_status VARCHAR(32) DEFAULT 'none'"
        )
    if "structured_confirmed_at" not in cols:
        statements.append("ALTER TABLE exam_papers ADD COLUMN structured_confirmed_at DATETIME")
    if "structured_version" not in cols:
        statements.append("ALTER TABLE exam_papers ADD COLUMN structured_version INTEGER DEFAULT 0")
    if "structured_updated_at" not in cols:
        statements.append("ALTER TABLE exam_papers ADD COLUMN structured_updated_at DATETIME")
    for stmt in statements:
        connection.execute(text(stmt))
    connection.commit()

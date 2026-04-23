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


def apply_sqlite_exam_paper_practice_config_column(connection: Connection) -> None:
    """为 exam_papers 增加 last_practice_config_json（V2.1 练习配置快照）。"""
    insp = inspect(connection)
    if not insp.has_table("exam_papers"):
        return
    cols = {c["name"] for c in insp.get_columns("exam_papers")}
    if "last_practice_config_json" not in cols:
        connection.execute(
            text("ALTER TABLE exam_papers ADD COLUMN last_practice_config_json TEXT"),
        )


def apply_sqlite_artifact_v21_columns(connection: Connection) -> None:
    """为 artifacts 表增加 V2.1 元信息列（若尚不存在）。"""
    insp = inspect(connection)
    if not insp.has_table("artifacts"):
        return
    cols = {c["name"] for c in insp.get_columns("artifacts")}
    statements: list[str] = []
    if "display_name" not in cols:
        statements.append("ALTER TABLE artifacts ADD COLUMN display_name VARCHAR(512)")
    if "source_tool" not in cols:
        statements.append("ALTER TABLE artifacts ADD COLUMN source_tool VARCHAR(128)")
    if "output_mode" not in cols:
        statements.append("ALTER TABLE artifacts ADD COLUMN output_mode VARCHAR(64)")
    if "config_snapshot_json" not in cols:
        # SQLite：JSON 以 TEXT 存储，与 SQLAlchemy JSON 类型兼容
        statements.append("ALTER TABLE artifacts ADD COLUMN config_snapshot_json TEXT")
    for stmt in statements:
        connection.execute(text(stmt))

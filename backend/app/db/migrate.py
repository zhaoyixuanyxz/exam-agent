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


def apply_sqlite_question_assets_v23_columns(connection: Connection) -> None:
    """V2.3：为 question_assets 增加题库主数据与治理字段，并回填 business_id。"""
    insp = inspect(connection)
    if not insp.has_table("question_assets"):
        return
    cols = {c["name"] for c in insp.get_columns("question_assets")}
    alters: list[str] = []
    if "business_id" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN business_id VARCHAR(36)")
    if "content_fingerprint" not in cols:
        alters.append(
            "ALTER TABLE question_assets ADD COLUMN content_fingerprint VARCHAR(64) DEFAULT ''"
        )
    if "answer" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN answer TEXT")
    if "explanation" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN explanation TEXT")
    if "difficulty" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN difficulty VARCHAR(32)")
    if "textbook_version" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN textbook_version VARCHAR(256)")
    if "chapter_path" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN chapter_path VARCHAR(512)")
    if "grade_label" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN grade_label VARCHAR(128)")
    if "subject_label" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN subject_label VARCHAR(128)")
    if "source_paper_name" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN source_paper_name VARCHAR(512)")
    if "quality_status" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN quality_status VARCHAR(32) DEFAULT 'pending'")
    if "review_status" not in cols:
        alters.append(
            "ALTER TABLE question_assets ADD COLUMN review_status VARCHAR(32) DEFAULT 'pending_review'"
        )
    if "owner_user_id" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN owner_user_id VARCHAR(36)")
    if "visibility" not in cols:
        alters.append("ALTER TABLE question_assets ADD COLUMN visibility VARCHAR(32) DEFAULT 'own'")
    for stmt in alters:
        connection.execute(text(stmt))
    # 重新读取列（可能已扩展）
    cols_after = {c["name"] for c in inspect(connection).get_columns("question_assets")}
    if "business_id" in cols_after:
        connection.execute(
            text(
                "UPDATE question_assets SET business_id = id WHERE business_id IS NULL OR TRIM(business_id) = ''"
            )
        )
    try:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_question_assets_business_id "
                "ON question_assets(business_id)"
            )
        )
    except Exception:
        pass

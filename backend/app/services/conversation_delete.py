"""删除会话及其关联数据：消息、试卷、产物文件、导出目录、LangGraph checkpoint 线程。"""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Artifact, Conversation, ExamPaper, Message


async def delete_conversation_cascade(session: AsyncSession, conversation_id: str) -> None:
    """删除数据库中的会话行（及关联 messages / papers / artifacts）。提交前不删磁盘文件。"""
    r = await session.execute(select(ExamPaper.id).where(ExamPaper.conversation_id == conversation_id))
    paper_ids = [row[0] for row in r.all()]
    if paper_ids:
        await session.execute(delete(Artifact).where(Artifact.paper_id.in_(paper_ids)))
    await session.execute(delete(ExamPaper).where(ExamPaper.conversation_id == conversation_id))
    await session.execute(delete(Message).where(Message.conversation_id == conversation_id))
    await session.execute(delete(Conversation).where(Conversation.id == conversation_id))
    await session.commit()


def collect_conversation_file_paths(conversation_id: str) -> tuple[set[Path], Path]:
    """在删除 ORM 行之前调用：同步收集待删除文件路径与导出目录。"""
    from app.db.sync_session import sync_session

    paths: set[Path] = set()
    with sync_session() as s:
        papers = list(
            s.execute(select(ExamPaper).where(ExamPaper.conversation_id == conversation_id)).scalars().all()
        )
        for p in papers:
            if p.raw_path:
                paths.add(Path(p.raw_path))
            if p.knowledge_markdown_path:
                paths.add(Path(p.knowledge_markdown_path))
            for a in p.artifacts:
                paths.add(Path(a.path))
    export_dir = settings.export_dir / conversation_id
    return paths, export_dir


def unlink_conversation_files(paths: set[Path], export_dir: Path) -> None:
    for path in paths:
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
        except OSError:
            pass
    if export_dir.is_dir():
        shutil.rmtree(export_dir, ignore_errors=True)

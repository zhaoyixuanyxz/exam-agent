from __future__ import annotations

import os

import aiosqlite
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.prebuilt import create_react_agent

from app.agent.prompts import SYSTEM
from app.agent.tools import AGENT_TOOLS
from app.config import settings

_checkpointer: AsyncSqliteSaver | MemorySaver | None = None
_graph = None


def _serverless() -> bool:
    if os.getenv("VERCEL", "").strip():
        return True
    return os.getenv("EXAM_AGENT_SERVERLESS", "").strip().lower() in ("1", "true", "yes")


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.require_deepseek_api_key(),
        base_url=settings.deepseek_base_url,
        temperature=0.3,
        streaming=True,
    )


async def setup_checkpoint() -> None:
    """在 FastAPI lifespan 中调用：使用 AsyncSqliteSaver，支持 graph.astream / aget_state。"""
    global _checkpointer, _graph
    # Vercel 无持久磁盘：用 MemorySaver（同实例内有效；跨冷启动不保留 graph 状态）。
    if _serverless():
        _checkpointer = MemorySaver()
        _graph = None
        return
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path = settings.checkpoint_db_path.as_posix()
    try:
        conn = await aiosqlite.connect(path)
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        _checkpointer = saver
    except Exception:
        _checkpointer = MemorySaver()
    _graph = None


async def shutdown_checkpoint() -> None:
    global _checkpointer, _graph
    saver = _checkpointer
    _checkpointer = None
    _graph = None
    if isinstance(saver, AsyncSqliteSaver):
        await saver.conn.close()


def build_checkpointer() -> AsyncSqliteSaver | MemorySaver:
    if _checkpointer is not None:
        return _checkpointer
    return MemorySaver()


def build_agent_graph():
    """编译带 checkpointer 的 ReAct agent。"""
    checkpointer = build_checkpointer()
    return create_react_agent(
        _llm(),
        AGENT_TOOLS,
        prompt=SYSTEM,
        checkpointer=checkpointer,
    )


def get_agent_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


async def delete_agent_thread(thread_id: str) -> None:
    """删除 LangGraph 中该 thread_id 的检查点（与 conversation_id 一致）。"""
    saver = _checkpointer
    if isinstance(saver, AsyncSqliteSaver):
        await saver.adelete_thread(thread_id)

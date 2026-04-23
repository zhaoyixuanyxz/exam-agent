from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import delete_agent_thread, get_agent_graph
from app.agent.tools import AGENT_TOOLS
from app.config import settings
from app.db.models import Conversation, ExamPaper, Message
from app.db.session import SessionLocal, get_session
from app.db.sync_session import sync_session
from app.services.agent_thread_repair import repair_dangling_tool_calls
from app.services.conversation_delete import (
    collect_conversation_file_paths,
    delete_conversation_cascade,
    unlink_conversation_files,
)
from app.services.llm_errors import user_message_for_llm_error
from app.services.parsers.pipeline import parse_input
from app.services.practice_json_recovery import try_recover_practice_pdf_from_assistant_text
from app.services.storage import new_stored_path

logger = logging.getLogger(__name__)


def _markdown_artifact_display_name(filename: str) -> str:
    """User-facing name for knowledge markdown files on disk."""
    if filename == "knowledge_points.md":
        return "考点说明.md"
    prefix = "考点说明_"
    if filename.startswith(prefix) and filename.endswith(".md"):
        pid = filename[len(prefix) : -len(".md")]
        short = pid[:8] if len(pid) >= 8 else pid
        return f"考点说明·{short}.md"
    return filename


def _artifact_url(abs_path: str) -> str:
    root = settings.export_dir.resolve()
    try:
        rel = Path(abs_path).resolve().relative_to(root)
        return f"/export-files/{rel.as_posix()}"
    except ValueError:
        return ""


router = APIRouter(prefix="/api", tags=["chat"])

_agent_run_tasks: dict[str, asyncio.Task[None]] = {}
_agent_run_registration_locks: dict[str, asyncio.Lock] = {}


def _agent_run_reg_lock(conversation_id: str) -> asyncio.Lock:
    if conversation_id not in _agent_run_registration_locks:
        _agent_run_registration_locks[conversation_id] = asyncio.Lock()
    return _agent_run_registration_locks[conversation_id]


def conversation_agent_run_active(conversation_id: str) -> bool:
    t = _agent_run_tasks.get(conversation_id)
    return t is not None and not t.done()


async def _cancel_agent_run(conversation_id: str) -> None:
    t = _agent_run_tasks.pop(conversation_id, None)
    if t is None or t.done():
        return
    t.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await t


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _text_from_llm_chunk(msg: BaseMessage) -> str:
    """Extract visible text from streamed chat chunks (skip tool-call only fragments)."""
    c = getattr(msg, "content", None)
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(c)


def _assistant_content_str(msg: AIMessage) -> str:
    c = msg.content
    if isinstance(c, str):
        return c if c.strip() else ""
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        s = "".join(parts)
        return s if s.strip() else ""
    s = str(c)
    return s if s.strip() else ""


def _last_assistant_text(messages: Sequence[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            t = _assistant_content_str(m)
            if t:
                return t
    return ""


async def _latest_paper_id(session: AsyncSession, conversation_id: str) -> str | None:
    r = await session.execute(
        select(ExamPaper.id)
        .where(ExamPaper.conversation_id == conversation_id)
        .order_by(ExamPaper.created_at.desc())
        .limit(1)
    )
    row = r.first()
    return row[0] if row else None


@router.post("/conversations")
async def create_conversation(session: Annotated[AsyncSession, Depends(get_session)]):
    cid = str(uuid.uuid4())
    session.add(Conversation(id=cid))
    await session.commit()
    return {"conversation_id": cid}


@router.post("/chat/stream")
async def chat_stream(
    session: Annotated[AsyncSession, Depends(get_session)],
    conversation_id: str = Form(...),
    message: str = Form(""),
    source_type: str = Form("text"),
    url: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")

    paper_id: str | None = None
    extra_note = ""

    if file and file.filename:
        raw = await file.read()
        if len(raw) > settings.max_upload_bytes:
            raise HTTPException(413, "文件超过 50MB 限制")
        dest = new_stored_path(file.filename)
        dest.write_bytes(raw)
        st = source_type.lower().strip()
        if st not in ("pdf", "docx", "text"):
            st = "pdf" if dest.suffix.lower() == ".pdf" else "docx"
        try:
            text, _ = parse_input(st, file_path=dest, url=None, text=None)
        except Exception as e:
            raise HTTPException(400, f"解析失败: {e!s}") from e
        pid = str(uuid.uuid4())
        session.add(
            ExamPaper(
                id=pid,
                conversation_id=conversation_id,
                raw_path=dest.as_posix(),
                source_type=st,
                raw_text=text,
            )
        )
        await session.commit()
        paper_id = pid
        preview = (text[:1200] + "…") if len(text) > 1200 else text
        extra_note = f"\n\n【用户上传了试卷文件，paper_id={paper_id}】\n正文预览：\n{preview}"
    elif url and url.strip() and source_type.lower() == "url":
        try:
            text, _ = parse_input("url", url=url.strip())
        except Exception as e:
            raise HTTPException(400, f"URL 抓取失败: {e!s}") from e
        pid = str(uuid.uuid4())
        session.add(
            ExamPaper(
                id=pid,
                conversation_id=conversation_id,
                source_type="url",
                raw_text=text,
            )
        )
        await session.commit()
        paper_id = pid
        extra_note = f"\n\n【来自 URL，paper_id={paper_id}】\n内容预览：\n{text[:1200]}"
    elif message.strip():
        existing = await _latest_paper_id(session, conversation_id)
        if existing is None:
            pid = str(uuid.uuid4())
            session.add(
                ExamPaper(
                    id=pid,
                    conversation_id=conversation_id,
                    source_type="text",
                    raw_text=message.strip(),
                )
            )
            await session.commit()
            paper_id = pid
            extra_note = f"\n\n【粘贴内容已保存为试卷，paper_id={paper_id}】"
        else:
            paper_id = existing

    if paper_id is None:
        paper_id = await _latest_paper_id(session, conversation_id)

    if not paper_id and not message.strip() and not file and not (url and url.strip()):
        raise HTTPException(400, "请发送消息、粘贴文本、上传文件或提供 URL")

    pc_r = await session.execute(
        select(func.count()).select_from(ExamPaper).where(ExamPaper.conversation_id == conversation_id)
    )
    paper_count = int(pc_r.scalar_one() or 0)

    base_msg = (message.strip() or "请根据我提供的材料开始分析试卷。") + extra_note
    ctx = (
        f"【系统上下文】conversation_id={conversation_id}；paper_id={paper_id}；本会话累计试卷材料份数={paper_count}。"
        "此 paper_id 为本轮默认绑定材料（一般为最近上传或粘贴的一份）。"
        "若份数大于 1 且用户未明确针对哪一份，须用简短中文请用户说明目标材料（可提示 paper_id 前 8 位），禁止猜测。"
        "工具调用的 paper_id 必须与上述 paper_id 一致。\n\n"
    )
    user_content = ctx + base_msg

    session.add(
        Message(
            conversation_id=conversation_id,
            role="user",
            content=user_content,
        )
    )
    await session.commit()

    async def gen() -> AsyncIterator[str]:
        out_q: asyncio.Queue[str | None] = asyncio.Queue()

        async def agent_runner() -> None:
            my_task = asyncio.current_task()
            out_text = ""
            streamed_any = False
            streamed_buf: list[str] = []
            try:
                graph = get_agent_graph()
                config = {"configurable": {"thread_id": conversation_id}}
                await repair_dangling_tool_calls(graph, config, AGENT_TOOLS)
                await out_q.put(_sse({"event": "meta", "data": {"paper_id": paper_id}}))
                inp = {"messages": [HumanMessage(content=user_content)]}
                async for part in graph.astream(
                    inp,
                    config,
                    stream_mode=["messages", "tasks"],
                    version="v2",
                ):
                    ptype = part.get("type")
                    if ptype == "tasks":
                        td: dict[str, Any] = part.get("data") or {}
                        if "result" in td:
                            continue
                        node = str(td.get("name", ""))
                        if node == "tools":
                            await out_q.put(
                                _sse(
                                    {
                                        "event": "status",
                                        "data": {
                                            "message": "正在执行工具（拆题、考点分析或出题等，内部会多次调用模型）…"
                                        },
                                    }
                                )
                            )
                        elif node == "agent":
                            await out_q.put(
                                _sse(
                                    {
                                        "event": "status",
                                        "data": {"message": "模型生成中…"},
                                    }
                                )
                            )
                    elif ptype == "messages":
                        data = part.get("data")
                        if not data or not isinstance(data, tuple) or len(data) < 1:
                            continue
                        msg_chunk, _meta = data[0], data[1] if len(data) > 1 else {}
                        piece = _text_from_llm_chunk(msg_chunk)
                        if piece:
                            streamed_any = True
                            streamed_buf.append(piece)
                            await out_q.put(_sse({"event": "token", "data": {"t": piece}}))

                snap = await graph.aget_state(config)
                values = getattr(snap, "values", None) or {}
                msgs = list(values.get("messages") or [])
                out_text = _last_assistant_text(msgs) or "".join(streamed_buf)
                if not streamed_any and out_text:
                    await out_q.put(_sse({"event": "token", "data": {"t": out_text}}))

                recovered_pdf = False
                if paper_id and out_text and not out_text.startswith("（处理出错"):
                    out_text, recovered_pdf = try_recover_practice_pdf_from_assistant_text(
                        out_text, paper_id
                    )
                if recovered_pdf and streamed_any:
                    await out_q.put(
                        _sse(
                            {
                                "event": "token",
                                "data": {
                                    "t": "\n\n（正文中的练习题 JSON 已自动导出为 PDF，见下方「生成文件」）"
                                },
                            }
                        )
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                friendly = user_message_for_llm_error(e)
                await out_q.put(_sse({"event": "error", "data": {"message": friendly}}))
                out_text = f"（处理出错：{friendly}）"
            finally:
                if out_text:
                    try:
                        async with SessionLocal() as write_session:
                            write_session.add(
                                Message(
                                    conversation_id=conversation_id,
                                    role="assistant",
                                    content=out_text,
                                )
                            )
                            await write_session.commit()
                    except Exception:
                        logger.exception("persist assistant message failed")
                try:
                    artifacts = _list_artifacts_sync(conversation_id)
                    await out_q.put(_sse({"event": "artifacts", "data": {"items": artifacts}}))
                    await out_q.put(_sse({"event": "done", "data": {}}))
                finally:
                    await out_q.put(None)
                cur = _agent_run_tasks.get(conversation_id)
                if cur is my_task:
                    _agent_run_tasks.pop(conversation_id, None)

        async with _agent_run_reg_lock(conversation_id):
            await _cancel_agent_run(conversation_id)
            _agent_run_tasks[conversation_id] = asyncio.create_task(agent_runner())

        try:
            while True:
                item = await out_q.get()
                if item is None:
                    break
                yield item
        except asyncio.CancelledError:
            raise

    return StreamingResponse(gen(), media_type="text/event-stream")


def _list_artifacts_sync(conversation_id: str) -> list[dict]:
    from sqlalchemy import select

    with sync_session() as s:
        papers = list(
            s.execute(
                select(ExamPaper)
                .where(ExamPaper.conversation_id == conversation_id)
                .order_by(ExamPaper.created_at.desc())
            )
            .scalars()
            .all()
        )
        items: list[dict] = []
        seen: set[str] = set()
        for p in papers:
            if p.knowledge_markdown_path and Path(p.knowledge_markdown_path).is_file():
                mp = p.knowledge_markdown_path
                if mp not in seen:
                    seen.add(mp)
                    md_name = Path(mp).name
                    md_name = _markdown_artifact_display_name(md_name)
                    items.append(
                        {
                            "kind": "markdown",
                            "path": mp,
                            "url": _artifact_url(mp),
                            "name": md_name,
                        }
                    )
            for a in p.artifacts:
                if a.path in seen:
                    continue
                seen.add(a.path)
                items.append(
                    {
                        "kind": a.kind,
                        "path": a.path,
                        "url": _artifact_url(a.path),
                        "name": Path(a.path).name,
                        "knowledge_point_key": a.knowledge_point_key,
                    }
                )
        return items


@router.get("/conversations/{conversation_id}/papers")
async def list_conversation_papers(
    conversation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    r = await session.execute(
        select(ExamPaper)
        .where(ExamPaper.conversation_id == conversation_id)
        .order_by(ExamPaper.created_at.desc())
    )
    papers = r.scalars().all()
    return {
        "papers": [
            {
                "id": p.id,
                "source_type": p.source_type,
                "raw_path": p.raw_path,
            }
            for p in papers
        ]
    }


@router.get("/conversations/{conversation_id}/artifacts")
async def list_artifacts(
    conversation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404)
    return {"items": _list_artifacts_sync(conversation_id)}


@router.get("/conversations/{conversation_id}/agent-run-active")
async def get_agent_run_active(
    conversation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """当前会话是否仍有后台 Agent 任务在跑（例如用户刷新页面后 SSE 已断、生成仍在继续）。"""
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    return {"active": conversation_agent_run_active(conversation_id)}


_RE_INJECTED_FILE_PREVIEW = re.compile(
    r"\n\n【用户上传了试卷文件，paper_id=[^】]+】\n正文预览：\n[\s\S]*$",
)
_RE_INJECTED_URL_PREVIEW = re.compile(
    r"\n\n【来自 URL，paper_id=[^】]+】\n内容预览：\n[\s\S]*$",
)


def _strip_injected_previews_from_user_body(s: str) -> str:
    """与前端 displayUserMessageContent 一致：列表预览不展示 OCR 注入块。"""
    s = _RE_INJECTED_FILE_PREVIEW.sub("", s)
    s = _RE_INJECTED_URL_PREVIEW.sub("", s)
    return s


def _preview_from_user_content(content: str | None, max_len: int = 80) -> str:
    if not content:
        return ""
    s = content.strip()
    prefix = "【系统上下文】"
    if s.startswith(prefix):
        idx = s.find("\n\n")
        if idx != -1:
            s = s[idx + 2 :].strip()
    s = _strip_injected_previews_from_user_body(s).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


@router.get("/conversations")
async def list_conversations(session: Annotated[AsyncSession, Depends(get_session)]):
    """按最近一条消息时间排序；无消息时按会话创建时间。"""
    last_msg = (
        select(
            Message.conversation_id.label("cid"),
            func.max(Message.created_at).label("last_at"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )
    msg_count_sq = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .scalar_subquery()
    )
    paper_count_sq = (
        select(func.count(ExamPaper.id))
        .where(ExamPaper.conversation_id == Conversation.id)
        .scalar_subquery()
    )
    first_user_sq = (
        select(Message.content)
        .where(
            Message.conversation_id == Conversation.id,
            Message.role == "user",
        )
        .order_by(Message.created_at.asc())
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        select(
            Conversation.id,
            Conversation.created_at,
            Conversation.title,
            func.coalesce(last_msg.c.last_at, Conversation.created_at).label("last_activity_at"),
            msg_count_sq.label("message_count"),
            paper_count_sq.label("paper_count"),
            first_user_sq.label("first_user_raw"),
        )
        .outerjoin(last_msg, Conversation.id == last_msg.c.cid)
        .order_by(func.coalesce(last_msg.c.last_at, Conversation.created_at).desc())
    )
    r = await session.execute(stmt)
    rows = r.all()
    items: list[dict] = []
    for row in rows:
        raw_preview = row.first_user_raw
        preview = _preview_from_user_content(raw_preview if raw_preview is None else str(raw_preview))
        items.append(
            {
                "id": row.id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
                "title": row.title,
                "message_count": int(row.message_count or 0),
                "paper_count": int(row.paper_count or 0),
                "preview": preview or "（空对话）",
            }
        )
    return {"conversations": items}


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    r = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    msgs = r.scalars().all()
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }


class ConversationTitlePatch(BaseModel):
    """用户自定义对话名称；空字符串表示清除标题，列表仍显示首条消息预览。"""

    title: str = Field(default="", max_length=512)


@router.patch("/conversations/{conversation_id}")
async def patch_conversation(
    conversation_id: str,
    body: ConversationTitlePatch,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    stripped = (body.title or "").strip()
    conv.title = stripped if stripped else None
    await session.commit()
    return {"ok": True, "title": conv.title}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    await _cancel_agent_run(conversation_id)
    paths, export_dir = collect_conversation_file_paths(conversation_id)
    await delete_conversation_cascade(session, conversation_id)
    await delete_agent_thread(conversation_id)
    unlink_conversation_files(paths, export_dir)
    return {"ok": True}

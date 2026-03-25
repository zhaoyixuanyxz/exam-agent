from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import get_agent_graph
from app.config import settings
from app.db.models import Conversation, ExamPaper, Message
from app.db.session import SessionLocal, get_session
from app.db.sync_session import sync_session
from app.services.llm_errors import user_message_for_llm_error
from app.services.parsers.pipeline import parse_input
from app.services.practice_json_recovery import try_recover_practice_pdf_from_assistant_text
from app.services.storage import new_stored_path


def _artifact_url(abs_path: str) -> str:
    root = settings.export_dir.resolve()
    try:
        rel = Path(abs_path).resolve().relative_to(root)
        return f"/export-files/{rel.as_posix()}"
    except ValueError:
        return ""


router = APIRouter(prefix="/api", tags=["chat"])


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

    base_msg = (message.strip() or "请根据我提供的材料开始分析试卷。") + extra_note
    ctx = (
        f"【系统上下文】conversation_id={conversation_id}；paper_id={paper_id}。"
        "调用工具时必须使用此 paper_id。\n\n"
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
        yield _sse({"event": "meta", "data": {"paper_id": paper_id}})
        out_text = ""
        streamed_any = False
        streamed_buf: list[str] = []
        try:
            graph = get_agent_graph()
            config = {"configurable": {"thread_id": conversation_id}}
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
                        yield _sse(
                            {
                                "event": "status",
                                "data": {
                                    "message": "正在执行工具（拆题、考点分析或出题等，内部会多次调用模型）…"
                                },
                            }
                        )
                    elif node == "agent":
                        yield _sse(
                            {
                                "event": "status",
                                "data": {"message": "模型生成中…"},
                            }
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
                        yield _sse({"event": "token", "data": {"t": piece}})

            snap = await graph.aget_state(config)
            values = getattr(snap, "values", None) or {}
            msgs = list(values.get("messages") or [])
            out_text = _last_assistant_text(msgs) or "".join(streamed_buf)
            if not streamed_any and out_text:
                yield _sse({"event": "token", "data": {"t": out_text}})

            recovered_pdf = False
            if paper_id and out_text and not out_text.startswith("（处理出错"):
                out_text, recovered_pdf = try_recover_practice_pdf_from_assistant_text(
                    out_text, paper_id
                )
            if recovered_pdf and streamed_any:
                yield _sse(
                    {
                        "event": "token",
                        "data": {"t": "\n\n（正文中的练习题 JSON 已自动导出为 PDF，见下方「生成文件」）"},
                    }
                )
        except Exception as e:
            friendly = user_message_for_llm_error(e)
            yield _sse({"event": "error", "data": {"message": friendly}})
            out_text = f"（处理出错：{friendly}）"

        if out_text:
            async with SessionLocal() as write_session:
                write_session.add(
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=out_text,
                    )
                )
                await write_session.commit()

        artifacts = _list_artifacts_sync(conversation_id)
        yield _sse({"event": "artifacts", "data": {"items": artifacts}})
        yield _sse({"event": "done", "data": {}})

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
                    if md_name == "knowledge_points.md":
                        md_name = "考点说明.md"
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


@router.get("/conversations/{conversation_id}/artifacts")
async def list_artifacts(
    conversation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404)
    return {"items": _list_artifacts_sync(conversation_id)}

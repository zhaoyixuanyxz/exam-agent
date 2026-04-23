from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.graph import delete_agent_thread, get_agent_graph
from app.agent.tools import AGENT_TOOLS
from app.config import settings
from app.db.models import Artifact, Conversation, ExamPaper, Message
from app.models.schemas import StructuredPaper
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
from app.services.question_assets import rebuild_question_assets_for_paper_id
from app.services.storage import new_stored_path
from app.services.structured_inspect import build_summary_from_parsed, list_anomalies
from app.services.workflow_state import (
    build_workflow_payload,
    effective_structured_status,
    infer_failed_step_key_from_error_text,
)

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


def _artifact_ui_category(kind: str) -> str:
    """产物中心分类：与 kind 区分，供前端分组展示。"""
    if kind == "markdown":
        return "knowledge_markdown"
    if kind == "pdf_question":
        return "practice_question_pdf"
    if kind == "pdf_answer":
        return "practice_answer_pdf"
    return "other"


def _iso_utc_naive(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat()


def _path_mtime_iso(abs_path: str) -> str | None:
    try:
        st = Path(abs_path).stat()
        return datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def _normalize_practice_generate_config(raw: dict[str, Any]) -> dict[str, Any]:
    """将前端练习配置 JSON 规范化为入库结构。"""
    out: dict[str, Any] = {}
    if "question_count" in raw:
        try:
            out["question_count"] = max(1, min(60, int(raw["question_count"])))
        except (TypeError, ValueError):
            pass
    d = raw.get("difficulty")
    if d is not None:
        ds = str(d).strip().lower()
        if ds in ("easy", "medium", "hard", "简单", "中等", "困难"):
            mmap = {"简单": "easy", "中等": "medium", "困难": "hard"}
            out["difficulty"] = mmap.get(ds, ds)
    qt = raw.get("question_types")
    if isinstance(qt, list):
        allowed: list[str] = []
        for x in qt:
            s = str(x).strip()
            if s in ("单选", "多选", "填空", "简答", "判断"):
                allowed.append(s)
            elif s == "选择题":
                allowed.extend(["单选", "多选"])
        allowed = list(dict.fromkeys(allowed))
        if allowed:
            out["question_types"] = allowed
    om = raw.get("output_mode")
    if om is not None:
        o = str(om).strip().lower()
        if o in ("questions_only", "questions_and_answers", "仅题目", "题目+答案"):
            if o == "仅题目":
                o = "questions_only"
            elif o == "题目+答案":
                o = "questions_and_answers"
            out["output_mode"] = o
    pm = raw.get("paper_mode")
    if pm is not None and str(pm).strip():
        out["paper_mode"] = str(pm).strip()
    if "use_original_figures" in raw:
        out["use_original_figures"] = bool(raw["use_original_figures"])
    if "include_figures" in raw:
        out["include_figures"] = bool(raw["include_figures"])
    return out


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
    target_paper_id: str | None = Form(None),
    practice_generate_config: str | None = Form(None),
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")

    new_paper_from_upload = False
    new_paper_from_paste = False
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
        dname = Path(file.filename or "file").stem or "上传文件"
        if len(dname) > 500:
            dname = dname[:500]
        session.add(
            ExamPaper(
                id=pid,
                conversation_id=conversation_id,
                raw_path=dest.as_posix(),
                source_type=st,
                raw_text=text,
                display_name=dname,
            )
        )
        await session.commit()
        paper_id = pid
        new_paper_from_upload = True
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
                display_name="网页材料",
            )
        )
        await session.commit()
        paper_id = pid
        new_paper_from_upload = True
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
                    display_name="粘贴材料",
                )
            )
            await session.commit()
            paper_id = pid
            new_paper_from_paste = True
            extra_note = f"\n\n【粘贴内容已保存为试卷，paper_id={paper_id}】"
        else:
            paper_id = existing

    if paper_id is None:
        paper_id = await _latest_paper_id(session, conversation_id)

    if (
        not new_paper_from_upload
        and not new_paper_from_paste
        and target_paper_id
        and str(target_paper_id).strip()
    ):
        tid = str(target_paper_id).strip()
        tp = await session.get(ExamPaper, tid)
        if not tp or tp.conversation_id != conversation_id:
            raise HTTPException(400, "目标材料无效或不属于当前会话。")
        paper_id = tid

    if not paper_id and not message.strip() and not file and not (url and url.strip()):
        raise HTTPException(400, "请发送消息、粘贴文本、上传文件或提供 URL")

    pc_r = await session.execute(
        select(func.count()).select_from(ExamPaper).where(ExamPaper.conversation_id == conversation_id)
    )
    paper_count = int(pc_r.scalar_one() or 0)

    practice_config_fragment = ""
    if (
        paper_id
        and practice_generate_config is not None
        and str(practice_generate_config).strip()
    ):
        try:
            cfg_raw = json.loads(practice_generate_config)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"practice_generate_config 须为合法 JSON：{e!s}") from e
        if not isinstance(cfg_raw, dict):
            raise HTTPException(400, "practice_generate_config 须为 JSON 对象")
        cfg_norm = _normalize_practice_generate_config(cfg_raw)
        ep = await session.get(ExamPaper, paper_id)
        if ep and ep.conversation_id == conversation_id:
            prev = ep.last_practice_config_json if isinstance(ep.last_practice_config_json, dict) else {}
            merged = {**prev, **cfg_norm}
            ep.last_practice_config_json = merged
            session.add(ep)
            await session.commit()
            practice_config_fragment = (
                "\n\n【练习生成默认配置】"
                + json.dumps(merged, ensure_ascii=False)
                + "\n若本回合需要出题，调用 generate_chunk_practice_pdf 或 generate_chunk_practice_pdfs_batch 时，"
                "须通过工具参数传入与上述一致的 difficulty、question_types_json（JSON 数组字符串）、"
                "output_mode、use_original_figures、include_figures；题量以配置中的 question_count 为准（工具 question_count 应与其一致）。\n"
            )

    base_msg = (message.strip() or "请根据我提供的材料开始分析试卷。") + extra_note
    ctx = (
        f"【系统上下文】conversation_id={conversation_id}；paper_id={paper_id}；本会话累计试卷材料份数={paper_count}。"
        "此 paper_id 为本轮默认绑定材料（用户可在界面选择目标材料；多份材料时须严格使用该 paper_id）。"
        "若份数大于 1 且用户未在界面选择目标、也未说明材料，须用简短中文请用户选择或说明（可提示 paper_id 前 8 位），禁止猜测。"
        "工具调用的 paper_id 必须与上述 paper_id 一致。\n\n"
    )
    user_content = ctx + base_msg + practice_config_fragment

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
                .options(selectinload(ExamPaper.artifacts))
                .order_by(ExamPaper.created_at.desc()),
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
                    created = (
                        _path_mtime_iso(mp)
                        or _iso_utc_naive(p.structured_updated_at)
                        or _iso_utc_naive(p.created_at)
                    )
                    items.append(
                        {
                            "id": f"md:{p.id}",
                            "kind": "markdown",
                            "category": _artifact_ui_category("markdown"),
                            "path": mp,
                            "url": _artifact_url(mp),
                            "name": md_name,
                            "paper_id": p.id,
                            "paper_display_name": p.display_name,
                            "knowledge_point_key": None,
                            "created_at": created,
                            "source_tool": "run_knowledge_analysis",
                            "config_snapshot": None,
                            "output_mode": None,
                        },
                    )
            arts = sorted(
                p.artifacts or [],
                key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            for a in arts:
                if a.path in seen:
                    continue
                seen.add(a.path)
                disp = a.display_name or Path(a.path).name
                items.append(
                    {
                        "id": a.id,
                        "kind": a.kind,
                        "category": _artifact_ui_category(a.kind),
                        "path": a.path,
                        "url": _artifact_url(a.path),
                        "name": disp,
                        "paper_id": p.id,
                        "paper_display_name": p.display_name,
                        "knowledge_point_key": a.knowledge_point_key,
                        "created_at": _iso_utc_naive(a.created_at),
                        "source_tool": a.source_tool,
                        "config_snapshot": a.config_snapshot_json,
                        "output_mode": a.output_mode,
                    },
                )

        def _sort_key(d: dict) -> tuple[str, str]:
            ca = d.get("created_at") or ""
            i = str(d.get("id") or "")
            return (ca, i)

        items.sort(key=_sort_key, reverse=True)
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
                "display_name": p.display_name,
                "structured_confirm_status": effective_structured_status(p),
                "last_practice_config": p.last_practice_config_json
                if isinstance(p.last_practice_config_json, dict)
                else None,
            }
            for p in papers
        ]
    }


class PaperDisplayNamePatch(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=512)


@router.patch("/conversations/{conversation_id}/papers/{paper_id}")
async def patch_paper_display_name(
    conversation_id: str,
    paper_id: str,
    body: PaperDisplayNamePatch,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != conversation_id:
        raise HTTPException(404, "paper not found")
    p.display_name = body.display_name.strip()
    await session.commit()
    return {"ok": True, "display_name": p.display_name, "id": p.id}


class StructuredPaperPatchBody(BaseModel):
    parsed_json: dict[str, Any]


@router.get("/conversations/{conversation_id}/papers/{paper_id}/structured")
async def get_paper_structured(
    conversation_id: str,
    paper_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != conversation_id:
        raise HTTPException(404, "paper not found")
    st = effective_structured_status(p)
    summary = build_summary_from_parsed(p.parsed_json) if p.parsed_json else None
    return {
        "paper_id": p.id,
        "display_name": p.display_name,
        "structured_confirm_status": st,
        "structured_version": int(p.structured_version or 0),
        "structured_confirmed_at": p.structured_confirmed_at.isoformat()
        if p.structured_confirmed_at
        else None,
        "structured_updated_at": p.structured_updated_at.isoformat()
        if p.structured_updated_at
        else None,
        "parsed_json": p.parsed_json,
        "summary": summary,
        "anomalies": list_anomalies(p.parsed_json),
        "alignment_json": p.alignment_json,
    }


@router.patch("/conversations/{conversation_id}/papers/{paper_id}/structured")
async def patch_paper_structured(
    conversation_id: str,
    paper_id: str,
    body: StructuredPaperPatchBody,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != conversation_id:
        raise HTTPException(404, "paper not found")
    try:
        sp = StructuredPaper.model_validate(body.parsed_json)
    except Exception as e:
        raise HTTPException(400, f"结构化数据格式不正确：{e!s}") from e
    p.parsed_json = sp.model_dump()
    p.structured_version = int(p.structured_version or 0) + 1
    p.structured_updated_at = datetime.utcnow()
    p.structured_confirm_status = "pending"
    p.structured_confirmed_at = None
    await session.commit()
    return {
        "ok": True,
        "structured_version": p.structured_version,
        "structured_confirm_status": effective_structured_status(p),
    }


@router.post("/conversations/{conversation_id}/papers/{paper_id}/structured/confirm")
async def post_confirm_structured(
    conversation_id: str,
    paper_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != conversation_id:
        raise HTTPException(404, "paper not found")
    if not p.parsed_json:
        raise HTTPException(400, "暂无可确认的结构化结果，请先完成拆题。")
    try:
        StructuredPaper.model_validate(p.parsed_json)
    except Exception as e:
        raise HTTPException(400, f"当前结构化数据仍无法通过校验，无法确认：{e!s}") from e
    if list_anomalies(p.parsed_json):
        # 允许带警告仍确认，由产品决定；此处仅阻止「无法解析」类已在 validate 处理
        pass
    p.structured_confirm_status = "confirmed"
    p.structured_confirmed_at = datetime.utcnow()
    p.structured_version = int(p.structured_version or 0)  # 确认不强制升版本
    await session.commit()
    n_assets = rebuild_question_assets_for_paper_id(paper_id)
    return {
        "ok": True,
        "structured_confirm_status": effective_structured_status(p),
        "structured_confirmed_at": p.structured_confirmed_at.isoformat() if p.structured_confirmed_at else None,
        "question_assets_synced": n_assets,
    }


@router.post("/conversations/{conversation_id}/papers/{paper_id}/question-assets/rebuild")
async def post_rebuild_question_assets(
    conversation_id: str,
    paper_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """历史数据回填：对已确认结构化的试卷重建题目资产行。"""
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != conversation_id:
        raise HTTPException(404, "paper not found")
    if (p.structured_confirm_status or "") != "confirmed":
        raise HTTPException(400, "仅对已确认结构化的材料重建题目资产")
    if not p.parsed_json:
        raise HTTPException(400, "无结构化数据")
    try:
        StructuredPaper.model_validate(p.parsed_json)
    except Exception as e:
        raise HTTPException(400, f"结构化数据无效：{e!s}") from e
    n = rebuild_question_assets_for_paper_id(paper_id)
    return {"ok": True, "count": n}


@router.get("/conversations/{conversation_id}/workflow")
async def get_conversation_workflow(
    conversation_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    paper_id: str = Query(..., min_length=1),
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    r = await session.execute(
        select(ExamPaper)
        .where(ExamPaper.id == paper_id, ExamPaper.conversation_id == conversation_id)
        .options(selectinload(ExamPaper.artifacts))
    )
    p = r.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "paper not found")
    ar = conversation_agent_run_active(conversation_id)
    last_failed: str | None = None
    if not ar:
        rmsg = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        m = rmsg.scalars().first()
        if m and m.content:
            c = str(m.content)
            if "（处理出错" in c or c.strip().startswith("（处理出错"):
                last_failed = infer_failed_step_key_from_error_text(c)
    return build_workflow_payload(
        p,
        agent_run_active=ar,
        conversation_id=conversation_id,
        last_failed_step=last_failed,
    )


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
async def list_conversations(
    session: Annotated[AsyncSession, Depends(get_session)],
    subject: str | None = Query(None, description="按学科子串筛选"),
    date_from: str | None = Query(None, description="最近活动时间起 YYYY-MM-DD"),
    date_to: str | None = Query(None, description="最近活动时间止 YYYY-MM-DD"),
):
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
    conv_ids = [row.id for row in rows]

    subject_by_c: dict[str, str | None] = {}
    grade_by_c: dict[str, str | None] = {}
    last_art_cat_by_c: dict[str, str | None] = {}
    if conv_ids:
        rp = await session.execute(select(ExamPaper).where(ExamPaper.conversation_id.in_(conv_ids)))
        all_papers = rp.scalars().all()
        papers_by_c: dict[str, list[ExamPaper]] = {}
        for p in all_papers:
            papers_by_c.setdefault(p.conversation_id, []).append(p)
        for cid, plist in papers_by_c.items():
            with_a = [p for p in plist if p.alignment_json]
            if with_a:
                with_a.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
                aj = with_a[0].alignment_json or {}
                sub = aj.get("subject")
                subject_by_c[cid] = str(sub) if sub else None
                gmin, gmax = aj.get("grade_min"), aj.get("grade_max")
                if gmin or gmax:
                    grade_by_c[cid] = f"{gmin or '?'}—{gmax or '?'}"

        ra = await session.execute(
            select(Artifact, ExamPaper.conversation_id)
            .join(ExamPaper, Artifact.paper_id == ExamPaper.id)
            .where(ExamPaper.conversation_id.in_(conv_ids))
            .order_by(Artifact.created_at.desc()),
        )
        for art, conv_id in ra.all():
            if conv_id not in last_art_cat_by_c:
                last_art_cat_by_c[conv_id] = _artifact_ui_category(art.kind)

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
                "subject": subject_by_c.get(row.id),
                "grade_range": grade_by_c.get(row.id),
                "last_artifact_category": last_art_cat_by_c.get(row.id),
            }
        )

    sub_f = (subject or "").strip()
    df = (date_from or "").strip()[:10]
    dt = (date_to or "").strip()[:10]
    if sub_f:
        items = [
            it
            for it in items
            if sub_f in (it.get("subject") or "")
            or sub_f in (it.get("title") or "")
            or sub_f in (it.get("preview") or "")
        ]
    if df or dt:

        def _ok_iso(iso: str | None) -> bool:
            d = (iso or "")[:10]
            if len(d) != 10:
                return False
            if df and d < df:
                return False
            if dt and d > dt:
                return False
            return True

        items = [it for it in items if _ok_iso(it.get("last_activity_at"))]

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

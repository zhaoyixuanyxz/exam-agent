"""修复 LangGraph 检查点中「仅有 AIMessage.tool_calls、缺少 ToolMessage」的断裂历史。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def find_last_incomplete_tool_calls(
    messages: Sequence[BaseMessage],
) -> tuple[AIMessage, set[str]] | None:
    """
    若消息列表末尾存在「最后一次带 tool_calls 的 AIMessage」尚未被后续
    ToolMessage 全部应答，则返回该 AIMessage 与缺失的 tool_call_id 集合。
    """
    last_ai: AIMessage | None = None
    last_ai_idx: int | None = None
    for i, m in enumerate(messages):
        if isinstance(m, AIMessage) and (m.tool_calls or []):
            last_ai = m
            last_ai_idx = i
    if last_ai is None or last_ai_idx is None:
        return None
    needed: set[str] = set()
    for c in last_ai.tool_calls or []:
        tid = c.get("id") if isinstance(c, dict) else getattr(c, "id", None)
        if tid is not None:
            needed.add(str(tid))
    if not needed:
        return None
    seen: set[str] = set()
    j = last_ai_idx + 1
    while j < len(messages):
        x = messages[j]
        if not isinstance(x, ToolMessage):
            break
        tid = getattr(x, "tool_call_id", None)
        if tid is not None:
            seen.add(str(tid))
        j += 1
    missing = needed - seen
    if not missing:
        return None
    return (last_ai, missing)


def _tool_call_id(tc: dict | object) -> str:
    if isinstance(tc, dict):
        return str(tc.get("id") or "")
    return str(getattr(tc, "id", "") or "")


def _tool_call_name(tc: dict | object) -> str:
    if isinstance(tc, dict):
        return str(tc.get("name") or "")
    return str(getattr(tc, "name", "") or "")


def _tool_call_args(tc: dict | object) -> dict:
    if isinstance(tc, dict):
        raw = tc.get("args")
        return raw if isinstance(raw, dict) else {}
    raw = getattr(tc, "args", None)
    return raw if isinstance(raw, dict) else {}


async def repair_dangling_tool_calls(
    graph: object,
    config: dict,
    tools: Sequence[BaseTool],
    *,
    max_rounds: int = 8,
) -> int:
    """
    对检查点线程执行修复：对缺失的 tool_call 重新执行工具并写入 ToolMessage。
    返回本轮累计追加的 ToolMessage 条数。
    """
    tool_map = {t.name: t for t in tools}
    total_appended = 0
    for _ in range(max_rounds):
        snap = await graph.aget_state(config)
        values = getattr(snap, "values", None) or {}
        msgs = list(values.get("messages") or [])
        found = find_last_incomplete_tool_calls(msgs)
        if not found:
            break
        ai_msg, missing_ids = found
        new_tool_messages: list[ToolMessage] = []
        for tc in ai_msg.tool_calls or []:
            tid = _tool_call_id(tc)
            if tid not in missing_ids:
                continue
            name = _tool_call_name(tc)
            args = _tool_call_args(tc)
            tool = tool_map.get(name)
            if tool is None:
                body = f"错误：未知工具 {name!r}，无法自动重试。"
                logger.warning("repair: unknown tool %s", name)
            else:

                def _sync_invoke() -> str:
                    try:
                        out = tool.invoke(args)
                        return out if isinstance(out, str) else str(out)
                    except Exception as e:
                        logger.exception("repair: tool %s failed", name)
                        return f"错误：工具重试失败：{e!s}"

                body = await asyncio.to_thread(_sync_invoke)
            new_tool_messages.append(
                ToolMessage(content=body, tool_call_id=tid, name=name or "tool")
            )
        if not new_tool_messages:
            logger.warning("repair: incomplete tool calls but built no ToolMessage; abort repair")
            break
        await graph.aupdate_state(config, {"messages": new_tool_messages}, as_node="tools")
        total_appended += len(new_tool_messages)
    return total_appended

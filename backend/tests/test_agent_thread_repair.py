from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.agent_thread_repair import find_last_incomplete_tool_calls


def test_find_incomplete_when_no_tool_messages() -> None:
    ai = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "generate_chunk_practice_pdf",
                "args": {"paper_id": "p1", "knowledge_point_key": "kp"},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    msgs = [HumanMessage(content="hi"), ai]
    r = find_last_incomplete_tool_calls(msgs)
    assert r is not None
    _ai, missing = r
    assert missing == {"call_1"}


def test_find_none_when_tools_answered() -> None:
    ai = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "foo",
                "args": {"x": 1},
                "id": "c1",
                "type": "tool_call",
            }
        ],
    )
    msgs = [
        HumanMessage(content="hi"),
        ai,
        ToolMessage(content="ok", tool_call_id="c1", name="foo"),
    ]
    assert find_last_incomplete_tool_calls(msgs) is None


def test_find_partial_batch() -> None:
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "a", "args": {}, "id": "t1", "type": "tool_call"},
            {"name": "b", "args": {}, "id": "t2", "type": "tool_call"},
        ],
    )
    msgs = [ai, ToolMessage(content="1", tool_call_id="t1", name="a")]
    r = find_last_incomplete_tool_calls(msgs)
    assert r is not None
    _ai, missing = r
    assert missing == {"t2"}

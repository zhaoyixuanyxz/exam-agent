# US-6 超时有提示，已入库的卷还在 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 出练习卷或排彩色说明时若判定为连接中断，对话里只出现「连接超时建议重试」；已经入库的 PDF 留下，同一会话可以只补没做完的那一步。

**Architecture:** 超时判定和固定一句放在 `layout_timeout.py`。出练习卷的两个 except（出题、渲染）和批量出卷在判定为中断时只回这一句，不删已 commit 的产物。对话层若看到工具整句返回该文案，把助手回复改成这一句，避免模型改写。拆题、对考点仍走原来的 `tool_error_user_text`。产品里不做计时器；20 分钟和环境作废由验收手记。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、pytest、LangChain ToolMessage。

---

## File map

- Create: `backend/app/services/layout_timeout.py` — 固定一句、连接中断判定、彩色说明写出的超时壳、对话里原样转述。
- Create: `backend/tests/test_layout_timeout.py`
- Modify: `backend/app/agent/tools.py` — 出练习卷（单考点与批量）连接中断只回这一句；对考点 except 不改。
- Modify: `backend/app/agent/prompts.py` — 工具整句返回该文案时必须原样发给老师。
- Modify: `backend/app/api/chat.py` — 本轮工具结果若是该文案，入库的助手回复用这一句。
- Modify: `backend/tests/test_humanize_errors.py` — 拆题/对考点的 TimeoutError 仍带原来的失败说明。
- Do not modify `pdf_render.py`、删除 PDF、一个考点一份、图文判定、彩色说明排版。
- Do not add an in-app timer, banner, MCP, or availability SLO.

实现从当前 `main` 拉分支。不要依赖尚未合并的 US-2、US-3、US-4 或 US-5。当前 `main` 没有彩色考点说明 PDF 写出；排彩色说明的超时由 `run_layout_write` 覆盖，US-4 合并后把写出回调接到这个函数即可。

Windows 上跑 pytest 时把 `TEMP`/`TMP` 指到仓库里的 `tmp`（避免 `pytest-of-Eason Zhao` 的 WinError 5）。

### Task 1: 固定一句，只认连接中断

**Files:**
- Create: `backend/app/services/layout_timeout.py`
- Create: `backend/tests/test_layout_timeout.py`
- Modify: `backend/tests/test_humanize_errors.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.layout_timeout import (
    TIMEOUT_MESSAGE,
    assistant_text_after_layout_timeout,
    is_connection_timeout,
    run_layout_write,
    user_text_for_layout_timeout,
)
from app.services.llm_errors import tool_error_user_text


def test_timeout_message_is_exact_sentence_without_secrets():
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE
    assert "Traceback" not in TIMEOUT_MESSAGE
    assert "sk-" not in TIMEOUT_MESSAGE


def test_is_connection_timeout_matches_interrupts_only():
    assert is_connection_timeout(TimeoutError()) is True
    assert is_connection_timeout(TimeoutError("timed out")) is True
    assert is_connection_timeout(ConnectionResetError()) is True
    assert is_connection_timeout(ConnectionError("Connection refused")) is True
    assert is_connection_timeout(Exception("ConnectError: failed")) is True
    assert is_connection_timeout(ValueError("nope")) is False
    assert is_connection_timeout(ValueError("KaiTi missing")) is False


def test_user_text_for_layout_timeout_is_sentence_or_none():
    assert user_text_for_layout_timeout(TimeoutError("timed out")) == TIMEOUT_MESSAGE
    assert user_text_for_layout_timeout(ValueError("KaiTi missing")) is None


def test_run_layout_write_timeout_keeps_existing_file(tmp_path: Path):
    kept = tmp_path / "考点说明.pdf"
    kept.write_bytes(b"%PDF-1.4 color")

    def boom() -> None:
        raise ConnectionResetError("reset")

    assert run_layout_write(boom) == TIMEOUT_MESSAGE
    assert kept.read_bytes() == b"%PDF-1.4 color"


def test_run_layout_write_other_errors_still_raise():
    def boom() -> None:
        raise ValueError("KaiTi missing")

    try:
        run_layout_write(boom)
    except ValueError as exc:
        assert "KaiTi" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_assistant_text_after_layout_timeout_overrides_paraphrase():
    msgs = [
        HumanMessage(content="出练习"),
        AIMessage(content=""),
        ToolMessage(content=TIMEOUT_MESSAGE, tool_call_id="1"),
        AIMessage(content="网络好像不太好，我们换个说法再试。"),
    ]
    assert assistant_text_after_layout_timeout(msgs) == TIMEOUT_MESSAGE


def test_assistant_text_after_layout_timeout_none_when_success():
    msgs = [
        ToolMessage(content="成功：练习已生成，请在界面「生成文件」中下载。", tool_call_id="1"),
        AIMessage(content="练习卷已经在生成文件里了。"),
    ]
    assert assistant_text_after_layout_timeout(msgs) is None
```

Append to `backend/tests/test_humanize_errors.py`:

```python
from app.services.layout_timeout import TIMEOUT_MESSAGE
from app.services.llm_errors import humanize_known_llm_message, tool_error_user_text


def test_humanize_response_format():
    msg = "This response_format type is unavailable now"
    out = humanize_known_llm_message(msg)
    assert out is not None
    assert "重试" in out or "分段" in out


def test_tool_error_user_text():
    s = tool_error_user_text("考点分析失败：", ValueError("random xyz"))
    assert "考点分析失败" in s
    assert "random xyz" in s


def test_structure_and_knowledge_timeout_keep_existing_copy():
    split = tool_error_user_text("拆题失败：", TimeoutError("timed out"))
    analyze = tool_error_user_text("考点分析失败：", TimeoutError("timed out"))
    assert split != TIMEOUT_MESSAGE
    assert analyze != TIMEOUT_MESSAGE
    assert "拆题失败" in split
    assert "考点分析失败" in analyze
    assert "技术说明" in split
    assert "技术说明" in analyze
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; python -m pytest tests/test_layout_timeout.py::test_timeout_message_is_exact_sentence_without_secrets -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.layout_timeout'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Connection-interrupt copy for practice PDFs and color knowledge layout."""

from __future__ import annotations

from collections.abc import Callable, Sequence

TIMEOUT_MESSAGE = "连接超时建议重试"

_INTERRUPT_MARKERS = (
    "timeout",
    "timed out",
    "connection",
    "connecterror",
    "reset",
    "refused",
)


def is_connection_timeout(exc: BaseException) -> bool:
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(marker in blob for marker in _INTERRUPT_MARKERS)


def user_text_for_layout_timeout(exc: BaseException) -> str | None:
    if is_connection_timeout(exc):
        return TIMEOUT_MESSAGE
    return None


def run_layout_write(write_fn: Callable[[], None]) -> str | None:
    """Run a color-knowledge (or other layout) write. Keep existing files on timeout."""
    try:
        write_fn()
    except Exception as exc:
        text = user_text_for_layout_timeout(exc)
        if text:
            return text
        raise
    return None


def assistant_text_after_layout_timeout(messages: Sequence[object]) -> str | None:
    for msg in messages:
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip() == TIMEOUT_MESSAGE:
            return TIMEOUT_MESSAGE
    return None
```

Do not change `tool_error_user_text` in `backend/app/services/llm_errors.py`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend; python -m pytest tests/test_layout_timeout.py tests/test_humanize_errors.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/layout_timeout.py backend/tests/test_layout_timeout.py backend/tests/test_humanize_errors.py
git commit -m "test: map layout connection interrupts to one retry sentence"
```

### Task 2: 出练习卷超时只回一句，已入库的留下

**Files:**
- Modify: `backend/app/agent/tools.py`
- Modify: `backend/tests/test_layout_timeout.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_layout_timeout.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent.tools import generate_chunk_practice_pdf, generate_chunk_practice_pdfs_batch
from app.db.models import Artifact, ExamPaper
from app.db.sync_session import sync_session
from app.main import app
from app.services.layout_timeout import TIMEOUT_MESSAGE
from app.services.storage import export_dir_for_conversation


def _ka_two_points() -> dict:
    return {
        "theme_title": "测",
        "knowledge_points": [
            {"key": "kp_a", "name": "一次函数", "summary": "s", "book_chapter_hint": "通用"},
            {"key": "kp_b", "name": "几何", "summary": "s", "book_chapter_hint": "通用"},
        ],
        "mappings": [{"question_order": 1, "knowledge_point_key": "kp_a"}],
    }


def _seed_paper_with_stored_practice(cid: str) -> tuple[str, Path]:
    pdf = export_dir_for_conversation(cid) / "practice_kp_a.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 stored-a")
    with sync_session() as session:
        paper = ExamPaper(
            conversation_id=cid,
            source_type="test",
            knowledge_analysis_json=_ka_two_points(),
        )
        session.add(paper)
        session.flush()
        session.add(
            Artifact(
                paper_id=paper.id,
                kind="pdf_question",
                path=pdf.as_posix(),
                knowledge_point_key="kp_a",
                display_name="一次函数练习卷",
            )
        )
        session.commit()
        return paper.id, pdf


def test_practice_timeout_returns_exact_sentence_keeps_stored_pdf():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        with patch(
            "app.agent.tools.generate_practice_set",
            side_effect=TimeoutError("timed out"),
        ):
            out = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert out == TIMEOUT_MESSAGE
        assert "技术说明" not in str(out)
        assert pdf.is_file()
        with sync_session() as session:
            rows = list(
                session.scalars(select(Artifact).where(Artifact.paper_id == paper_id))
            )
            assert len(rows) == 1
            assert rows[0].knowledge_point_key == "kp_a"


def test_practice_render_timeout_returns_sentence_not_font_copy():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        with (
            patch(
                "app.agent.tools.generate_practice_set",
                return_value=MagicMock(),
            ),
            patch(
                "app.agent.tools.render_practice_pdf",
                side_effect=ConnectionError("Connection refused"),
            ),
        ):
            out = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert out == TIMEOUT_MESSAGE
        assert "楷体" not in str(out)
        assert pdf.is_file()


def test_practice_render_font_error_keeps_kaiti_copy():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, _pdf = _seed_paper_with_stored_practice(cid)
        with (
            patch(
                "app.agent.tools.generate_practice_set",
                return_value=MagicMock(),
            ),
            patch(
                "app.agent.tools.render_practice_pdf",
                side_effect=ValueError("KaiTi missing"),
            ),
        ):
            out = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert out != TIMEOUT_MESSAGE
        assert "楷体" in str(out)


def test_batch_timeout_returns_only_the_sentence_and_stops():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        calls: list[str] = []

        def fake_gen(session, paper, kp, *args, **kwargs):
            calls.append(kp.key)
            if kp.key == "kp_a":
                return None
            return TIMEOUT_MESSAGE

        items = json.dumps(
            [
                {"knowledge_point_key": "kp_a"},
                {"knowledge_point_key": "kp_b"},
            ]
        )
        with patch(
            "app.agent.tools._generate_chunk_practice_pdf_for_kp",
            side_effect=fake_gen,
        ):
            out = generate_chunk_practice_pdfs_batch.invoke(
                {"paper_id": paper_id, "items_json": items}
            )
        assert out == TIMEOUT_MESSAGE
        assert "批量结果" not in str(out)
        assert calls == ["kp_a", "kp_b"]
        assert pdf.is_file()


def test_retry_unfinished_point_does_not_clear_stored_pdf():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        paper_id, pdf = _seed_paper_with_stored_practice(cid)
        with patch(
            "app.agent.tools.generate_practice_set",
            side_effect=TimeoutError("timed out"),
        ):
            first = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert first == TIMEOUT_MESSAGE
        with (
            patch(
                "app.agent.tools.generate_practice_set",
                return_value=MagicMock(),
            ),
            patch("app.agent.tools.render_practice_pdf"),
            patch("app.agent.tools.render_answer_pdf"),
        ):
            second = generate_chunk_practice_pdf.invoke(
                {"paper_id": paper_id, "knowledge_point_key": "kp_b"}
            )
        assert "成功" in str(second)
        assert pdf.is_file()
        with sync_session() as session:
            rows = list(
                session.scalars(select(Artifact).where(Artifact.paper_id == paper_id))
            )
            keys = {row.knowledge_point_key for row in rows}
            assert "kp_a" in keys
            assert "kp_b" in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; python -m pytest tests/test_layout_timeout.py::test_practice_timeout_returns_exact_sentence_keeps_stored_pdf -v`

Expected: FAIL because `generate_chunk_practice_pdf` still returns `出题失败：…技术说明：…` rather than `连接超时建议重试`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/agent/tools.py`, add to the existing llm_errors import block:

```python
from app.services.layout_timeout import TIMEOUT_MESSAGE, user_text_for_layout_timeout
from app.services.llm_errors import humanize_known_llm_message, tool_error_user_text
```

Replace the `generate_practice_set` except in `_generate_chunk_practice_pdf_for_kp` with:

```python
    except Exception as e:
        timeout = user_text_for_layout_timeout(e)
        if timeout:
            return timeout
        return tool_error_user_text("出题失败：", e)
```

Replace the PDF render except in the same function with:

```python
    except Exception as e:
        timeout = user_text_for_layout_timeout(e)
        if timeout:
            return timeout
        return f"PDF 渲染失败（检查楷体字体配置）：{e!s}"
```

Do not unlink files and do not `session.delete` artifacts in those excepts.

In `generate_chunk_practice_pdfs_batch`, replace the `if err:` branch with:

```python
            if err:
                if err == TIMEOUT_MESSAGE:
                    return TIMEOUT_MESSAGE
                lines.append(f"「{kp.name}」{err}")
            else:
                lines.append(f"「{kp.name}」练习与答案 PDF 已生成。")
```

Leave `structure_exam_paper` and `run_knowledge_analysis` excepts on `tool_error_user_text("拆题失败：", e)` / `tool_error_user_text("考点分析失败：", e)`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend; python -m pytest tests/test_layout_timeout.py tests/test_humanize_errors.py tests/test_batch_practice_tool.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools.py backend/tests/test_layout_timeout.py
git commit -m "fix: show one retry sentence when practice generation drops"
```

### Task 3: 对话里出现这一句，不改拆题和对考点

**Files:**
- Modify: `backend/app/agent/prompts.py`
- Modify: `backend/app/api/chat.py`

- [ ] **Step 1: Write the failing test**

The Task 1 tests `test_assistant_text_after_layout_timeout_overrides_paraphrase` and `test_structure_and_knowledge_timeout_keep_existing_copy` already lock the contract. Add this assertion in `backend/tests/test_layout_timeout.py` (keep it failing until chat.py imports the helper in the live path by reading the module):

```python
def test_chat_runner_imports_layout_timeout_relay():
    import inspect

    from app.api import chat as chat_mod

    source = inspect.getsource(chat_mod)
    assert "assistant_text_after_layout_timeout" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; python -m pytest tests/test_layout_timeout.py::test_chat_runner_imports_layout_timeout_relay -v`

Expected: FAIL with `assert 'assistant_text_after_layout_timeout' in source`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/agent/prompts.py`, immediately after the bullet that starts with `**禁止**把工具返回内容原文复述给用户`, add:

```
- 例外：工具返回原文恰好是「连接超时建议重试」时，必须把这一句原样发给用户，不要改写，不要加「技术说明」、密钥、堆栈或卷子正文。
```

In `backend/app/api/chat.py`, add to the services imports:

```python
from app.services.layout_timeout import assistant_text_after_layout_timeout
```

Replace the block that currently does:

```python
                out_text = _last_assistant_text(msgs) or "".join(streamed_buf)
                if not streamed_any and out_text:
                    await out_q.put(_sse({"event": "token", "data": {"t": out_text}}))
```

with:

```python
                out_text = _last_assistant_text(msgs) or "".join(streamed_buf)
                timeout_text = assistant_text_after_layout_timeout(msgs)
                if timeout_text:
                    out_text = timeout_text
                if not streamed_any and out_text:
                    await out_q.put(_sse({"event": "token", "data": {"t": out_text}}))
```

Do not put this sentence into `streamError` / `请求失败：`. Do not change the `structure_exam_paper` or `analyze_knowledge` excepts.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend; python -m pytest tests/test_layout_timeout.py tests/test_humanize_errors.py tests/test_batch_practice_tool.py tests/test_agent_thread_repair.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/prompts.py backend/app/api/chat.py backend/tests/test_layout_timeout.py
git commit -m "fix: keep the timeout sentence in the teacher chat"
```

---

## Spec coverage

- 出练习卷连接中断只回「连接超时建议重试」，无密钥/堆栈/卷子正文/技术说明：Task 1、Task 2。
- 排彩色说明同一句：Task 1 的 `run_layout_write`（当前 main 无彩色 PDF 写出；不改 US-4 排版）。
- 这句话出现在老师正在看的对话里：Task 3。
- 已入库 PDF 不撤：Task 2。
- 同一会话再试未完成的部分、已成功的不清掉：Task 2 `test_retry_unfinished_point_does_not_clear_stored_pdf`。
- 拆题、对考点仍用现在的失败说明：Task 1 `test_structure_and_knowledge_timeout_keep_existing_copy`；Task 2 不改那两处 except。
- 20 分钟秒表、环境失败作废：不写产品代码。
- 不改一个考点一份、图文判定、彩色排版、删除 PDF；不新增 MCP、计时器、可用性百分比。

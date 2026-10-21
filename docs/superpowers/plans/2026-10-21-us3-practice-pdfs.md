# US-3 每个考点一份练习卷 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 这套卷上每个考点各有一份练习卷 PDF；该有图的才重做那一份；连接中断只显示「连接超时建议重试」，已入库的留下。

**Architecture:** 纯函数决定跳过、重做还是入库。新的出卷入口按考点逐个起草，判断通过后才写入现在的库。原来的「一次最多 8 个」不再当作做完。彩色说明和删除不改。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、pytest。

---

## File map

- Create: `backend/app/services/practice_fill.py` — 该不该有图、空白、跳过已有、重做循环、超时。
- Create: `backend/tests/test_practice_fill.py` — 不调用真实模型和渲染。
- Modify: `backend/app/services/llm_errors.py` — 这种超时返回固定一句，不附技术说明。
- Modify: `backend/app/agent/tools.py` — 判断通过后才入库；新增按整卷考点出卷的入口。
- Modify: `backend/app/agent/prompts.py` — 不再把 8 个上限写成做完。
- Do not modify the color-explanation path, PDF delete, or the old batch cap test.

实现从当前 `main` 拉分支。不要依赖尚未合并的 US-2 分支。超时句子在本模块里写成同一个字面量。

### Task 1: 判断哪些考点必须有图

**Files:**
- Create: `backend/app/services/practice_fill.py`
- Test: `backend/tests/test_practice_fill.py`

- [ ] **Step 1: Write the failing test**

```python
from app.services.practice_fill import needs_figure


def test_needs_figure_matches_diagram_topics_not_the_bare_word_function():
    assert needs_figure("几何", ["求阴影部分面积"]) is True
    assert needs_figure("二次函数", ["画出函数图像"]) is True
    assert needs_figure("欧姆定律", ["画出电路"]) is True
    assert needs_figure("实验室制氧", ["画出化学装置"]) is True
    assert needs_figure("一次函数", ["求解析式"]) is False
    assert needs_figure("牛顿第一定律", ["用文字说明惯性"]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_practice_fill.py::test_needs_figure_matches_diagram_topics_not_the_bare_word_function -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.practice_fill'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Decide which practice papers to skip, redo, or store."""

from __future__ import annotations

_FIGURE_MARKERS = ("几何", "函数图像", "函数图象", "电路", "化学装置")


def needs_figure(point_name: str, stems: list[str]) -> bool:
    blob = f"{point_name}\n" + "\n".join(stems)
    return any(marker in blob for marker in _FIGURE_MARKERS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_practice_fill.py::test_needs_figure_matches_diagram_topics_not_the_bare_word_function -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/practice_fill.py backend/tests/test_practice_fill.py
git commit -m "test: detect practice topics that require a figure"
```

### Task 2: 空白不入库，缺图只重做这一份

**Files:**
- Modify: `backend/app/services/practice_fill.py`
- Test: `backend/tests/test_practice_fill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_practice_outcome_retries_blank_and_missing_figure_only():
    from app.services.practice_fill import practice_outcome

    assert practice_outcome("几何", ["求面积"], ["geometry"], [False]) == "store"
    assert practice_outcome("几何", ["求面积"], ["none"], [False]) == "retry"
    assert practice_outcome("一次函数", ["求解析式"], ["none"], [False]) == "store"
    assert practice_outcome("概念", ["", "  "], ["none"], [False]) == "retry"
    assert practice_outcome("电路", [""], ["none"], [True]) == "store"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_practice_fill.py::test_practice_outcome_retries_blank_and_missing_figure_only -v`

Expected: FAIL with `ImportError: cannot import name 'practice_outcome'`

- [ ] **Step 3: Write minimal implementation**

Add to `practice_fill.py`:

```python
def _has_text(stems: list[str]) -> bool:
    return any((stem or "").strip() for stem in stems)


def _has_figure(figure_kinds: list[str], uses_paper_figure: list[bool]) -> bool:
    if any(kind and kind != "none" for kind in figure_kinds):
        return True
    return any(uses_paper_figure)


def practice_outcome(
    point_name: str,
    stems: list[str],
    figure_kinds: list[str],
    uses_paper_figure: list[bool],
) -> str:
    has_text = _has_text(stems)
    has_figure = _has_figure(figure_kinds, uses_paper_figure)
    if not has_text and not has_figure:
        return "retry"
    if needs_figure(point_name, stems) and not has_figure:
        return "retry"
    return "store"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_practice_fill.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/practice_fill.py backend/tests/test_practice_fill.py
git commit -m "feat: retry a practice paper that is blank or missing a required figure"
```

### Task 3: 已有的跳过，中断不撤已入库的

**Files:**
- Modify: `backend/app/services/practice_fill.py`
- Modify: `backend/app/services/llm_errors.py`
- Test: `backend/tests/test_practice_fill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_fill_skips_stored_points_and_timeout_keeps_them():
    from app.services.llm_errors import tool_error_user_text
    from app.services.practice_fill import TIMEOUT_MESSAGE, PracticeFillTimeout, fill_practice_pdfs

    points = [("kp_a", "一次函数"), ("kp_b", "几何")]
    calls: list[str] = []

    def generate_one(key: str, name: str):
        calls.append(key)
        if key == "kp_b":
            raise PracticeFillTimeout(["kp_a"])
        return ("store", key)

    try:
        fill_practice_pdfs(points, stored_keys=["kp_a"], generate_one=generate_one)
        raised = False
    except PracticeFillTimeout as exc:
        raised = True
        assert exc.stored_keys == ["kp_a"]
    assert raised is True
    assert calls == ["kp_b"]
    assert tool_error_user_text("", PracticeFillTimeout(["kp_a"])) == TIMEOUT_MESSAGE
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_practice_fill.py::test_fill_skips_stored_points_and_timeout_keeps_them -v`

Expected: FAIL with `ImportError: cannot import name 'fill_practice_pdfs'`

- [ ] **Step 3: Write minimal implementation**

Add to `practice_fill.py`:

```python
from collections.abc import Callable

TIMEOUT_MESSAGE = "连接超时建议重试"


class PracticeFillTimeout(Exception):
    """The model call timed out while drafting one practice paper."""

    def __init__(self, stored_keys: list[str]):
        self.stored_keys = list(stored_keys)
        super().__init__(TIMEOUT_MESSAGE)


GenerateOne = Callable[[str, str], tuple[str, str]]


def fill_practice_pdfs(
    points: list[tuple[str, str]],
    stored_keys: list[str],
    generate_one: GenerateOne,
) -> list[str]:
    # Retry until the page is acceptable. There is no attempt cap.
    stored = list(stored_keys)
    stored_set = set(stored)
    while True:
        missing = [item for item in points if item[0] not in stored_set]
        if not missing:
            return [item[0] for item in points]
        key, name = missing[0]
        try:
            action, stored_key = generate_one(key, name)
        except PracticeFillTimeout:
            raise PracticeFillTimeout(stored) from None
        if action == "store":
            stored.append(stored_key)
            stored_set.add(stored_key)
```

In `tool_error_user_text`, before the other branches:

```python
    from app.services.practice_fill import TIMEOUT_MESSAGE, PracticeFillTimeout

    if isinstance(exc, PracticeFillTimeout):
        return TIMEOUT_MESSAGE
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_practice_fill.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/practice_fill.py backend/app/services/llm_errors.py backend/tests/test_practice_fill.py
git commit -m "feat: skip stored practice papers and keep them on timeout"
```

### Task 4: 整卷出卷在判断通过后才入库

**Files:**
- Modify: `backend/app/agent/tools.py` around `_generate_chunk_practice_pdf_for_kp` and `AGENT_TOOLS`
- Modify: `backend/app/agent/prompts.py` step 4
- Test: `backend/tests/test_practice_fill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_generate_one_for_tool_does_not_store_a_retry(monkeypatch):
    from app.services.practice_fill import generate_one_for_tool

    stored: list[str] = []

    def draft(key: str, name: str):
        return (["画出函数图像"], ["none"], [False], {"key": key})

    def store(payload: dict):
        stored.append(payload["key"])

    action, key = generate_one_for_tool(
        "kp_plot",
        "二次函数",
        draft=draft,
        store=store,
    )
    assert action == "retry"
    assert stored == []
    assert key == "kp_plot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_practice_fill.py::test_generate_one_for_tool_does_not_store_a_retry -v`

Expected: FAIL with `ImportError: cannot import name 'generate_one_for_tool'`

- [ ] **Step 3: Write minimal implementation**

Add to `practice_fill.py`:

```python
def generate_one_for_tool(key: str, name: str, *, draft, store) -> tuple[str, str]:
    stems, figure_kinds, uses_paper_figure, payload = draft(key, name)
    action = practice_outcome(name, stems, figure_kinds, uses_paper_figure)
    if action == "store":
        store(payload)
    return action, key
```

In `tools.py`, add a tool `generate_all_practice_pdfs(paper_id: str) -> str`. It loads the paper's knowledge points and the `pdf_question` artifact keys already stored for that paper. It calls `fill_practice_pdfs`. `generate_one` drafts with the existing `generate_practice_set`, then `generate_one_for_tool`. `store` is the current render-and-artifact block that starts at `out_dir = export_dir_for_conversation(...)` and ends at `session.commit(); return None` inside `_generate_chunk_practice_pdf_for_kp`. Move that block into `store_drafted_practice(...)` and call it from both the old function and the new store callback. A `"retry"` result must not call it.

On `PracticeFillTimeout`, do not delete files and return `tool_error_user_text("", exc)`. On success, return a short Chinese line that the practice PDFs are stored, one per knowledge point. Other exceptions do not store the current point and do not delete stored files; return `tool_error_user_text("出题失败：", exc)`.

Register the tool in `AGENT_TOOLS`.

In `prompts.py` step 4, replace the sentence that the batch must stop at 8 points with: 老师要这套卷的练习卷时，调用一次 `generate_all_practice_pdfs(paper_id)`。它会跳过已有练习卷的考点，并一直补到每个考点都有一份。不要因为旧的 8 个上限停止。

Leave `generate_chunk_practice_pdfs_batch` and `test_batch_rejects_over_cap` unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_practice_fill.py tests/test_batch_practice_tool.py -v`

Expected: PASS. The old cap test still rejects a batch over the cap. The new tests accept store-or-retry without writing a file on retry.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/practice_fill.py backend/app/agent/tools.py backend/app/agent/prompts.py backend/tests/test_practice_fill.py
git commit -m "feat: store one practice PDF per knowledge point after it passes"
```

## Spec coverage

- 已有练习卷的考点跳过：Task 3。
- 生成成功才入库，空白和缺图不入库：Task 2 与 Task 4。
- 几何、函数图像、电路、化学装置必须有图；单独的「函数」不强迫配图：Task 1。
- 连接超时显示「连接超时建议重试」，已入库的留下：Task 3 与 Task 4。
- 8 个上限不再当作做完：Task 4 的新入口和提示词。旧批量工具的上限测试保持不变。
- 不改彩色说明和删除：计划没有改那些文件。

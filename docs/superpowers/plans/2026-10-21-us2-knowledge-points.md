# US-2 每题至少一个考点 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 拆出来的每一题至少有一个考点；缺的只重问该题直到有结果；认不出的页不编题；连接超时只显示「连接超时建议重试」。

**Architecture:** 纯函数判断缺哪些题、合并补上的考点。考点分析工具在第一次分析后调用这个函数。认不出的页在拆题前停住，不调用模型。老师仍看现有的结构化结果面板，面板多显示每题考点名。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、pytest、React 18。

---

## File map

- Create: `backend/app/services/knowledge_fill.py` — 缺题、合并、重问循环、超时类型、认不出的页。
- Create: `backend/tests/test_knowledge_fill.py` — 不调用真实模型。
- Modify: `backend/app/services/paper_ai.py` — 增加只分析一道题的函数。
- Modify: `backend/app/agent/tools.py` — 拆题前拦截认不出的页；考点分析后补缺。
- Modify: `backend/app/services/llm_errors.py` — 连接超时变成固定一句，不附技术说明。
- Modify: `backend/app/api/chat.py` — 结构化接口带上每题考点名。
- Modify: `frontend/src/components/StructuredResultPanel.tsx` — 在现有面板列出每题考点。
- Do not modify practice PDF tools, markdown export layout, or color-PDF work.

### Task 1: 找出没有考点的题

**Files:**
- Create: `backend/app/services/knowledge_fill.py`
- Test: `backend/tests/test_knowledge_fill.py`

- [ ] **Step 1: Write the failing test**

```python
from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    PaperSection,
    QuestionItem,
    QuestionKnowledgeMapping,
    StructuredPaper,
)
from app.services.knowledge_fill import missing_orders


def _paper() -> StructuredPaper:
    return StructuredPaper(
        title="t",
        sections=[
            PaperSection(
                title="一",
                questions=[
                    QuestionItem(order_index=1, qtype="选择", stem="第一题"),
                    QuestionItem(order_index=2, qtype="填空", stem="第二题"),
                ],
            )
        ],
    )


def test_missing_orders_skips_questions_that_already_have_a_point():
    paper = _paper()
    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[
            KnowledgePointItem(key="kp_a", name="考点甲", summary="甲"),
        ],
        mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a")],
    )
    assert missing_orders(paper, analysis) == [2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py::test_missing_orders_skips_questions_that_already_have_a_point -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.knowledge_fill'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Fill knowledge-point gaps one question at a time."""

from __future__ import annotations

from app.models.schemas import KnowledgeAnalysisResult, StructuredPaper


def question_orders(paper: StructuredPaper) -> list[int]:
    orders: list[int] = []
    for sec in paper.sections:
        for q in sec.questions:
            orders.append(int(q.order_index))
    return orders


def missing_orders(paper: StructuredPaper, analysis: KnowledgeAnalysisResult) -> list[int]:
    covered: set[int] = set()
    for mapping in analysis.mappings:
        if (mapping.knowledge_point_key or "").strip():
            covered.add(int(mapping.question_order))
    return [order for order in question_orders(paper) if order not in covered]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py::test_missing_orders_skips_questions_that_already_have_a_point -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_fill.py backend/tests/test_knowledge_fill.py
git commit -m "test: detect questions that have no knowledge point"
```

### Task 2: 只重问缺考点的题，直到有结果

**Files:**
- Modify: `backend/app/services/knowledge_fill.py`
- Test: `backend/tests/test_knowledge_fill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_fill_retries_only_the_empty_question_until_it_has_a_point():
    from app.services.knowledge_fill import fill_missing_knowledge

    paper = _paper()
    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[KnowledgePointItem(key="kp_a", name="考点甲", summary="甲")],
        mappings=[QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a")],
    )
    calls: list[int] = []

    def ask_one(order: int, stem: str):
        calls.append(order)
        if len(calls) < 2:
            return KnowledgeAnalysisResult(theme_title="主题", knowledge_points=[], mappings=[])
        return KnowledgeAnalysisResult(
            theme_title="主题",
            knowledge_points=[KnowledgePointItem(key="kp_b", name="考点乙", summary="乙")],
            mappings=[QuestionKnowledgeMapping(question_order=order, knowledge_point_key="kp_b")],
        )

    filled = fill_missing_knowledge(paper, analysis, ask_one)
    assert calls == [2, 2]
    keys = [m.knowledge_point_key for m in filled.mappings if m.question_order == 1]
    assert keys == ["kp_a"]
    keys2 = [m.knowledge_point_key for m in filled.mappings if m.question_order == 2]
    assert keys2 == ["kp_b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py::test_fill_retries_only_the_empty_question_until_it_has_a_point -v`

Expected: FAIL with `ImportError: cannot import name 'fill_missing_knowledge'`

- [ ] **Step 3: Write minimal implementation**

Add to `knowledge_fill.py`:

```python
from collections.abc import Callable

from app.models.schemas import KnowledgePointItem, QuestionKnowledgeMapping


AskOne = Callable[[int, str], KnowledgeAnalysisResult]


def _stem_for(paper: StructuredPaper, order: int) -> str:
    for sec in paper.sections:
        for q in sec.questions:
            if int(q.order_index) == order:
                return q.stem
    return ""


def merge_fill(
    base: KnowledgeAnalysisResult,
    extra: KnowledgeAnalysisResult,
    only_order: int,
) -> KnowledgeAnalysisResult:
    points = list(base.knowledge_points)
    known = {p.key for p in points}
    for point in extra.knowledge_points:
        if point.key not in known and (point.key or "").strip():
            points.append(point)
            known.add(point.key)
    mappings = list(base.mappings)
    for mapping in extra.mappings:
        if int(mapping.question_order) != only_order:
            continue
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        mappings.append(
            QuestionKnowledgeMapping(question_order=only_order, knowledge_point_key=key)
        )
    return base.model_copy(
        update={"knowledge_points": points, "mappings": mappings}
    )


def fill_missing_knowledge(
    paper: StructuredPaper,
    analysis: KnowledgeAnalysisResult,
    ask_one: AskOne,
) -> KnowledgeAnalysisResult:
    while True:
        missing = missing_orders(paper, analysis)
        if not missing:
            return analysis
        order = missing[0]
        try:
            extra = ask_one(order, _stem_for(paper, order))
        except KnowledgeFillTimeout:
            raise KnowledgeFillTimeout(analysis) from None
        analysis = merge_fill(analysis, extra, order)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py -v`

Expected: PASS for both tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_fill.py backend/tests/test_knowledge_fill.py
git commit -m "feat: re-ask only questions that still lack a knowledge point"
```

### Task 3: 认不出的页不产生题目

**Files:**
- Modify: `backend/app/services/knowledge_fill.py`
- Modify: `backend/app/agent/tools.py` around `structure_exam_paper`
- Test: `backend/tests/test_knowledge_fill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_unreadable_page_is_detected_without_inventing_questions():
    from app.services.knowledge_fill import UNREADABLE_PAGE, is_unreadable_page

    assert is_unreadable_page("   \n  ") is True
    assert is_unreadable_page("???") is True
    assert is_unreadable_page("1. 已知三角形ABC，求角A。") is False
    assert UNREADABLE_PAGE == "这一页无法识别"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py::test_unreadable_page_is_detected_without_inventing_questions -v`

Expected: FAIL with `ImportError: cannot import name 'is_unreadable_page'`

- [ ] **Step 3: Write minimal implementation**

Add to `knowledge_fill.py`:

```python
UNREADABLE_PAGE = "这一页无法识别"


def is_unreadable_page(raw_text: str) -> bool:
    text = (raw_text or "").strip()
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return cjk < 4 and letters < 4
```

In `structure_exam_paper`, after the paper is loaded and before `structure_paper_text`:

```python
from app.services.knowledge_fill import UNREADABLE_PAGE, is_unreadable_page
```

Inside the function, replace the call path start with:

```python
        if is_unreadable_page(p.raw_text):
            return UNREADABLE_PAGE
        try:
            sp = structure_paper_text(p.raw_text)
```

Do not assign `parsed_json` on that return.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py::test_unreadable_page_is_detected_without_inventing_questions -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_fill.py backend/app/agent/tools.py backend/tests/test_knowledge_fill.py
git commit -m "feat: skip structuring when a page has no readable text"
```

### Task 4: 连接超时不编考点

**Files:**
- Modify: `backend/app/services/knowledge_fill.py`
- Modify: `backend/app/services/llm_errors.py`
- Modify: `backend/app/services/paper_ai.py`
- Modify: `backend/app/agent/tools.py` `run_knowledge_analysis`
- Test: `backend/tests/test_knowledge_fill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_timeout_stops_without_a_fake_point_and_uses_the_fixed_sentence():
    from app.services.knowledge_fill import TIMEOUT_MESSAGE, KnowledgeFillTimeout, fill_missing_knowledge
    from app.services.llm_errors import tool_error_user_text

    paper = _paper()
    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[],
        mappings=[],
    )

    def ask_one(order: int, stem: str):
        raise KnowledgeFillTimeout(analysis)

    try:
        fill_missing_knowledge(paper, analysis, ask_one)
        raised = False
    except KnowledgeFillTimeout as exc:
        raised = True
        assert exc.analysis.mappings == []
    assert raised is True
    assert tool_error_user_text("", KnowledgeFillTimeout(analysis)) == TIMEOUT_MESSAGE
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py::test_timeout_stops_without_a_fake_point_and_uses_the_fixed_sentence -v`

Expected: FAIL with `ImportError: cannot import name 'KnowledgeFillTimeout'`

- [ ] **Step 3: Write minimal implementation**

Add to `knowledge_fill.py`:

```python
TIMEOUT_MESSAGE = "连接超时建议重试"


class KnowledgeFillTimeout(Exception):
    """The model call timed out while filling one question."""

    def __init__(self, analysis: KnowledgeAnalysisResult):
        self.analysis = analysis
        super().__init__(TIMEOUT_MESSAGE)


def is_connection_timeout(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    return "timeout" in name or "timed out" in text or "timeout" in text
```

Change the loop in `fill_missing_knowledge` so `ask_one` may raise `KnowledgeFillTimeout`. Do not catch it. Do not add a mapping when it is raised.

In `llm_errors.py` `tool_error_user_text`, before other branches:

```python
    from app.services.knowledge_fill import TIMEOUT_MESSAGE, KnowledgeFillTimeout

    if isinstance(exc, KnowledgeFillTimeout):
        return TIMEOUT_MESSAGE
```

Add `analyze_one_question` to `paper_ai.py` after `analyze_knowledge`:

```python
def analyze_one_question(order: int, stem: str, alignment: dict) -> KnowledgeAnalysisResult:
    sys = (
        "只为下面这一道题标注至少一个考点。可以有多个。"
        "不要改题号。name 与 summary 用中文。key 用英文小写加下划线。"
        f"{_JSON_ONLY}\n{_KNOWLEDGE_SCHEMA}"
    )
    human = f"对齐信息：{alignment}\n\n第{order}题：{stem}"
    raw = _invoke_text(sys, human)
    return parse_pydantic_from_llm_text(raw, KnowledgeAnalysisResult)
```

In `run_knowledge_analysis`, after `ka = analyze_knowledge(...)` succeeds:

```python
        from app.services.knowledge_fill import (
            KnowledgeFillTimeout,
            fill_missing_knowledge,
            is_connection_timeout,
        )
        from app.services.paper_ai import analyze_one_question

        def ask_one(order: int, stem: str) -> KnowledgeAnalysisResult:
            try:
                return analyze_one_question(order, stem, p.alignment_json or {})
            except Exception as exc:
                if is_connection_timeout(exc):
                    raise KnowledgeFillTimeout() from exc
                raise

        try:
            ka = fill_missing_knowledge(sp, ka, ask_one)
        except KnowledgeFillTimeout as exc:
            p.knowledge_analysis_json = exc.analysis.model_dump()
            session.add(p)
            session.commit()
            return tool_error_user_text("", exc)
```

On timeout, save `exc.analysis` (points already returned, none invented for the timed-out question) and return only the fixed sentence. On success, save the filled `ka` as today.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_fill.py backend/app/services/llm_errors.py backend/app/services/paper_ai.py backend/app/agent/tools.py backend/tests/test_knowledge_fill.py
git commit -m "feat: surface a fixed timeout sentence instead of a fake knowledge point"
```

### Task 5: 在现有拆题结果里显示考点

**Files:**
- Modify: `backend/app/api/chat.py` `get_paper_structured` return dict around the `anomalies` field
- Modify: `frontend/src/components/StructuredResultPanel.tsx`
- Test: `backend/tests/test_knowledge_fill.py`

- [ ] **Step 1: Write the failing test**

```python
def test_question_point_names_lists_every_name_on_that_question():
    from app.services.knowledge_fill import question_point_names

    analysis = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[
            KnowledgePointItem(key="kp_a", name="考点甲", summary="甲"),
            KnowledgePointItem(key="kp_b", name="考点乙", summary="乙"),
        ],
        mappings=[
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a"),
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_b"),
        ],
    )
    assert question_point_names(analysis) == [
        {"order_index": 1, "names": ["考点甲", "考点乙"]},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py::test_question_point_names_lists_every_name_on_that_question -v`

Expected: FAIL with `ImportError: cannot import name 'question_point_names'`

- [ ] **Step 3: Write minimal implementation**

Add to `knowledge_fill.py`:

```python
def question_point_names(analysis: KnowledgeAnalysisResult) -> list[dict]:
    by_order: dict[int, list[str]] = {}
    names = {point.key: point.name for point in analysis.knowledge_points}
    for mapping in analysis.mappings:
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        by_order.setdefault(int(mapping.question_order), [])
        by_order[int(mapping.question_order)].append(names.get(key, key))
    return [
        {"order_index": order, "names": by_order[order]}
        for order in sorted(by_order)
    ]
```

In `get_paper_structured`, add to the returned dict:

```python
    from app.models.schemas import KnowledgeAnalysisResult
    from app.services.knowledge_fill import question_point_names

    point_rows: list[dict] = []
    if p.knowledge_analysis_json:
        point_rows = question_point_names(
            KnowledgeAnalysisResult.model_validate(p.knowledge_analysis_json)
        )
```

Include `"question_knowledge": point_rows` in the JSON response.

In `StructuredResultPanel.tsx`, extend `StructuredPayload`:

```tsx
  question_knowledge?: { order_index: number; names: string[] }[];
```

Under the existing summary block, render:

```tsx
      {data?.question_knowledge?.length ? (
        <ul className="mb-3 text-sm text-slate-800">
          {data.question_knowledge.map((row) => (
            <li key={row.order_index}>
              第 {row.order_index} 题：{row.names.join("、")}
            </li>
          ))}
        </ul>
      ) : null}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_fill.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_fill.py backend/app/api/chat.py frontend/src/components/StructuredResultPanel.tsx backend/tests/test_knowledge_fill.py
git commit -m "feat: show each question's knowledge points on the existing result"
```

## Spec coverage

- 只重问缺考点的题，直到有结果：Task 2。
- 已有考点的题不动，多个考点都留：Task 2 与 Task 5。
- 认不出的页不编题，并说明无法识别：Task 3。
- 超时显示「连接超时建议重试」，不编假考点：Task 4。
- 老师在现有拆题结果里看见考点：Task 5。
- 不改练习卷和彩色说明：计划没有改那些文件。

# US-4 彩色考点说明 PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 考点分析成功后，老师从「生成文件」里的「考点说明」打开一份有标题、分块和颜色的 PDF，而不是 Markdown。

**Architecture:** 纯函数从已有考点结果抽出标题和分块。本地排出 PDF，判断通过后写入现在的库。阅读入口改指这份 PDF。磁盘上的旧 Markdown 不删。

**Tech Stack:** Python 3.11、fpdf2、Pydantic、pytest、React 18。

---

## File map

- Create: `backend/app/services/knowledge_pdf.py` — 标题与分块、颜色、写出 PDF、跳过已有、超时。
- Create: `backend/tests/test_knowledge_pdf.py`
- Modify: `backend/app/services/llm_errors.py` — 这种超时返回固定一句。
- Modify: `backend/app/agent/tools.py` — 分析成功后写出 PDF 并入库。
- Modify: `backend/app/api/chat.py` — 产物列表把「考点说明」指到 PDF。
- Modify: `frontend/src/components/ArtifactCenter.tsx` 与 `frontend/src/components/ConversationSidebar.tsx` — 分类名仍是「考点说明」。
- Do not delete Markdown files. Do not change practice PDF generation or delete.

实现从当前 `main` 拉分支。不要依赖尚未合并的 US-2 或 US-3 分支。

### Task 1: 抽出标题和考点分块

**Files:**
- Create: `backend/app/services/knowledge_pdf.py`
- Test: `backend/tests/test_knowledge_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
from app.models.schemas import (
    KnowledgeAnalysisResult,
    KnowledgePointItem,
    QuestionKnowledgeMapping,
)
from app.services.knowledge_pdf import knowledge_pdf_blocks


def _ka() -> KnowledgeAnalysisResult:
    return KnowledgeAnalysisResult(
        theme_title="二次函数综合",
        knowledge_points=[
            KnowledgePointItem(key="kp_a", name="顶点式", summary="配方法求顶点", book_chapter_hint="九下"),
            KnowledgePointItem(key="kp_b", name="图像性质", summary="开口与对称轴", book_chapter_hint="九下"),
        ],
        mappings=[
            QuestionKnowledgeMapping(question_order=1, knowledge_point_key="kp_a"),
            QuestionKnowledgeMapping(question_order=2, knowledge_point_key="kp_a"),
            QuestionKnowledgeMapping(question_order=3, knowledge_point_key="kp_b"),
        ],
    )


def test_knowledge_pdf_blocks_groups_questions_under_each_point():
    blocks = knowledge_pdf_blocks(_ka(), {"grade_min": "初三", "grade_max": "初三", "subject": "数学"})
    assert blocks["title"] == "初三～初三 · 数学 · 二次函数综合"
    assert [b["name"] for b in blocks["points"]] == ["顶点式", "图像性质"]
    assert blocks["points"][0]["summary"] == "配方法求顶点"
    assert blocks["points"][0]["orders"] == [1, 2]
    assert blocks["points"][1]["orders"] == [3]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py::test_knowledge_pdf_blocks_groups_questions_under_each_point -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.knowledge_pdf'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Color knowledge-point explanation PDF from an existing analysis."""

from __future__ import annotations

from app.models.schemas import KnowledgeAnalysisResult


def knowledge_pdf_blocks(ka: KnowledgeAnalysisResult, alignment: dict) -> dict:
    g1 = alignment.get("grade_min", "")
    g2 = alignment.get("grade_max", "")
    sub = alignment.get("subject", "")
    title = f"{g1}～{g2} · {sub} · {ka.theme_title}"
    orders_by_key: dict[str, list[int]] = {}
    for mapping in ka.mappings:
        key = (mapping.knowledge_point_key or "").strip()
        if not key:
            continue
        orders_by_key.setdefault(key, []).append(int(mapping.question_order))
    points = []
    for point in ka.knowledge_points:
        points.append(
            {
                "name": point.name,
                "summary": point.summary,
                "orders": orders_by_key.get(point.key, []),
            }
        )
    return {"title": title, "points": points}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py::test_knowledge_pdf_blocks_groups_questions_under_each_point -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_pdf.py backend/tests/test_knowledge_pdf.py
git commit -m "test: group knowledge-point blocks for the explanation PDF"
```

### Task 2: 排出有标题、分块和颜色的 PDF

**Files:**
- Modify: `backend/app/services/knowledge_pdf.py`
- Test: `backend/tests/test_knowledge_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

import pymupdf

from app.services.knowledge_pdf import BLOCK_FILLS, render_knowledge_pdf


def test_render_knowledge_pdf_has_title_blocks_and_color(tmp_path: Path):
    out = tmp_path / "考点说明.pdf"
    payload = knowledge_pdf_blocks(
        _ka(),
        {"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
    )
    render_knowledge_pdf(payload, out)
    raw = out.read_bytes()
    assert raw.startswith(b"%PDF-")
    doc = pymupdf.open(out)
    text = "".join(page.get_text() for page in doc)
    drawings = [d for page in doc for d in page.get_drawings()]
    doc.close()
    assert "初三" in text
    assert "数学" in text
    assert "二次函数综合" in text
    assert "顶点式" in text
    assert "图像性质" in text
    assert "第 1 题" in text
    fills = []
    for drawing in drawings:
        fill = drawing.get("fill")
        if not fill:
            continue
        if max(fill[:3]) <= 1:
            fills.append(tuple(round(c * 255) for c in fill[:3]))
        else:
            fills.append(tuple(round(c) for c in fill[:3]))
    assert "顶点式" in text and "图像性质" in text
    assert any(fill in BLOCK_FILLS for fill in fills)
```

If pymupdf reports fill as 0–1 floats, compare with a 0.02 tolerance. The test must fail if the file is not a PDF, if the title or a point name is missing, or if there is no filled rectangle.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py::test_render_knowledge_pdf_has_title_blocks_and_color -v`

Expected: FAIL with `ImportError: cannot import name 'render_knowledge_pdf'`

- [ ] **Step 3: Write minimal implementation**

Use the existing KaiTi resolver `app.services.fonts.resolve_kaiti_font` the same way `pdf_render.py` does. Palette (not a product promise, only implementation):

```python
BLOCK_FILLS = ((214, 234, 248), (252, 229, 205), (232, 218, 239))
```

`render_knowledge_pdf(payload: dict, path: Path) -> None`:

- Create an FPDF page.
- Write `payload["title"]` as the heading.
- For each point, fill a rectangle with `BLOCK_FILLS[i % 3]`, then write name, summary, and `第 {n} 题` joined with 、.
- Output must start with `%PDF-`. Do not write Markdown and rename it.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_pdf.py backend/tests/test_knowledge_pdf.py
git commit -m "feat: render a color knowledge explanation PDF with titled blocks"
```

### Task 3: 已有的跳过，中断不入库空白页

**Files:**
- Modify: `backend/app/services/knowledge_pdf.py`
- Modify: `backend/app/services/llm_errors.py`
- Test: `backend/tests/test_knowledge_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
def test_store_skips_existing_and_timeout_keeps_it():
    from app.services.knowledge_pdf import TIMEOUT_MESSAGE, KnowledgePdfTimeout, store_knowledge_pdf
    from app.services.llm_errors import tool_error_user_text

    calls = {"n": 0}

    def write_pdf():
        calls["n"] += 1
        raise KnowledgePdfTimeout(stored=True)

    out = store_knowledge_pdf(already_stored=True, write_pdf=write_pdf)
    assert out == "skip"
    assert calls["n"] == 0

    try:
        store_knowledge_pdf(already_stored=False, write_pdf=write_pdf)
        raised = False
    except KnowledgePdfTimeout as exc:
        raised = True
        assert exc.stored is False
    assert raised is True
    assert tool_error_user_text("", KnowledgePdfTimeout(stored=False)) == TIMEOUT_MESSAGE
    assert TIMEOUT_MESSAGE == "连接超时建议重试"
    assert "技术说明" not in TIMEOUT_MESSAGE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py::test_store_skips_existing_and_timeout_keeps_it -v`

Expected: FAIL with `ImportError: cannot import name 'store_knowledge_pdf'`

- [ ] **Step 3: Write minimal implementation**

```python
from collections.abc import Callable

TIMEOUT_MESSAGE = "连接超时建议重试"


class KnowledgePdfTimeout(Exception):
    def __init__(self, stored: bool):
        self.stored = stored
        super().__init__(TIMEOUT_MESSAGE)


def store_knowledge_pdf(*, already_stored: bool, write_pdf: Callable[[], None]) -> str:
    if already_stored:
        return "skip"
    try:
        write_pdf()
    except KnowledgePdfTimeout:
        raise KnowledgePdfTimeout(stored=False) from None
    return "stored"
```

In `tool_error_user_text`, before other branches:

```python
    from app.services.knowledge_pdf import TIMEOUT_MESSAGE, KnowledgePdfTimeout

    if isinstance(exc, KnowledgePdfTimeout):
        return TIMEOUT_MESSAGE
```

If `llm_errors.py` already has a timeout class that returns the same sentence, keep both checks. Do not delete the other.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_pdf.py backend/app/services/llm_errors.py backend/tests/test_knowledge_pdf.py
git commit -m "feat: skip a stored knowledge PDF and keep it on timeout"
```

### Task 4: 分析成功后入库，阅读入口改指 PDF

**Files:**
- Modify: `backend/app/agent/tools.py` `run_knowledge_analysis`
- Modify: `backend/app/api/chat.py` `_artifact_ui_category` and `_list_artifacts_sync`
- Modify: `frontend/src/components/ArtifactCenter.tsx`
- Modify: `frontend/src/components/ConversationSidebar.tsx`
- Test: `backend/tests/test_knowledge_pdf.py`

- [ ] **Step 1: Write the failing test**

```python
def test_artifact_category_for_knowledge_pdf_is_the_explanation_slot():
    from app.api.chat import _artifact_ui_category

    assert _artifact_ui_category("knowledge_pdf") == "knowledge_markdown"
    assert _artifact_ui_category("markdown") == "knowledge_markdown"
```

The category string stays `knowledge_markdown` so the existing label 「考点说明」 does not change. The listed file for a paper that has a knowledge PDF must be the PDF path, not the `.md` path.

Add a second test that `_list_artifacts_sync` prefers the PDF when both files exist. Follow the existing artifact-list tests if any; otherwise build a paper with `knowledge_markdown_path` pointing at a `.md` file and an `Artifact(kind="knowledge_pdf", path=pdf)`. Assert the item shown in category `knowledge_markdown` has `path` ending in `.pdf` and `kind == "knowledge_pdf"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py::test_artifact_category_for_knowledge_pdf_is_the_explanation_slot -v`

Expected: FAIL because `knowledge_pdf` currently maps to `other`

- [ ] **Step 3: Write minimal implementation**

`_artifact_ui_category`: `kind == "knowledge_pdf"` returns `"knowledge_markdown"`.

`_list_artifacts_sync`: if the paper has an `Artifact` with `kind == "knowledge_pdf"` and the file exists, list that as the 考点说明 item. Do not list the Markdown file for that paper in this category. If there is no PDF yet, keep listing the Markdown file as today.

`run_knowledge_analysis`: after `ka` is saved, if a `knowledge_pdf` artifact already exists for this paper, skip writing. Otherwise write `考点说明_{paper_id}.pdf` beside the existing markdown file with `render_knowledge_pdf`. Then `session.add(Artifact(..., kind="knowledge_pdf", display_name="考点说明", path=pdf_path))` and `session.commit()`. Keep writing the Markdown file as today; do not delete it.

`write_pdf` exceptions whose type name or message contains `timeout`, `timed out`, `connection`, `connecterror`, `reset`, or `refused` become `KnowledgePdfTimeout(stored=False)`. Return `tool_error_user_text("", exc)`. Do not add an Artifact row. Do not write a zero-byte file; if a partial file was created, unlink it before returning.

Frontend: keep the label 「考点说明」. Links already use `a.url`; a PDF url downloads/opens the PDF. No new page.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_knowledge_pdf.py tests/test_export_markdown.py -v`

Expected: PASS. Markdown builder tests still pass because the `.md` file is still written.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_pdf.py backend/app/agent/tools.py backend/app/api/chat.py frontend/src/components/ArtifactCenter.tsx frontend/src/components/ConversationSidebar.tsx backend/tests/test_knowledge_pdf.py
git commit -m "feat: serve the knowledge explanation as a color PDF"
```

## Spec coverage

- 分析成功后用已有结果排 PDF，不把 Markdown 改后缀，不再问模型：Task 2 与 Task 4。
- 老师从「生成文件」的「考点说明」打开 PDF：Task 4。
- 标题、按考点分块、颜色：Task 1 与 Task 2。
- 旧 Markdown 不删，阅读入口不再指向它：Task 4。
- 已有 PDF 跳过；中断显示「连接超时建议重试」，不入库空白页：Task 3 与 Task 4。
- 不改练习卷和删除：计划没有改那些文件。

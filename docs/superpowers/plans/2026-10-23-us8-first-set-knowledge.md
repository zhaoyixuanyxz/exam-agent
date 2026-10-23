# US-8 首套考点说明（薄体验）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合订切开后自动选中第一套子材料并提示继续；父本 `done` 时硬挡考点/练习工具，保证首套彩色考点说明绑在子材料上。

**Architecture:** 在 `anthology_ranges` 增加 `refuse_if_anthology_parent_done`；考点与练习工具入口调用它。Chat 拆分成功回调里 `setTargetPaperId(new_papers[0].id)` 并改提示文案。不重做考点引擎，不做产品内秒表。

**Tech Stack:** Python 3.11、LangChain `@tool`、pytest、React 18。

**Spec:** `docs/superpowers/specs/2026-10-23-us8-first-set-knowledge-design.md`

**Branch:** 继续在 `feat/us7-anthology-split` worktree（或从其拉 `feat/us8-first-set`）。Python：`exam-agent/backend/.venv`；TEMP 指 worktree `tmp`。

---

## File map

- Modify: `backend/app/services/anthology_ranges.py` — 父本拒绝文案与判定函数。
- Modify: `backend/tests/test_anthology_ranges.py` — 纯函数测试。
- Modify: `backend/app/agent/tools.py` — 考点/练习工具入口硬挡。
- Create: `backend/tests/test_anthology_parent_tools.py` — 工具级拒绝。
- Modify: `frontend/src/components/Chat.tsx` — 拆分成功选中第一套 + 提示。
- Do not modify knowledge PDF 排版、US-7 分套 API、超时固定句实现（仅回归）。

---

### Task 1: `refuse_if_anthology_parent_done` 纯函数

**Files:**
- Modify: `backend/app/services/anthology_ranges.py`
- Modify: `backend/tests/test_anthology_ranges.py`

- [ ] **Step 1: Write the failing test**

在 `test_anthology_ranges.py` 追加：

```python
from app.services.anthology_ranges import (
    ANTHOLOGY_PARENT_DONE_TOOLS,
    refuse_if_anthology_parent_done,
)


def test_refuse_if_anthology_parent_done():
    assert refuse_if_anthology_parent_done("done") == ANTHOLOGY_PARENT_DONE_TOOLS
    assert refuse_if_anthology_parent_done("needed") is None
    assert refuse_if_anthology_parent_done("none") is None
    assert refuse_if_anthology_parent_done("single_ok") is None
    assert refuse_if_anthology_parent_done(None) is None
    assert "子材料" in ANTHOLOGY_PARENT_DONE_TOOLS
```

- [ ] **Step 2: Run to fail**

Run: `cd backend; python -m pytest tests/test_anthology_ranges.py::test_refuse_if_anthology_parent_done -v`

Expected: FAIL import / AttributeError

- [ ] **Step 3: Implement**

在 `anthology_ranges.py` 增加：

```python
ANTHOLOGY_PARENT_DONE_TOOLS = (
    "该材料为已切开的合订本原件，请改选切开后的子材料再出考点/练习。"
)


def refuse_if_anthology_parent_done(status: str | None) -> str | None:
    s = (status or "none").strip() or "none"
    if s == "done":
        return ANTHOLOGY_PARENT_DONE_TOOLS
    return None
```

- [ ] **Step 4: Pass + commit**

```bash
git add backend/app/services/anthology_ranges.py backend/tests/test_anthology_ranges.py
git commit -m "feat(us8): refuse helper for anthology parent done tools"
```

---

### Task 2: 工具入口硬挡

**Files:**
- Modify: `backend/app/agent/tools.py`
- Create: `backend/tests/test_anthology_parent_tools.py`

- [ ] **Step 1: Failing tool test**

```python
# backend/tests/test_anthology_parent_tools.py
from fastapi.testclient import TestClient

from app.agent.tools import (
    generate_all_practice_pdfs,
    generate_chunk_practice_pdf,
    generate_chunk_practice_pdfs_batch,
    run_knowledge_analysis,
)
from app.db.models import ExamPaper
from app.db.session import sync_session
from app.main import app
from app.services.anthology_ranges import ANTHOLOGY_PARENT_DONE_TOOLS


def _paper(cid: str, status: str, **kwargs) -> str:
    with sync_session() as s:
        p = ExamPaper(
            conversation_id=cid,
            source_type="pdf",
            anthology_split_status=status,
            parsed_json=kwargs.get("parsed_json")
            or {
                "title": "t",
                "sections": [
                    {
                        "title": "一",
                        "questions": [
                            {
                                "order_index": 1,
                                "qtype": "填空",
                                "stem": "题",
                                "options": [],
                                "blocks": [],
                            }
                        ],
                    }
                ],
            },
            structured_confirm_status=kwargs.get("structured_confirm_status", "confirmed"),
            alignment_json=kwargs.get("alignment_json")
            or {"grade_min": "初三", "grade_max": "初三", "subject": "数学"},
            knowledge_analysis_json=kwargs.get("knowledge_analysis_json"),
        )
        s.add(p)
        s.commit()
        return p.id


def test_tools_refuse_anthology_parent_done():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pid = _paper(cid, "done")
        out = run_knowledge_analysis.invoke({"paper_id": pid})
        assert out == ANTHOLOGY_PARENT_DONE_TOOLS
        out2 = generate_chunk_practice_pdf.invoke(
            {"paper_id": pid, "knowledge_point_key": "x"}
        )
        assert out2 == ANTHOLOGY_PARENT_DONE_TOOLS
        out3 = generate_chunk_practice_pdfs_batch.invoke(
            {"paper_id": pid, "items_json": "[]"}
        )
        assert out3 == ANTHOLOGY_PARENT_DONE_TOOLS
        out4 = generate_all_practice_pdfs.invoke({"paper_id": pid})
        assert out4 == ANTHOLOGY_PARENT_DONE_TOOLS


def test_tools_allow_child_none_past_gate():
    """none 子本不应被父本文案挡住；可因缺考点分析等返回其它提示。"""
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pid = _paper(cid, "none", knowledge_analysis_json=None)
        out = generate_chunk_practice_pdf.invoke(
            {"paper_id": pid, "knowledge_point_key": "x"}
        )
        assert out != ANTHOLOGY_PARENT_DONE_TOOLS
        assert "考点" in out or "分析" in out
```

- [ ] **Step 2: Run to fail**

Run: `python -m pytest tests/test_anthology_parent_tools.py::test_tools_refuse_anthology_parent_done -v`

Expected: FAIL（工具仍往下跑或返回其它句）

- [ ] **Step 3: Wire tools**

在 `tools.py` 顶部附近：

```python
from app.services.anthology_ranges import refuse_if_anthology_parent_done
```

在 `run_knowledge_analysis` 取得 `p` 后立刻：

```python
blocked = refuse_if_anthology_parent_done(getattr(p, "anthology_split_status", None))
if blocked:
    return blocked
```

在 `generate_chunk_practice_pdf`、`generate_chunk_practice_pdfs_batch`、`generate_all_practice_pdfs` 取得 `p` 且确认存在后同样插入（在「请先完成考点分析」等检查之前或之后均可，但必须在任何生成逻辑之前；建议紧跟 `_get_paper`）。

- [ ] **Step 4: Pass + commit**

```bash
git add backend/app/agent/tools.py backend/tests/test_anthology_parent_tools.py
git commit -m "feat(us8): block knowledge and practice tools on anthology parent"
```

---

### Task 3: 前端选中第一套 + 提示

**Files:**
- Modify: `frontend/src/components/Chat.tsx`

- [ ] **Step 1: 拆分成功回调**

在现有 `split-by-pages` 成功分支（已有 `ids = j.new_papers`）中，在 `setSplitNote` / `loadPapers` 处改为：

```tsx
const ids = (j.new_papers || []) as { id: string; label?: string }[];
const first = ids[0];
const idLine = ids.map((x) => `${x.label ?? "新材料"}: ${x.id.slice(0, 8)}…`).join("；");
const hint = String((j.uncovered_pages_hint as string) || "").trim();
const firstLabel = (first?.label || "").trim() || "第一套";
setSplitNote(
  first
    ? `拆分完成。已选第一套（${firstLabel}），请拆题并确认后出考点说明。新材料：${idLine}`
    : `${j.message || "拆分完成。"} 新材料：${idLine || "（见响应）"}`,
);
setUncoveredHint(hint || null);
setSplitRanges("");
setSplitLabels([]);
autoSuggestForRef.current = null;
await loadPapers();
if (first?.id) {
  setTargetPaperId(first.id);
}
onConversationActivity?.();
```

注意：`loadPapers` 的 `useEffect` 若在 papers 变化时把 `targetPaperId` 重置为 `papers[0]`，须确认不会盖掉刚设的第一套。现有逻辑是「若 cur 仍在列表中则保留」——先 `setTargetPaperId` 再 `loadPapers`，或 `await loadPapers()` 后再 `setTargetPaperId(first.id)`。**采用先 await loadPapers 再 setTargetPaperId**，避免竞态：

```tsx
await loadPapers();
if (first?.id) setTargetPaperId(first.id);
```

- [ ] **Step 2: 手动核对**

- 合订切开后材料选择器停在第一套。  
- 提示含「请拆题并确认后出考点说明」。  
- 不自动出现拆题流式请求。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Chat.tsx
git commit -m "feat(us8): select first child paper after anthology split"
```

---

### Task 4: 回归与交回

- [ ] **Step 1: 跑测试**

```
cd backend
python -m pytest tests/test_anthology_ranges.py tests/test_anthology_parent_tools.py tests/test_anthology_split_api.py -q --basetemp=../.pytest-tmp
```

Expected: all PASS

- [ ] **Step 2: Push / 更新 PR #8（或新 PR）**

同一分支则 `git push` 更新 PR #8；若已拆分支则开新 PR。

- [ ] **Step 3: 停**

交回产品经理：对照 US-8 Given/When/Then（含 20 分钟秒表真人验收）。不在本行实现 US-9。

---

## Spec coverage self-review

| Spec | Task |
|------|------|
| 切开选中 new_papers[0] + 提示 | T3 |
| 不自动拆题/确认 | T3（无自动消息） |
| 父本 done 硬挡考点/练习四工具 | T1–T2 |
| 子材料现有路径 / 20 分钟仅验收 | T4 交回说明 |
| 超时沿用 US-6 | 不改代码 |

无 TBD；文案常量名 `ANTHOLOGY_PARENT_DONE_TOOLS` 与工具返回一致。

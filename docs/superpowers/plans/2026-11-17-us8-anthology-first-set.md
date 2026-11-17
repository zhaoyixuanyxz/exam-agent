# US-8 合订首套考点说明 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合订本分套（US-7）后，老师任选一套子材料完成「确认结构化 + 彩色考点说明 PDF 入库」，产物绑子 `paper_id`；父合订不得充当首套达标；20 分钟仅产品秒表（方案 A，无应用内计时）。

**Architecture:** 复用现有 `run_knowledge_analysis` → `knowledge_pdf` 管线；在 confirm 与考点工具入口叠加 US-7 父本门禁；自动化测试模拟父/子 `ExamPaper` 与 `anthology_split_status`；前端在父本禁用确认并引导选子套。若本分支尚无 US-7，先按 `docs/superpowers/plans/2026-10-23-us7-anthology-split.md` 交回后再做本计划 Task 2+。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy、pytest、React 18、TypeScript。

**Spec:** `docs/superpowers/specs/2026-11-17-us8-anthology-first-set-design.md`（2026-11-17 **approved**）

**Implementation status（2026-11-17，本会话收口）**

| 项 | 状态 |
|----|------|
| Task 0–4、6（代码 + 自动化） | **Done** → `6bddc0e` |
| Task 5（`docs/US-8-产品验收记录.md` 真人秒表） | **Deferred**（五模块统一产品验收） |
| `pytest tests -q` | **309 passed**, 2 skipped（本会话） |
| `npm run build` | **Pass** |
| 远程 | 收口 commit + **push** `main` |

下一模块：**US-9**（本对话范围外）。

---

## File map

- Create: `backend/tests/test_us8_anthology_first_set.py` — US-8 集成/API 回归。
- Create: `docs/US-8-产品验收记录.md` — 从 spec 附录拆出，供老师填秒表。
- Modify: `backend/app/api/chat.py` — `post_confirm_structured` 父本门禁（若 US-7 未写入则补）；`get_paper_structured` 已暴露 `anomalies`（AC-1 软提示已有）。
- Modify: `backend/app/agent/tools.py` — `run_knowledge_analysis` 拒绝父合订 `done`/`needed`。
- Modify: `frontend/src/components/StructuredResultPanel.tsx` — `anthology_split_status` 门禁文案 + 首套提示。
- Modify: `frontend/src/components/MaterialSelector.tsx` — 父 `done` 材料标注「已切开，请选下方套卷」。
- Do not modify: 分套启发式、MCP、应用内计时、US-9 默认路径。
- Do not implement: 自动选中第一套、向导式首套。

从 `main` 拉分支 `feat/us8-anthology-first-set`。Windows 跑测用仓库 `backend/.venv` 与 `pyproject.toml` 内 `--basetemp=.pytest_tmp`（跑前可删 `backend/.pytest_tmp`）。

---

### Task 0: US-7 前置检查

**Files:** 无（只读）

- [ ] **Step 1: 检查列与 API 是否存在**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -c "from app.db.models import ExamPaper; assert hasattr(ExamPaper, 'anthology_split_status')"
.\.venv\Scripts\python.exe -m pytest tests/test_anthology_ranges.py tests/test_anthology_split_api.py -q --tb=no
```

Expected: 属性存在；两测试文件存在且 PASS。

- [ ] **Step 2: 若 Step 1 失败**

停止本计划；先完整执行 `docs/superpowers/plans/2026-10-23-us7-anthology-split.md`，合并到本分支后从 Task 1 继续。

- [ ] **Step 3: 记录**

在 PR 描述写一行：`US-7 prerequisite: met`。

---

### Task 1: 父合订确认结构化硬挡（回归加固）

**Files:**
- Modify: `backend/app/api/chat.py`（`post_confirm_structured`）
- Test: `backend/tests/test_us8_anthology_first_set.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_us8_anthology_first_set.py
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models import ExamPaper
from app.db.sync_session import sync_session
from app.main import app

_PARSED = {
    "title": "2022套",
    "sections": [
        {
            "title": "一",
            "questions": [
                {
                    "order_index": 1,
                    "qtype": "选择",
                    "stem": "题1",
                    "options": [],
                    "blocks": [],
                }
            ],
        }
    ],
}


def test_confirm_blocked_on_parent_anthology_done():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            parent = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                anthology_split_status="done",
            )
            s.add(parent)
            s.commit()
            pid = parent.id

        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 400
        assert "分套" in r.json()["detail"] or "合订" in r.json()["detail"]


def test_confirm_ok_on_child_after_split():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            child = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                anthology_split_status="none",
                display_name="2022广州中考",
            )
            s.add(child)
            s.commit()
            pid = child.id

        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 200
        assert r.json()["structured_confirm_status"] == "confirmed"
```

- [ ] **Step 2: Run test to verify failure or pass**

Run:

```powershell
cd backend
Remove-Item -Recurse -Force .\.pytest_tmp -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest tests/test_us8_anthology_first_set.py::test_confirm_blocked_on_parent_anthology_done -v
```

Expected: 若 US-7 已挡父本 → PASS，跳过 Step 3；若 FAIL 404/200 → Step 3。

- [ ] **Step 3: Implement gate in confirm API（仅当 Step 2 失败时）**

在 `post_confirm_structured` 中，`parsed_json` 校验通过后、写 `confirmed` 前增加：

```python
from app.services.anthology_ranges import confirm_blocked_message

st_anth = (getattr(p, "anthology_split_status", None) or "none").strip() or "none"
block = confirm_blocked_message(st_anth)
if block:
    raise HTTPException(400, block)
```

`confirm_blocked_message` 应对 `done` / `needed` 返回中文说明；`none` / `single_ok` 返回 `None`（与 US-7 spec 一致）。

- [ ] **Step 4: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_us8_anthology_first_set.py::test_confirm_blocked_on_parent_anthology_done tests/test_us8_anthology_first_set.py::test_confirm_ok_on_child_after_split -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/tests/test_us8_anthology_first_set.py
git commit -m "feat(us8): block structured confirm on anthology parent done"
```

---

### Task 2: 考点说明仅对子套生成（工具层门禁）

**Files:**
- Modify: `backend/app/agent/tools.py`（`run_knowledge_analysis`）
- Modify: `backend/tests/test_us8_anthology_first_set.py`

- [ ] **Step 1: Write the failing test**

在 `test_us8_anthology_first_set.py` 末尾追加：

```python
from unittest.mock import patch

from app.agent.tools import run_knowledge_analysis


def test_knowledge_analysis_refuses_parent_anthology_done():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            parent = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                structured_confirm_status="confirmed",
                alignment_json={
                    "grade_min": "初三",
                    "grade_max": "初三",
                    "subject": "数学",
                    "type_counts": {"选择": 1},
                },
                anthology_split_status="done",
            )
            s.add(parent)
            s.commit()
            pid = parent.id

        msg = run_knowledge_analysis.invoke({"paper_id": pid})
        assert "分套" in msg or "合订" in msg or "套卷" in msg


@patch("app.agent.tools.analyze_knowledge")
@patch("app.agent.tools.fill_missing_knowledge")
@patch("app.agent.tools.render_knowledge_pdf")
@patch("app.agent.tools.store_knowledge_pdf", return_value="ok")
def test_knowledge_pdf_artifact_on_child_paper(
    _store,
    _render,
    _fill,
    _analyze,
    tmp_path: Path,
):
    from app.db.models import Artifact
    from app.models.schemas import KnowledgeAnalysisResult, KnowledgePointItem

    _analyze.return_value = KnowledgeAnalysisResult(
        theme_title="主题",
        knowledge_points=[KnowledgePointItem(key="k1", name="考点A", summary="s")],
        mappings=[],
    )
    _fill.side_effect = lambda sp, ka, ask: ka

    pdf_path = tmp_path / "kp.pdf"
    _render.side_effect = lambda payload, path: path.write_bytes(b"%PDF-1.4\n")

    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            child = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                structured_confirm_status="confirmed",
                alignment_json={
                    "grade_min": "初三",
                    "grade_max": "初三",
                    "subject": "数学",
                    "type_counts": {"选择": 1},
                },
                anthology_split_status="none",
            )
            s.add(child)
            s.commit()
            child_id = child.id

        with patch(
            "app.agent.tools.export_dir_for_conversation", return_value=tmp_path
        ), patch(
            "app.agent.tools.knowledge_pdf_blocks",
            return_value={"title": "t", "points": []},
        ), patch.object(
            type(_render),
            "__call__",
            side_effect=lambda payload, path: path.write_bytes(b"%PDF-1.4\n"),
        ):
            # 简化：直接 patch render 路径在 run 内使用的 Path
            with patch(
                "app.agent.tools.render_knowledge_pdf",
                side_effect=lambda payload, path: path.write_bytes(b"%PDF-1.4\n"),
            ):
                run_knowledge_analysis.invoke({"paper_id": child_id})

        with sync_session() as s:
            arts = list(
                s.query(Artifact).filter(Artifact.paper_id == child_id).all()
            )
            assert any(a.kind == "knowledge_pdf" for a in arts)
            assert all(a.paper_id == child_id for a in arts)
```

若 mock 链过长导致脆弱，可缩短为：子套 invoke 不返回错误前缀，且 DB 中 `Artifact.paper_id == child_id`（参考 `tests/test_knowledge_pdf.py` 里对 DB 的写法）。

- [ ] **Step 2: Run failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_us8_anthology_first_set.py::test_knowledge_analysis_refuses_parent_anthology_done -v
```

Expected: FAIL（父本未拒绝）或 PASS（US-7 已拦）

- [ ] **Step 3: Add guard at start of `run_knowledge_analysis` body**

在 `st != "confirmed"` 检查之后：

```python
st_anth = (getattr(p, "anthology_split_status", None) or "none").strip() or "none"
if st_anth in ("done", "needed"):
    return "这是已切开或待分套的合订父本，请先在材料列表中选择某一「套卷」材料，再生成该套的考点说明。"
```

- [ ] **Step 4: Run Task 2 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_us8_anthology_first_set.py -v --tb=short
```

Expected: 本文件全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools.py backend/tests/test_us8_anthology_first_set.py
git commit -m "feat(us8): knowledge analysis only on child anthology paper"
```

---

### Task 3: AC-1 软提示（已有能力，补文档化测试）

**Files:**
- Test: `backend/tests/test_us8_anthology_first_set.py`

- [ ] **Step 1: Write test for anomalies on duplicate order_index**

```python
def test_structured_anomalies_lists_duplicate_order_index():
    from app.services.structured_inspect import list_anomalies

    parsed = {
        "title": "t",
        "sections": [
            {
                "title": "一",
                "questions": [
                    {
                        "order_index": 1,
                        "qtype": "选择",
                        "stem": "a",
                        "options": [],
                        "blocks": [],
                    },
                    {
                        "order_index": 1,
                        "qtype": "选择",
                        "stem": "b",
                        "options": [],
                        "blocks": [],
                    },
                ],
            }
        ],
    }
    msgs = list_anomalies(parsed)
    assert any("order_index" in m or "题号" in m for m in msgs)
```

- [ ] **Step 2: Run test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_us8_anthology_first_set.py::test_structured_anomalies_lists_duplicate_order_index -v
```

Expected: PASS（无需改产品代码；confirm 仍允许带 anomalies，见 `post_confirm_structured`）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_us8_anthology_first_set.py
git commit -m "test(us8): document soft AC-1 duplicate order_index hints"
```

---

### Task 4: 前端引导（父本禁确认 + 选套提示）

**Files:**
- Modify: `frontend/src/components/StructuredResultPanel.tsx`
- Modify: `frontend/src/components/MaterialSelector.tsx`
- Modify: `backend/app/api/chat.py`（若 `GET .../structured` 尚未返回 `anthology_split_status`，与 US-7 对齐补字段）

- [ ] **Step 1: Extend structured payload type**

在 `StructuredResultPanel.tsx` 的 `StructuredPayload` 增加：

```typescript
anthology_split_status?: string;
```

- [ ] **Step 2: Disable confirm for parent**

在确认按钮 `disabled` 条件增加：

```typescript
const anth = data?.anthology_split_status ?? "none";
const anthologyBlocksConfirm = anth === "done" || anth === "needed";
```

```typescript
disabled={
  confirming ||
  data?.structured_confirm_status === "confirmed" ||
  anthologyBlocksConfirm
}
```

在按钮上方当 `anthologyBlocksConfirm` 时展示：

```text
此为合订父本，不能在这里确认。请在左侧材料列表选择切开后的某一「套卷」，再拆题并确认。
```

当 `anth === "none"` 且子套有 `display_name` 时可选一行小字：

```text
首套验收：确认本套结构化后，继续生成彩色考点说明 PDF。
```

- [ ] **Step 3: MaterialSelector 标注父本**

在材料列表项中，若 `p.anthology_split_status === "done"`，在名称旁显示徽章「合订·已切开」；`needed` 显示「待分套」。

类型：给 paper 列表项增加可选 `anthology_split_status?: string`（与 `GET /api/conversations/{id}/papers` 对齐）。

- [ ] **Step 4: Manual smoke**

Run 前端 dev + 后端；上传合订 → 分套 → 点父本见禁用确认；选子套可确认。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/StructuredResultPanel.tsx frontend/src/components/MaterialSelector.tsx
git commit -m "feat(us8): UI hints for anthology child-first path"
```

---

### Task 5: 产品验收记录模板

**Files:**
- Create: `docs/US-8-产品验收记录.md`

- [ ] **Step 1: 从 spec 附录复制表格**

内容与 `docs/superpowers/specs/2026-11-17-us8-anthology-first-set-design.md` 附录一致，加一句说明：AC-3 仅用本表秒表，系统无计时字段。

- [ ] **Step 2: Commit**

```bash
git add docs/US-8-产品验收记录.md
git commit -m "docs(us8): add manual acceptance record for 20-minute gate"
```

---

### Task 6: 回归与交回

- [ ] **Step 1: 全量后端测试**

```powershell
cd backend
Remove-Item -Recurse -Force .\.pytest_tmp, .\.pytest_session_db -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest tests -q --tb=no
```

Expected: 0 failed（允许 skip 与 warning）

- [ ] **Step 2: 前端 build**

```powershell
cd frontend
npm run build
```

Expected: exit 0

- [ ] **Step 3: 对照 US-8 AC 自检表**

在 PR 描述列出：

| AC | 自动化 | 手工 |
|----|--------|------|
| AC-1 | `test_structured_anomalies_*` + 子套 confirm | 套内题号人眼 |
| AC-2 | `test_knowledge_pdf_artifact_on_child_paper` | 打开 PDF |
| AC-3 | — | `docs/US-8-产品验收记录.md` 秒表 |
| AC-4 | 沿用 `test_layout_timeout` 等 | 可选抽测合订路径 |

- [ ] **Step 4: PR**

标题：`feat: US-8 anthology first-set knowledge PDF on child paper`

- [ ] **Step 5: 停**

交回产品经理对照 `docs/2026-10-23-合订本多卷-stories.md` US-8 Given/When/Then；任务单 US-8 行登记。下一模块：**US-9**（brainstorming）。

---

## Spec coverage self-review

| Spec / AC | Task |
|-----------|------|
| 子套 confirm + 说明 PDF | T1, T2, T4 |
| 父本不得达标 | T1, T2, T4 |
| AC-1 软提示 | T3 |
| AC-3 秒表仅产品 | T5 |
| AC-4 超时不改 | T6 回归 US-6 测试 |
| 无应用内计时 | 无 Task |
| US-7 前置 | T0 |
| 不自动首套 | 文件 map 排除 |

无 TBD；`anthology_split_status` 与 US-7 命名一致。
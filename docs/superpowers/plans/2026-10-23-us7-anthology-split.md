# US-7 合订本先分套 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合订 PDF 在确认结构化前进入可改页码分套（启发式预填 + 现有按页拆分）；`needed`/`done` 硬挡确认；提供「按单套继续」逃生；重复题号自动进入同一路径。

**Architecture:** 纯函数启发式出 ranges/labels；`exam_papers.anthology_split_status` 持久化门禁；扩展 `split-by-pages` 写 labels 与父 `done`；Chat 复用拆分 UI 并加合订/单套按钮；`StructuredResultPanel` 禁用确认。不新增 MCP，不自动拆第一套。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、PyMuPDF、pytest、React 18、TypeScript。

**Spec:** `docs/superpowers/specs/2026-10-23-us7-anthology-split-design.md`

---

## File map

- Create: `backend/app/services/anthology_ranges.py` — 启发式、空提示文案、确认门禁文案/判定。
- Create: `backend/tests/test_anthology_ranges.py`
- Create: `backend/tests/test_anthology_split_api.py` — suggest / mark-needed / single-ok / confirm 门禁 / split labels。
- Modify: `backend/app/db/models.py` — `anthology_split_status` 列。
- Modify: `backend/app/db/migrate.py` — `apply_sqlite_exam_paper_anthology_split_status`。
- Modify: `backend/app/db/init_db.py` — 调用迁移。
- Modify: `backend/app/api/exam_papers.py` — suggest、mark-needed；split 接受 `labels`、父→`done`。
- Modify: `backend/app/api/chat.py` — confirm 门禁；single-ok；list/get structured 返回 `anthology_split_status`；重复题号时标 `needed`（get structured 副作用或专用逻辑）。
- Modify: `frontend/src/components/Chat.tsx` — 合订按钮、预填、labels、覆盖提示、按单套继续。
- Modify: `frontend/src/components/StructuredResultPanel.tsx` — 确认禁用。
- Do not modify practice/knowledge PDF 生成、超时文案、MCP。
- Do not implement US-8 自动选套拆题或 US-9 完整护栏验收（逃生按钮在本计划内）。

从 `main` 拉分支 `feat/us7-anthology-split`。Windows 上 pytest 将 `TEMP`/`TMP` 指到仓库 `tmp`（若现有约定如此则沿用）。

---

### Task 1: 启发式 ranges（纯函数）

**Files:**
- Create: `backend/app/services/anthology_ranges.py`
- Create: `backend/tests/test_anthology_ranges.py`

- [ ] **Step 1: Write the failing test**

```python
from app.services.anthology_ranges import (
    EMPTY_SUGGEST_MESSAGE,
    CONFIRM_BLOCKED_NEEDED,
    CONFIRM_BLOCKED_DONE,
    suggest_ranges_from_page_texts,
    confirm_blocked_message,
)


def test_suggest_splits_on_year_markers():
    pages = [
        "2021年广州市中考数学",
        "第1题 …",
        "2022年广州市中考数学",
        "第1题 …",
        "2023年广州市中考数学",
        "尾页",
    ]
    ranges, labels, msg = suggest_ranges_from_page_texts(pages)
    assert ranges == [[1, 2], [3, 4], [5, 6]]
    assert labels[0].startswith("2021")
    assert labels[1].startswith("2022")
    assert labels[2].startswith("2023")
    assert msg == ""


def test_suggest_empty_when_fewer_than_two_markers():
    ranges, labels, msg = suggest_ranges_from_page_texts(["普通单套卷 第1题", "第2题"])
    assert ranges == []
    assert labels == []
    assert msg == EMPTY_SUGGEST_MESSAGE


def test_suggest_never_equal_splits_total_pages():
    # 10 页无年份：必须空，禁止 [[1,2],[3,4],…] 均分
    pages = [f"内容{i}" for i in range(10)]
    ranges, labels, msg = suggest_ranges_from_page_texts(pages)
    assert ranges == []
    assert labels == []
    assert msg == EMPTY_SUGGEST_MESSAGE


def test_confirm_blocked_message():
    assert confirm_blocked_message("needed") == CONFIRM_BLOCKED_NEEDED
    assert confirm_blocked_message("done") == CONFIRM_BLOCKED_DONE
    assert confirm_blocked_message("none") is None
    assert confirm_blocked_message("single_ok") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; python -m pytest tests/test_anthology_ranges.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.anthology_ranges'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/anthology_ranges.py
from __future__ import annotations

import re

EMPTY_SUGGEST_MESSAGE = "请按套填写页码"
CONFIRM_BLOCKED_NEEDED = "请先确认合订本分套（或选择按单套继续），再确认结构化。"
CONFIRM_BLOCKED_DONE = "该材料为已切开的合订本原件，请对切开后的各套确认结构化。"

_YEAR_LINE = re.compile(
    r"(?P<year>20[0-9]{2})\s*年?.{0,24}(中考|期末|一模|二模|三模|月考|调研)",
    re.MULTILINE,
)


def _marker_year(text: str) -> str | None:
    m = _YEAR_LINE.search(text or "")
    if m:
        return m.group("year")
    # 弱匹配：页首附近单独年份且含「考」
    m2 = re.search(r"(20[0-9]{2})", text or "")
    if m2 and ("考" in (text or "")[:80] or "中考" in (text or "")):
        return m2.group(1)
    return None


def suggest_ranges_from_page_texts(
    page_texts: list[str],
) -> tuple[list[list[int]], list[str], str]:
    """page_texts 下标 0 = 第 1 页。少于两个年份标记则返回空，禁止均分。"""
    markers: list[tuple[int, str]] = []  # 1-based page, year
    for i, t in enumerate(page_texts):
        y = _marker_year(t or "")
        if y:
            # 同一年连续页只保留首次
            if markers and markers[-1][1] == y and i + 1 == markers[-1][0] + 1:
                continue
            if markers and markers[-1][1] == y:
                continue
            markers.append((i + 1, y))
    # 去重：只保留年份变化的边界页
    boundary: list[tuple[int, str]] = []
    for page, year in markers:
        if not boundary or boundary[-1][1] != year:
            boundary.append((page, year))
    if len(boundary) < 2:
        return [], [], EMPTY_SUGGEST_MESSAGE
    n = len(page_texts)
    ranges: list[list[int]] = []
    labels: list[str] = []
    for idx, (start, year) in enumerate(boundary):
        end = (boundary[idx + 1][0] - 1) if idx + 1 < len(boundary) else n
        if end < start:
            end = start
        ranges.append([start, end])
        labels.append(f"{year}年试卷")
    return ranges, labels, ""


def confirm_blocked_message(status: str | None) -> str | None:
    s = (status or "none").strip() or "none"
    if s == "needed":
        return CONFIRM_BLOCKED_NEEDED
    if s == "done":
        return CONFIRM_BLOCKED_DONE
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend; python -m pytest tests/test_anthology_ranges.py -v`

Expected: PASS（若弱匹配导致边界页与样例不符，微调 `_marker_year` 或样例字符串，保持「≥2 标记才出 ranges、无标记不均分」不变）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/anthology_ranges.py backend/tests/test_anthology_ranges.py
git commit -m "feat(us7): anthology page-range heuristic and confirm gate copy"
```

---

### Task 2: DB 列 `anthology_split_status`

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/migrate.py`
- Modify: `backend/app/db/init_db.py`

- [ ] **Step 1: Add model column**

在 `ExamPaper` 中 `last_practice_config_json` 附近增加：

```python
# none | needed | done | single_ok — 合订分套门禁（US-7）
anthology_split_status: Mapped[str] = mapped_column(String(32), default="none")
```

- [ ] **Step 2: Add migrate helper**

在 `migrate.py` 末尾增加：

```python
def apply_sqlite_exam_paper_anthology_split_status(connection: Connection) -> None:
    insp = inspect(connection)
    if not insp.has_table("exam_papers"):
        return
    cols = {c["name"] for c in insp.get_columns("exam_papers")}
    if "anthology_split_status" not in cols:
        connection.execute(
            text(
                "ALTER TABLE exam_papers ADD COLUMN anthology_split_status "
                "VARCHAR(32) DEFAULT 'none'"
            )
        )
```

在 `init_db.py` 导入并 `await conn.run_sync(apply_sqlite_exam_paper_anthology_split_status)`。

- [ ] **Step 3: Smoke import**

Run: `cd backend; python -c "from app.db.models import ExamPaper; assert hasattr(ExamPaper, 'anthology_split_status')"`

Expected: exit 0

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrate.py backend/app/db/init_db.py
git commit -m "feat(us7): add anthology_split_status column"
```

---

### Task 3: Confirm 门禁 + single-ok + list/structured 暴露字段

**Files:**
- Modify: `backend/app/api/chat.py`
- Create: `backend/tests/test_anthology_split_api.py`（本 Task 先写 confirm / single-ok 用例）

- [ ] **Step 1: Write failing API tests**

```python
# backend/tests/test_anthology_split_api.py
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.db.models import ExamPaper
from app.db.session import sync_session
from app.main import app


def _pdf(tmp: Path, pages: list[str]) -> Path:
    p = tmp / "a.pdf"
    doc = fitz.open()
    try:
        for t in pages:
            pg = doc.new_page()
            pg.insert_text((72, 72), t)
        doc.save(p.as_posix())
    finally:
        doc.close()
    return p


def test_confirm_blocked_when_needed(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(tmp_path, ["2021年中考", "x", "2022年中考", "y"])
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                raw_path=pdf.as_posix(),
                parsed_json={
                    "title": "合订",
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
                structured_confirm_status="pending",
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 400
        assert "分套" in r.json()["detail"]


def test_single_ok_allows_confirm(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json={
                    "title": "卷",
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
                structured_confirm_status="pending",
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(
            f"/api/conversations/{cid}/papers/{pid}/anthology-split/single-ok"
        )
        assert r.status_code == 200
        assert r.json()["anthology_split_status"] == "single_ok"
        r2 = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r2.status_code == 200
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend; python -m pytest tests/test_anthology_split_api.py::test_confirm_blocked_when_needed -v`

Expected: FAIL（仍 200 或路由不存在）

- [ ] **Step 3: Implement gate + single-ok + expose field**

在 `post_confirm_structured` 校验 `parsed_json` 之后：

```python
from app.services.anthology_ranges import confirm_blocked_message

block = confirm_blocked_message(getattr(p, "anthology_split_status", None))
if block:
    raise HTTPException(400, block)
```

新增：

```python
@router.post("/conversations/{conversation_id}/papers/{paper_id}/anthology-split/single-ok")
async def post_anthology_single_ok(...):
    # 404 同其他 paper 路由
    st = (p.anthology_split_status or "none").strip() or "none"
    if st != "needed":
        raise HTTPException(400, "仅待分套材料可选择按单套继续。")
    p.anthology_split_status = "single_ok"
    await session.commit()
    return {"ok": True, "anthology_split_status": p.anthology_split_status}
```

`list_conversation_papers` 与 `get_paper_structured` 的 JSON 增加 `"anthology_split_status": getattr(p, "anthology_split_status", None) or "none"`。

- [ ] **Step 4: Run tests**

Run: `cd backend; python -m pytest tests/test_anthology_split_api.py::test_confirm_blocked_when_needed tests/test_anthology_split_api.py::test_single_ok_allows_confirm -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/chat.py backend/tests/test_anthology_split_api.py
git commit -m "feat(us7): block structured confirm until anthology split or single-ok"
```

---

### Task 4: suggest-page-ranges + mark needed

**Files:**
- Modify: `backend/app/api/exam_papers.py`
- Modify: `backend/tests/test_anthology_split_api.py`

- [ ] **Step 1: Append failing tests**

```python
def test_suggest_page_ranges_and_mark_needed(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(
            tmp_path,
            [
                "2021年广州市中考数学",
                "题",
                "2022年广州市中考数学",
                "题",
            ],
        )
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                raw_path=pdf.as_posix(),
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(
            f"/api/exam-papers/{pid}/anthology-split/mark-needed",
            json={"conversation_id": cid},
        )
        assert r.status_code == 200
        assert r.json()["anthology_split_status"] == "needed"
        sgg = client.post(
            f"/api/exam-papers/{pid}/suggest-page-ranges",
            json={"conversation_id": cid},
        )
        assert sgg.status_code == 200
        body = sgg.json()
        assert len(body["ranges"]) >= 2
        assert len(body["labels"]) == len(body["ranges"])
```

- [ ] **Step 2: Run to fail**

Run: `cd backend; python -m pytest tests/test_anthology_split_api.py::test_suggest_page_ranges_and_mark_needed -v`

Expected: 404

- [ ] **Step 3: Implement endpoints in `exam_papers.py`**

```python
class ConversationIdBody(BaseModel):
    conversation_id: str = Field(..., min_length=1)


@router.post("/exam-papers/{paper_id}/anthology-split/mark-needed")
async def mark_anthology_needed(paper_id: str, body: ConversationIdBody, session=...):
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != body.conversation_id:
        raise HTTPException(404, "试卷不存在或不属于该会话")
    if (p.anthology_split_status or "") == "done":
        raise HTTPException(400, "该合订本已切开，请对子材料操作。")
    p.anthology_split_status = "needed"
    await session.commit()
    return {"ok": True, "anthology_split_status": "needed"}


@router.post("/exam-papers/{paper_id}/suggest-page-ranges")
async def suggest_page_ranges(paper_id: str, body: ConversationIdBody, session=...):
    from app.services.anthology_ranges import suggest_ranges_from_page_texts
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != body.conversation_id:
        raise HTTPException(404, "试卷不存在或不属于该会话")
    if not p.raw_path:
        raise HTTPException(400, "该材料无本地 PDF 路径")
    path = Path(p.raw_path)
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise HTTPException(400, "仅支持已上传且存在的 PDF 文件")
    try:
        doc = fitz.open(path.as_posix())
        try:
            texts = [(doc.load_page(i).get_text("text") or "") for i in range(doc.page_count)]
        finally:
            doc.close()
    except Exception as e:
        raise HTTPException(400, f"无法读取 PDF：{e!s}") from e
    ranges, labels, message = suggest_ranges_from_page_texts(texts)
    return {"ranges": ranges, "labels": labels, "message": message, "page_count": len(texts)}
```

（`import fitz` 放文件顶或函数内均可，与项目一致。）

- [ ] **Step 4: Pass tests + commit**

```bash
git add backend/app/api/exam_papers.py backend/tests/test_anthology_split_api.py
git commit -m "feat(us7): suggest page ranges and mark anthology needed"
```

---

### Task 5: split-by-pages 支持 labels + 父 done + 覆盖提示数据

**Files:**
- Modify: `backend/app/api/exam_papers.py`
- Modify: `backend/tests/test_anthology_split_api.py`

- [ ] **Step 1: Failing test**

```python
def test_split_sets_parent_done_and_labels(tmp_path: Path):
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        pdf = _pdf(tmp_path, ["2021年中考 A", "a2", "2022年中考 B", "b2"])
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                raw_path=pdf.as_posix(),
                anthology_split_status="needed",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(
            f"/api/exam-papers/{pid}/split-by-pages",
            json={
                "conversation_id": cid,
                "ranges": [[1, 2], [3, 4]],
                "labels": ["2021年试卷", "2022年试卷"],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["new_papers"]) == 2
        assert body["new_papers"][0]["label"] == "2021年试卷"
        assert body.get("uncovered_pages_hint")  # 若全覆盖可为 "" 或省略
        with sync_session() as s:
            parent = s.get(ExamPaper, pid)
            assert parent.anthology_split_status == "done"
            child = s.get(ExamPaper, body["new_papers"][0]["id"])
            assert child.display_name == "2021年试卷"
            assert (child.anthology_split_status or "none") == "none"
```

- [ ] **Step 2: Implement**

扩展 `SplitByPagesBody`：

```python
class SplitByPagesBody(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    ranges: list[list[int]] = Field(..., min_length=1)
    labels: list[str] | None = None
```

在创建子材料循环中：

```python
label = None
if body.labels and idx < len(body.labels) and str(body.labels[idx]).strip():
    label = str(body.labels[idx]).strip()
display = label or f"片段{idx + 1}"
# ExamPaper(..., display_name=display, anthology_split_status="none")
# new_papers append label=display
```

循环结束后：

```python
p.anthology_split_status = "done"
# uncovered: pages 1..total not in any range
covered: set[int] = set()
for a, b in ...:
    covered.update(range(a, b + 1))
missing = [i for i in range(1, total + 1) if i not in covered]
hint = ""
if missing:
    hint = f"有页未纳入任何套（将排除）：{missing[0]}…"  # 或列出摘要
await session.commit()
return {..., "uncovered_pages_hint": hint}
```

若 `labels` 长度与 `ranges` 不一致：`raise HTTPException(400, "labels 须与 ranges 等长，或省略 labels")`（仅当 labels 非 null 时检查）。

- [ ] **Step 3: Pass + commit**

```bash
git add backend/app/api/exam_papers.py backend/tests/test_anthology_split_api.py
git commit -m "feat(us7): split-by-pages labels and mark parent anthology done"
```

---

### Task 6: 重复题号 → 自动 needed

**Files:**
- Modify: `backend/app/api/chat.py`（`get_paper_structured`）
- Modify: `backend/tests/test_anthology_split_api.py`

- [ ] **Step 1: Failing test**

```python
def test_get_structured_marks_needed_on_duplicate_order_index():
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                anthology_split_status="none",
                parsed_json={
                    "title": "合订",
                    "sections": [
                        {
                            "title": "一",
                            "questions": [
                                {"order_index": 1, "qtype": "填空", "stem": "a", "options": [], "blocks": []},
                                {"order_index": 1, "qtype": "填空", "stem": "b", "options": [], "blocks": []},
                            ],
                        }
                    ],
                },
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.get(f"/api/conversations/{cid}/papers/{pid}/structured")
        assert r.status_code == 200
        assert any("重复" in a for a in r.json()["anomalies"])
        assert r.json()["anthology_split_status"] == "needed"
        with sync_session() as s:
            assert s.get(ExamPaper, pid).anthology_split_status == "needed"
```

- [ ] **Step 2: Implement in `get_paper_structured`**

```python
anoms = list_anomalies(p.parsed_json)
st_anth = (getattr(p, "anthology_split_status", None) or "none").strip() or "none"
if (
    st_anth == "none"
    and any("order_index 重复" in a for a in anoms)
):
    p.anthology_split_status = "needed"
    await session.commit()
    st_anth = "needed"
# return 中带 anthology_split_status=st_anth
```

不覆盖已是 `done` / `single_ok` / `needed` 的状态。

- [ ] **Step 3: Pass + commit**

```bash
git add backend/app/api/chat.py backend/tests/test_anthology_split_api.py
git commit -m "feat(us7): auto mark anthology needed on duplicate order_index"
```

---

### Task 7: 前端合订入口、预填、确认禁用

**Files:**
- Modify: `frontend/src/components/Chat.tsx`
- Modify: `frontend/src/components/StructuredResultPanel.tsx`

- [ ] **Step 1: StructuredResultPanel**

扩展 `StructuredPayload` 增加 `anthology_split_status?: string`。

确认按钮：

```tsx
const anth = data?.anthology_split_status ?? "none";
const confirmBlocked = anth === "needed" || anth === "done";
// disabled={confirming || data?.structured_confirm_status === "confirmed" || confirmBlocked}
// 旁注：confirmBlocked 时显示 data 无法确认的原因短句（与后端文案一致即可）
```

- [ ] **Step 2: Chat.tsx 状态与合订操作**

- `papers` 类型增加 `anthology_split_status?: string`。
- state：`splitLabels: string[]`（与 ranges 平行；切开时若长度匹配则传 `labels`）。
- 在按页拆分卡片上方或旁增加按钮：
  - 「这是合订本」：对 `splitTarget`  
    `POST /api/exam-papers/{id}/anthology-split/mark-needed` →  
    `POST …/suggest-page-ranges` → 将 ranges 格式化为 `1-2, 3-4` 写入 `splitRanges`，保存 `splitLabels`；`loadPapers()`。
  - 「按单套继续」：仅当目标 `anthology_split_status==="needed"` 时显示；  
    `POST /api/conversations/{cid}/papers/{id}/anthology-split/single-ok` → `loadPapers()` + `setV2Tick`。
- 切开请求 body 增加 `labels: splitLabels`（若非空且与 parse 出的 ranges 等长）。
- 若响应 `uncovered_pages_hint`：黄字展示。
- `useEffect`：当 `targetPaperId` 对应 paper 的 `anthology_split_status==="needed"` 且 `splitRanges` 为空时，自动调用 suggest 预填一次（避免重复题号路径还要再点）；用 ref 防死循环。

- [ ] **Step 3: 手动核对清单（实现者）**

- 点合订 → 预填或空提示 → 改 ranges → 切开 → 列表出现带名子材料，父不可确认。  
- `needed` 时确认按钮灰。  
- 按单套继续后可确认。  

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Chat.tsx frontend/src/components/StructuredResultPanel.tsx
git commit -m "feat(us7): anthology split UI on page-split and confirm gate"
```

---

### Task 8: 回归与交回准备

- [ ] **Step 1: 跑相关测试**

Run:

```
cd backend
python -m pytest tests/test_anthology_ranges.py tests/test_anthology_split_api.py tests/test_pdf_pages.py -v
```

Expected: all PASS

- [ ] **Step 2: 对照 US-7 AC 自检（文档备注即可）**

在 PR 描述中列出：AC-1～AC-4 各一句「已测/待老师验收」。

- [ ] **Step 3: 开 PR（不要在本计划里合并）**

标题建议：`feat: US-7 anthology split before structured confirm`

- [ ] **Step 4: 停**

实现交回后由**产品经理**对照 `docs/2026-10-23-合订本多卷-stories.md` US-7 Given/When/Then 验收；项目经理登记任务单。不在本行实现 US-8。

---

## Spec coverage self-review

| Spec 项 | Task |
|--------|------|
| 显式合订入口 + 预填 | T4, T7 |
| 启发式、宁空勿均分 | T1, T4 |
| 复用 split-by-pages + labels | T5, T7 |
| 排除=不填 ranges + 未覆盖提示 | T5, T7 |
| needed/done 硬挡确认 | T1, T3, T7 |
| single_ok 逃生 | T3, T7 |
| 父 done、子可确认、不自动拆第一套 | T5（不自动拆） |
| 重复题号 → needed | T6, T7 |
| 不改 MCP / US-8 考点 | 文件 map 排除 |

无 TBD 占位；类型名 `anthology_split_status` / `suggest-page-ranges` / `mark-needed` / `single-ok` 全文一致。

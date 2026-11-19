# US-9 单套护栏 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 日常单套 PDF 不被合订流程无故拦住；`needed` 时在结构化结果区提供「按单套继续」，复用 `single-ok` 回到 US-1 确认路径；不削弱 US-7 重复题号自动待分套与按页拆分。

**Architecture:** 后端不增接口——现有 `anthology-split/single-ok` 与 `GET structured` 写 `needed` 保持不变；补 API 回归（`none` / 重复→`needed`→`single_ok`→confirm）；前端仅改 `StructuredResultPanel`：区分 `needed` 与 `done` 文案，加逃生按钮并刷新状态。

**Tech Stack:** Python 3.12、FastAPI、pytest、React 18、TypeScript。

**Spec:** `docs/superpowers/specs/2026-11-17-us9-anthology-single-paper-design.md`（2026-11-17 **approved**）

**Implementation status（2026-11-19）**

| 项 | 状态 |
|----|------|
| Task 0–4（代码 + 自动化 + 任务单） | **Done**（待 commit） |
| `test_anthology_split_api` | +2 用例，`7 passed` |
| `npm run build` | **Pass** |
| 产品验收 | **Deferred**（五模块统一） |

---

## Global Constraints

- 重复题号时 `GET …/structured` 仍自动写 `anthology_split_status=needed`（不修改 `list_anomalies` / `chat.py` 副作用条件）。
- `single-ok` 仅 `needed`→`single_ok`；父本 `done` 仍禁止确认、不提供单套继续。
- 不实现材料选择器引导条（spec 做法 ②）；不抽共享门禁组件（做法 ③ 非必须）。
- 不新增 MCP、应用内 20 分钟计时；Chat 合订按钮与 `split-by-pages` 行为不改。
- 师生可见文案中文，不带密钥与卷子正文。

---

## File map

- Modify: `frontend/src/components/StructuredResultPanel.tsx` — `needed` 门禁文案、`按单套继续` 按钮、`done` 与 `needed` 分开展示。
- Modify: `backend/tests/test_anthology_split_api.py` — AC-1/AC-2 API 回归（`none` 可确认；重复→needed→single_ok→confirm）。
- Test (manual): spec 附录 US-9 产品验收记录（五模块统一验收时填；本计划不新建独立 md 除非操作者要求）。
- Do not modify: `backend/app/api/chat.py` 自动 `needed` 逻辑、`exam_papers.py` 分套 API、Chat 拆分区按钮逻辑（仅回归）。

从 `main` 拉分支 `feat/us9-anthology-single-paper`。Windows：`backend\.venv` + `pytest`；前端 `frontend` 下 `npm run build`。

---

### Task 0: US-7 前置检查

**Files:** 无（只读）

- [ ] **Step 1: 确认 single-ok 与门禁已存在**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_anthology_split_api.py::test_single_ok_allows_confirm tests/test_anthology_split_api.py::test_confirm_blocked_when_needed -q --tb=short
```

Expected: 2 passed.

- [ ] **Step 2: 确认前端 Chat 仍有「按单套继续」**

Run:

```powershell
rg "按单套继续" frontend/src/components/Chat.tsx
```

Expected: 至少一处匹配。

- [ ] **Step 3: 记录**

实现 PR 描述写：`US-7 prerequisite: met（single-ok API + anthology_split_status 列）`。

---

### Task 1: API 回归（单套默认 + 误判逃生链）

**Files:**
- Modify: `backend/tests/test_anthology_split_api.py`

**Interfaces:**
- Consumes: `POST /api/conversations/{cid}/papers/{pid}/structured/confirm`、`POST …/anthology-split/single-ok`、`GET …/structured`
- Produces: `test_confirm_ok_when_anthology_none`、`test_duplicate_then_single_ok_then_confirm`

- [ ] **Step 1: Write tests**

在 `backend/tests/test_anthology_split_api.py` 末尾追加：

```python
def test_confirm_ok_when_anthology_none():
    """US-9 AC-1: 单套默认 none 可确认。"""
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                parsed_json=_PARSED,
                structured_confirm_status="pending",
                anthology_split_status="none",
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        r = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert r.status_code == 200


def test_duplicate_then_single_ok_then_confirm():
    """US-9 AC-2: 重复→needed→single_ok→confirm。"""
    with TestClient(app) as client:
        cid = client.post("/api/conversations").json()["conversation_id"]
        dup_parsed = {
            "title": "单套误判",
            "sections": [
                {
                    "title": "一",
                    "questions": [
                        {
                            "order_index": 1,
                            "qtype": "填空",
                            "stem": "a",
                            "options": [],
                            "blocks": [],
                        },
                        {
                            "order_index": 1,
                            "qtype": "填空",
                            "stem": "b",
                            "options": [],
                            "blocks": [],
                        },
                    ],
                }
            ],
        }
        with sync_session() as s:
            paper = ExamPaper(
                conversation_id=cid,
                source_type="pdf",
                anthology_split_status="none",
                parsed_json=dup_parsed,
            )
            s.add(paper)
            s.commit()
            pid = paper.id
        g = client.get(f"/api/conversations/{cid}/papers/{pid}/structured")
        assert g.status_code == 200
        assert g.json()["anthology_split_status"] == "needed"
        blocked = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert blocked.status_code == 400
        ok = client.post(f"/api/conversations/{cid}/papers/{pid}/anthology-split/single-ok")
        assert ok.status_code == 200
        assert ok.json()["anthology_split_status"] == "single_ok"
        confirmed = client.post(f"/api/conversations/{cid}/papers/{pid}/structured/confirm")
        assert confirmed.status_code == 200
```

- [ ] **Step 2: Run tests**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_anthology_split_api.py::test_confirm_ok_when_anthology_none tests/test_anthology_split_api.py::test_duplicate_then_single_ok_then_confirm -v
```

Expected: PASS（不依赖前端改动）。

- [ ] **Step 3: Commit**

```powershell
git add backend/tests/test_anthology_split_api.py
git commit -m "test(us9): single-paper confirm path and duplicate escape chain"
```

---

### Task 2: 结构化结果区「按单套继续」（做法 ①）

**Files:**
- Modify: `frontend/src/components/StructuredResultPanel.tsx`

**Interfaces:**
- Consumes: `POST /api/conversations/${conversationId}/papers/${paperId}/anthology-split/single-ok`（已有）；`load()` 刷新 structured。
- Produces: `singleOkBusy` / `singleOkNote` 状态；`needed` 专用 UI 块。

- [ ] **Step 1: 拆分 `done` 与 `needed` 提示（修现状误文案）**

现状：`needed` 与 `done` 共用「此为合订父本…」——与 spec 不符。

将约 209–215 行替换为：

```tsx
      {data?.anthology_split_status === "done" && (
        <p className="mb-2 rounded-xl border border-sky-200 bg-sky-50/90 p-2 text-sm text-sky-950">
          此为合订父本，不能在这里确认。请在材料列表选择切开后的某一「套卷」，再拆题并确认。
          首套验收：确认本套结构化后，继续生成彩色考点说明 PDF。
        </p>
      )}

      {data?.anthology_split_status === "needed" && (
        <div className="mb-2 rounded-xl border border-amber-200 bg-amber-50/90 p-2 text-sm text-amber-950">
          <p className="mb-2">
            当前材料处于<strong>待分套</strong>：可先回到聊天区按页切开多卷；若实际只有一套卷，可点下方「按单套继续」，无需填写第二套页码。
          </p>
          <button
            type="button"
            disabled={singleOkBusy}
            onClick={() => void runSingleOk()}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50"
          >
            {singleOkBusy ? "处理中…" : "按单套继续"}
          </button>
          {singleOkNote ? <p className="mt-2 text-xs text-slate-700">{singleOkNote}</p> : null}
        </div>
      )}
```

- [ ] **Step 2: 增加 state 与 `runSingleOk`**

在组件 state 区增加：

```tsx
  const [singleOkBusy, setSingleOkBusy] = useState(false);
  const [singleOkNote, setSingleOkNote] = useState<string | null>(null);
```

在 `confirm` 回调附近增加：

```tsx
  const runSingleOk = useCallback(async () => {
    if (!paperId) return;
    setSingleOkBusy(true);
    setSingleOkNote(null);
    setSaveErr(null);
    try {
      const r = await fetch(
        `${API}/api/conversations/${conversationId}/papers/${paperId}/anthology-split/single-ok`,
        { method: "POST" },
      );
      if (!r.ok) {
        const t = await r.text();
        setSingleOkNote(t || "无法切换为单套模式");
        return;
      }
      setSingleOkNote("已按单套继续，可直接确认结构化。");
      await load();
      onAfterSave();
    } catch {
      setSingleOkNote("网络错误");
    } finally {
      setSingleOkBusy(false);
    }
  }, [conversationId, paperId, load, onAfterSave]);
```

- [ ] **Step 3: 确认按钮 disabled 规则不变**

保持：`needed` 禁用确认、`single_ok` 可确认；`done` 仍禁用。成功后 `load()` 应返回 `single_ok`，确认按钮自动可点。

- [ ] **Step 4: 构建**

```powershell
cd frontend
npm run build
```

Expected: 编译成功。

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/StructuredResultPanel.tsx
git commit -m "feat(us9): single-ok escape in structured result panel"
```

---

### Task 3: 全量回归与手工抽检清单

**Files:** 无

- [ ] **Step 1: 后端 anthology 相关测试**

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_anthology_split_api.py tests/test_anthology_ranges.py tests/test_us8_anthology_first_set.py -q --tb=no
```

Expected: 全部 PASS。

- [ ] **Step 2: 全量 pytest（可选，发版前）**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=no
```

Expected: 与基线相比仅 +2（Task 1 新测）。

- [ ] **Step 3: 手工（AC-2 主路径）**

1. 打开工作台，选目标材料，点「这是合订本」进入 `needed`（或用药重复 parsed 触发 GET structured 标 `needed`）。
2. 打开 **结构化结果** 区：见「待分套」文案与 **按单套继续**（非「合订父本」文案）。
3. 点 **按单套继续** → 成功句 → **确认结构化结果** 可点且成功。
4. 回归：真合订父本 `done` 仍只显示父本文案、无单套按钮、确认仍灰。

- [ ] **Step 4: Commit（若有文档/任务单更新）**

仅当更新了任务单 US-9 状态行时：

```powershell
git add docs/2026-10-23-合订本多卷-任务单.md
git commit -m "docs: mark US-9 implementation ready for product acceptance"
```

---

### Task 4: 交回项目经理 / 产品

**Files:** `docs/2026-10-23-合订本多卷-任务单.md`（可选更新 US-9 行状态）

- [ ] **Step 1: 登记交付物**

- 代码：`StructuredResultPanel` + 测试文件。
- 产品验收：spec 附录「US-9 产品验收记录」；与五模块统一验收，本轮不填秒表。

- [ ] **Step 2: 任务单行（建议）**

将「US-9 | 未派」改为「US-9 | 研发交回，待产品验收」。

---

## Plan self-review（相对 spec）

| Spec 要求 | 任务 |
|-----------|------|
| AC-1 单套 `none` 可确认 | Task 1 `test_confirm_ok_when_anthology_none` |
| AC-2 结构化区按单套继续 | Task 2 |
| 重复仍自动 `needed` | Global Constraints；不改 chat.py |
| `done` 父本边界 | Task 2 文案拆分 + 手工 Step 3 |
| 不破坏按页拆分 / Chat 按钮 | File map Do not modify |
| 20 分钟方案 A | 无任务（仅 spec 记录） |
| 后端默认无新接口 | 无 chat.py 修改任务 |

无 TBD / TODO 占位。

---

## Execution Handoff

Plan 已保存：`docs/superpowers/plans/2026-11-17-us9-anthology-single-paper.md`。

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每 Task 派子 Agent，Task 间人工扫一眼 diff  
2. **本会话 Inline** — 按 `executing-plans` 连续做 Task 0→4，每 Task 末汇报

你还没说「开始实现」前，本计划 **不自动写代码**。要开工请回复例如：**「按 plan 实现 US-9」** 并选 1 或 2。
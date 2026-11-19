---
artifact: design
story: US-9
version: "1.0"
created: 2026-11-17
approved: 2026-11-17
status: approved
---

# US-9 设计：单套卷不被强制分套

对应故事：`docs/2026-10-23-合订本多卷-stories.md` 的 US-9。  
对应 PRD：`docs/2026-10-23-合订本多卷-prd.md`（**FR-7** 单套护栏）。  
前置：`docs/superpowers/specs/2026-10-23-us7-anthology-split-design.md`（分套门禁、`single_ok` API、重复题号进待分套）。  
单套主路径：`docs/2026-10-21-拆卷出卷-stories.md`（US-1）。  
任务单：`docs/2026-10-23-合订本多卷-任务单.md` 的 US-9 行。

本设计经 brainstorming 对齐：**重复题号仍自动进待分套（与 US-7 一致）**；US-9 落地 **做法 ①**——在**结构化结果区**显性提供「按单套继续」，复用既有 `single-ok` 接口，不新增后端门禁模型。**20 分钟**延续 US-8 **方案 A**（仅产品验收秒表；本故事不涉及应用内计时）。

## 目标（白话）

老师日常上传**本来就是一套**的 PDF 时，应能直接走与 US-1 相同的拆题与确认，不被合订流程无故拦住。若因误点「这是合订本」或**题号重复**被标成「待分套」，老师应能在**被挡住确认的地方**一键「按单套继续」，回到单套结构化路径，**不必为了过关虚构第二套页码**。老师仍可主动使用按页拆分、点「这是合订本」走 US-7，本故事不削弱这些能力。

## 范围

### 做

- **AC-1**：未主动进合订、且无触发待分套条件的单套材料 → 行为与改 US-7 前单卷一致（可确认结构化）。
- **AC-2**：`anthology_split_status=needed` 时，在 **StructuredResultPanel（结构化结果区）** 展示门禁说明 + **「按单套继续」** 按钮；调用既有 `POST /api/conversations/{conversation_id}/papers/{paper_id}/anthology-split/single-ok`；成功后状态为 `single_ok`，确认按钮可用，提示与 Chat 拆分区一致语义（「已按单套继续，可直接确认结构化」）。
- 文档化 **何时自动标待分套**、与 **主动点合订本** 的边界；明确 **不破坏** Chat 内按页拆分与「这是合订本 / 需要分套」。
- 回归：`done` 父本仍不能确认；切开流程、`split-by-pages`、建议页码接口不变。
- 自动化：扩展现有 `test_anthology_split_api`（或等价）覆盖 `needed` → `single_ok` → `structured/confirm` 200；`none` 材料 confirm 仍 200。

### 不做

- 不因 US-9 而取消「重复题号 → 自动待分套」（brainstorming 已选方案 A）。
- 不把重复检测收窄为「仅跨大题 / 仅启发式≥2 套」——若误伤仍多，另开议题。
- **做法 ②**（材料选择器额外引导条）本行不实现。
- 共享门禁组件抽离（做法 ③）：非必须，允许结构化区与 Chat 各保留按钮（逻辑可抄同一 API）。
- 应用内 20 分钟计时、新 MCP、启发式算法改版。
- 合订本分套正确性复检（US-7）、首套考点说明（US-8）——仅回归不破坏。

## 何时进入「待分套」（`needed`）

与故事文首 **合订触发**、US-7 spec 一致；US-9 **不弱化**自动标，只补逃生可达性。

| 触发 | 行为 | US-9 说明 |
|------|------|-----------|
| 老师点 **「这是合订本 / 需要分套」** | `mark-needed` → `needed`；可请求建议页码、预填按页拆分 | 老师意图明确；不属于「误伤单套」 |
| 拉取 **结构化结果**（`GET …/structured`）且当前为 `none`，异常列表含 **「重复」**（题号 `order_index` 重复） | 服务端写库 `needed` 并返回 | 与 US-7 相同；单套若解析出重复也会被标待分套，靠 **按单套继续** 退出 |
| 已是 `needed` / `single_ok` / `done` | 不因重复再次改写状态 | `done` 父本永久挡确认 |

**主动合订 vs 自动重复**：主动合订**不依赖**已拆题；重复路径可在老师第一次打开结构化面板时写 `needed`。二者汇合后 UI 均为待分套 + 可切开或按单套继续。

**按单套继续前置条件**（与 US-7 相同）：仅当 `anthology_split_status===needed` 且**尚未切开**（父本未 `done`）。`single_ok` 后允许 `structured/confirm`；`confirm_blocked_message` 对 `single_ok` / `none` 返回空。

## 老师路径（对照 AC）

### AC-1：单套可直接结构化

1. 上传**单套**验收用中考 PDF（非合订主验收材料）。  
2. 不点「这是合订本」。  
3. 完成拆题 / 结构化，且结构化异常中**无**题号重复（或重复未触发写库——以当前实现：无「重复」文案则不写 `needed`）。  
4. **Then**：不出现「必须先确认多套边界才能确认」的硬挡；`anthology_split_status` 保持 `none`（或自始至终未进入 `needed`）；可走 US-1 至 **确认结构化**。

### AC-2：误判时可按单套继续

1. 材料处于 `needed`（误点合订，或重复题号自动标）。  
2. 老师打开 **结构化结果区**（与禁用「确认结构化」同一屏）。  
3. 点 **「按单套继续」** → `single_ok`。  
4. **Then**：确认按钮可用；`POST structured/confirm` 成功；后续考点 / 说明路径与单套 US-1 相同；**无需**在拆分框填写第二套页码。

**备选路径（已有，本故事不删）**：Chat 按页拆分区内的「按单套继续」仍可用；US-9 验收至少覆盖 **结构化区** 按钮一次。

## 与 US-7 状态机（复述）

| 值 | 确认结构化 | US-9 关注点 |
|----|------------|-------------|
| `none` | 允许（另有结构化校验） | 单套日常默认 |
| `needed` | 禁止 | 结构化区须有「按单套继续」 |
| `single_ok` | 允许 | 逃生成功态 |
| `done` | 禁止（父合订） | 不能对父本点单套继续冒充整本确认 |

子材料切开后为 `none`，走 US-1/US-8，不在 US-9 范围。

## 实现策略（做法 ①）

### 前端（主交付）

**修改**：`frontend/src/components/StructuredResultPanel.tsx`

- 当 `data.anthology_split_status === "needed"` 时（且非 `done`）：
  - 展示简短中文：**待分套**说明——可去 Chat 按页切开，或若实际只有一套则点下方按钮。
  - 渲染 **「按单套继续」** 按钮（loading / 错误提示与 Chat 同级体验即可）。
  - 请求：`POST /api/conversations/{conversationId}/papers/{paperId}/anthology-split/single-ok`（`conversationId`、`paperId` 从组件已有 props / 结构化拉取上下文取得；若组件缺 `conversationId`，从父级传入一次，**不**新造全局状态）。
  - 成功：重新拉取 structured（或合并响应中的 `anthology_split_status`），解除确认按钮 `disabled`；可显示绿色/中性成功句（与 Chat `setSplitNote` 语义一致）。
- 当 `single_ok`：不展示合订父本那类「此为合订父本…」sky 条（该条仅 `done` / 父本语境；`needed` 条与 `done` 条文案需区分：**待分套整卷** vs **已切开父本**）。
- **不改**：`done` 时仍禁用确认并保留 US-8 首套引导文案；Chat 合订按钮、自动 suggest 预填、`split-by-pages` 行为不动。

### 后端

- **默认无新接口、无新列**；`single-ok` 与 `GET structured` 重复→`needed` 逻辑保持现状。
- 若实现中发现 StructuredResultPanel 无法拿到 `conversationId`，仅在路由/父组件 **透传现有会话 id**（最小 props 增量）。

### 测试

- **后端**：在 `test_anthology_split_api.py` 增加或收紧：`needed` → `single_ok` → `POST structured/confirm` → 200；`none` 材料 confirm 回归 200；`done` 仍 400。
- **前端**：本行可手工验收清单为主（结构化区按钮可见、点后 confirm 可点）；若有既有前端测试基建再补一条可选。

## 错误与边界

| 场景 | 期望 |
|------|------|
| `single-ok` 在非 `needed` 状态调用 | 400「仅待分套材料可选择按单套继续」（已有） |
| 已切开父本 `done` | 无「按单套继续」；只能选子套材料 |
| 老师点合订后决定真是合订 | 继续用按页拆分，**不**强制点单套继续 |
| 重复题号但老师坚持单套 | 结构化区「按单套继续」→ `single_ok`；异常列表仍可展示，不强制清重复 |
| 网络失败点单套继续 | 中文错误提示，状态仍为 `needed`，可重试 |

## 20 分钟（方案 A，记入本 spec）

- US-9 **不**引入计时 UI、不写库计时字段。
- 合订首套 ≤20 分钟仍属 **US-8 产品外挂秒表**；US-9 产品验收为：**单套路径走通** + **至少一次结构化区「按单套继续」**（或等效 API 链路），不与 20 分钟绑在同一 AC。

## 怎样算过（任务单 / 故事）

| 交付 | 说明 |
|------|------|
| 单套 PDF 走通 | 不强制多套确认即可到可确认结构化（AC-1） |
| 一次按单套继续 | 从 `needed` 经结构化区按钮到 `single_ok` 并确认成功（AC-2） |
| 产品经理 | 对照 US-9 Given/When/Then；与五模块统一验收时可合并填表 |

## 不改什么

- 不修改 `list_anomalies` / 重复判定规则；不修改 `GET structured` 自动写 `needed` 条件。  
- 不修改 `suggest-page-ranges`、启发式、`split-by-pages`、labels、父→`done`。  
- 不修改 US-8 父本 `done` 门禁与首套说明绑定规则。  
- 不新增 MCP；师生可见文案不带密钥与卷子正文堆栈。

## 附录：US-9 产品验收记录（模板）

与五模块统一验收时可填；本故事可单独附页。

| 字段 | 填写 |
|------|------|
| 验收日期 | |
| 验收人 | |
| AC-1 材料 | 单套中考 PDF 名称 |
| AC-1 是否点合订 | 否 |
| AC-1 结果 | 通过 / 不通过 |
| AC-2 如何进入待分套 | 误点合订 / 重复题号（注明） |
| AC-2 逃生入口 | 结构化区「按单套继续」（必勾） |
| AC-2 确认结构化 | 通过 / 不通过 |
| 回归：按页拆分仍可用 | 未测 / 通过 |
| 回归：真合订 `done` 父本仍不能确认 | 未测 / 通过 |

## 下一步

- **Spec**：2026-11-17 操作者验收通过（`status: approved`）。
- **Plan**：`docs/superpowers/plans/2026-11-17-us9-anthology-single-paper.md`。
- **研发**：待操作者明确开工后按 plan 执行；五模块产品验收仍统一延后。
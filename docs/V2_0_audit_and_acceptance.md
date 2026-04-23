# V2.0 首发：现状审计与验收

本文档对应计划中的「盘点数据流 / 联调与产品验收」交付物，便于研发与测试对齐。

## 1. 现状审计（Sprint 1 基线）

### 1.1 结构化结果

| 项 | 说明 |
|----|------|
| 来源 | Agent 工具 `structure_exam_paper` 调用 `paper_ai.structure_paper_text`，将 `raw_text` 拆为 `StructuredPaper`，写入 `ExamPaper.parsed_json` |
| 对齐 | `save_alignment_metadata` 写入 `alignment_json`（年级、学科、题型数） |
| 考点 | `run_knowledge_analysis` 写入 `knowledge_analysis_json` 与 `knowledge_markdown_path` |
| 缺口 | 无「已解析 / 已确认」持久状态；V2.0 通过 `structured_confirm_status` 等字段补齐 |

### 1.2 材料与绑定

| 项 | 说明 |
|----|------|
| 创建 | `POST /api/chat/stream` 在上传/URL/首条粘贴时创建 `ExamPaper` |
| 列表 | `GET /api/conversations/{id}/papers` 返回 `id, source_type, raw_path` |
| 绑定 | 系统消息中注入 `paper_id`；多材料时靠提示用户报 id |
| 缺口 | 无 `display_name` 与重命名；V2.0 由 `display_name` + 前端目标材料 + `target_paper_id` 表单字段解决 |

### 1.3 任务 / 步骤状态

| 项 | 说明 |
|----|------|
| Agent | `graph.astream` + 内存 `_agent_run_tasks`；`GET .../agent-run-active` 表示会话级是否在跑 |
| 缺口 | 无与 PRD 五步一一对应的产品态；V2.0 由 `GET .../workflow` 基于 `ExamPaper` 与产物推导 |

## 2. 验收标准（BKL-024 / BKL-025）

### 2.1 结构化确认（模块 A）

- [ ] 选择材料后，可拉取并展示结构化摘要（标题、大题数、小题数、题型等）。
- [ ] 可编辑并保存，保存后回读一致。
- [ ] 未点击「确认」时，`save_alignment_metadata` / `run_knowledge_analysis` 等工具侧拒绝并提示先确认（若已打通后端约束）。
- [ ] 点击「确认」后状态变为已确认；明显异常有提示（重题号等）。
- [ ] 「重新结构化」会触发新一轮 Agent（聊天流）且绑定当前 `target_paper_id`。

### 2.2 显式工作流（模块 B）

- [ ] 主界面显示五步：上传、结构化、分析考点、生成练习、下载；状态与 `GET /workflow?paper_id=` 一致。
- [ ] 会话有 Agent 运行时，流式区仍可用；步骤「进行中」与 `agent-run-active` 可一起理解。

### 2.3 多材料（模块 C）

- [ ] 材料列表显示友好名，可重命名并持久化。
- [ ] 可切换目标材料；发送消息、拆题等使用 `target_paper_id` 绑定。
- [ ] 多份材料时切换目标后，结构化面板与流程条针对当前材料，无明显串台。

### 2.4 回归

- [ ] 无材料时首条长文本仍创建材料并可继续。
- [ ] 按页拆分、考点 PDF、练习 PDF 链接仍可从产物区打开。

## 3. 数据库与发布注意

- 使用 SQLite 时，新列通过启动时 `ALTER TABLE ... ADD COLUMN` 补齐；首次部署后无需手工删库。
- 若生产环境对 Schema 有更强约束，可再引入 Alembic；当前仓库以 `create_all` + 轻量迁移为主。

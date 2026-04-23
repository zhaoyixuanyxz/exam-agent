# V2.1 增强包：实现说明与验收

本文档对应 `new/V2任务表.md` 中 **BKL-026～BKL-043**，便于研发、测试与产品对齐。

## 1. 练习生成配置

### 1.1 数据与接口

- 材料表 `exam_papers.last_practice_config_json`：保存每份材料最近一次练习配置快照（SQLite 启动时自动 `ALTER TABLE` 补列）。
- `POST /api/chat/stream` 表单字段 **`practice_generate_config`**：JSON 字符串，服务端校验后与当前 `paper_id` 对应材料合并写入 `last_practice_config_json`，并在用户消息中追加 **【练习生成默认配置】** 块供 Agent 遵循。
- 出题工具 `generate_chunk_practice_pdf` / `generate_chunk_practice_pdfs_batch` 增加 `difficulty`、`question_types_json`、`output_mode`；服务端 `_merge_practice_generation` **以材料上已存配置优先**（同名字段覆盖工具入参），保证界面配置可靠生效。

### 1.2 前端

- 组件：`frontend/src/components/PracticeGenerateConfigPanel.tsx`
- 所有经 `startStream` 发送的回合（含重试按钮）均附带 `practice_generate_config`。
- 切换目标材料时，从 `GET .../papers` 返回的 `last_practice_config` 回填面板。

### 1.3 出题与 PDF

- `output_mode`：`questions_and_answers` 生成习题卷 + 答案卷；`questions_only` 仅生成习题卷，仅入库 `pdf_question` 类型产物。
- `difficulty` / `question_types` 传入 `paper_ai.generate_practice_set` 影响提示词。

## 2. 产物中心

### 2.1 模型与列表 API

- `artifacts` 表扩展：`display_name`、`source_tool`、`output_mode`、`config_snapshot_json`（迁移见 `app/db/migrate.py`）。
- `GET /api/conversations/{id}/artifacts` 每项包含：`id`、`category`、`paper_id`、`paper_display_name`、`created_at`、`source_tool`、`config_snapshot`、`output_mode` 等；旧行缺字段时由路径/文件名等兜底，列表不报错。

### 2.2 前端

- `frontend/src/components/ArtifactCenter.tsx`：按 `category` 分组（考点说明 / 练习卷 / 参考答案），展示元数据；练习类产物支持 **「按此考点再生成」**。

## 3. 会话历史增强

### 3.1 列表 API

- `GET /api/conversations` 每条增加：`subject`、`grade_range`、`last_artifact_category`（由材料 `alignment_json` 与最近 `Artifact` 推导）。
- 查询参数：`subject`（子串匹配学科/标题/预览）、`date_from` / `date_to`（按 `last_activity_at` 日期前缀 `YYYY-MM-DD` 过滤）。

### 3.2 前端

- `ConversationSidebar`：展示学科·年级、最近产物类型；学科搜索 + 最近 7/30 天筛选。
- 右键菜单：**继续主流程**、**重试练习生成**（同一会话 + 当前材料语义，由 `App` 注入 `bootAction` 触发 `Chat` 自动发一轮流式请求）。

## 4. 自动化测试

- `backend/tests/test_api.py`：会话列表 V2.1 字段、学科筛选空结果等。
- 全量：`cd backend && python -m pytest tests/ -q`

## 5. 验收清单（BKL-043）

- [ ] 练习面板修改题量/难度/题型/输出模式后发送消息，数据库中该材料 `last_practice_config_json` 与消息中【练习生成默认配置】一致。
- [ ] `questions_only` 仅产生练习 PDF 产物；`questions_and_answers` 产生练习 + 答案 PDF。
- [ ] 产物中心分组正确，元数据（时间、材料、来源、题量等）合理；「按此考点再生成」可发起新一轮流式任务。
- [ ] 会话列表展示学科/年级/最近产物；学科筛选与 7/30 天筛选结果符合预期。
- [ ] 右键「继续主流程」「重试练习生成」在当前会话内可触发 Agent，且不新开会话分叉。

## 6. 风险与兼容（关闭情况）

**检查项状态（V2.1 收官）**：阶段 4B（`phase-4b-risk-guardrails`）已关闭，对应任务表 **`new/V2任务表.md` → §5.3 / BKL-043A**。

- **旧 artifacts 无元信息**：列表仍返回 `kind`/`name`/`url` 等基础字段，分类归入 `other` 或按 `kind` 映射。
- **配置与 Agent 行为**：以 `last_practice_config_json` + 工具合并为准；提示词中已强调【练习生成默认配置】须与工具参数一致。
- **历史范围**：续作/重试均为**同一会话**，未实现会话分叉或任务复制。

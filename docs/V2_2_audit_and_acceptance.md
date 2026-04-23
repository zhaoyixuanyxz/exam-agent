# V2.2 预研包：实现说明与验收

本文档对应 `new/V2任务表.md` 中 **BKL-044～BKL-051**，范围：**题目资产落库** + **多卷确定性聚合分析原型**（不引入跨卷 LLM）。

## 1. 数据模型

### 1.1 表 `question_assets`

- 位置：`backend/app/db/models.py` → `QuestionAsset`
- 唯一键：`paper_id` + `structured_version` + `question_order`
- 主要字段：`conversation_id`、`section_title`、`qtype`、`stem`、`options_json`、`knowledge_point_keys_json`（来自考点 `mappings`）、`alignment_snapshot_json`（`alignment_json` 快照）
- 新库由 `init_db()` → `Base.metadata.create_all` 创建；旧库在同路径下启动应用时自动建表。

### 1.2 同步策略

- **仅在结构化已确认**（`structured_confirm_status == confirmed`）时写入/重建题目资产。
- **确认接口** `POST /api/conversations/{cid}/papers/{pid}/structured/confirm` 成功提交后，自动调用 `rebuild_question_assets_for_paper_id`，响应体增加 `question_assets_synced`（写入行数）。
- **同版本幂等**：对同一 `paper_id` + `structured_version` 重建时，先删该版本下全部题目行再插入当前 `parsed_json` 展开结果；历史 `structured_version` 行保留，便于追溯。
- **会话删除**：`delete_conversation_cascade` 在删 `artifacts` / `exam_papers` 前先删 `question_assets`。

## 2. API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/conversations/{cid}/papers/{pid}/structured/confirm` | 与 V2.0 相同，另返回 `question_assets_synced` |
| POST | `/api/conversations/{cid}/papers/{pid}/question-assets/rebuild` | 历史回填：对已确认材料重建题目资产 |
| POST | `/api/conversations/{cid}/multi-paper-analysis` | 多卷聚合分析（请求体见 OpenAPI） |

### 2.1 多卷分析请求体（`MultiPaperAnalysisRequest`）

- `paper_ids`：至少 2 个，须属于该 `conversation_id`
- 可选：`subject`、`grade_contains` — 按 `alignment_json` 过滤材料；过滤后不足 2 份则 **400**

### 2.2 多卷分析响应（`MultiPaperAnalysisResponse`）

- `paper_summaries`：题量、考点数、结构化标题与版本等
- `knowledge_coverage_diff`：每卷考点 key 列表、相对其它卷的独有考点、所选卷**交集**考点
- `question_type_distribution`：各卷题型计数
- `repeated_knowledge_points`：至少在 **2** 份卷中出现的考点 key 及题目命中次数
- `chapter_distribution`：按 `knowledge_points[].book_chapter_hint` 聚合（无考点 JSON 时为空）
- `notes`：如无考点分析、无资产行等提示

分析实现：`backend/app/services/multi_paper_analysis.py`（确定性聚合，无新模型调用）。若库中无题目行但材料已确认，会在分析流程内通过 `load_question_assets_or_build` 尝试补建。

## 3. 前端

- `frontend/src/components/MultiPaperAnalysisPrototype.tsx`：勾选 ≥2 份材料 → 调用多卷分析 API → 展示四类结果块
- `frontend/src/App.tsx`：顶部 **工作台 / 多卷分析（预研）** 切换；URL 参数 `view=multi` 可深链（与 `c=` 并存）
- `frontend/src/components/ConversationSidebar.tsx`：**多卷分析（预研）** 快捷入口

## 4. 自动化测试

- `backend/tests/test_multi_paper_analysis.py`：确认同步资产、多卷分析结果、筛选导致有效卷不足、`paper_ids` 长度校验等
- 建议全量：`cd backend && python -m pytest tests/ -q`

## 5. 手工验收清单（BKL-051）

- [ ] 两份材料均完成结构化确认后，数据库 `question_assets` 有对应题目行（或确认接口返回 `question_assets_synced > 0`）
- [ ] 「多卷分析」页勾选两卷后能得到 JSON 结果；共有考点 / 重复考点与材料上考点映射一致
- [ ] `question-assets/rebuild` 对已确认卷可重复执行，题量与结构化一致
- [ ] 删除会话后，题目资产随材料一并删除，无孤儿行

## 6. 预研结论与后续建议

- **可进入题库产品化** 的条件建议：稳定题目标识（超越仅 `order_index`）、考点主数据与跨卷 key 归一、检索与权限模型。
- **当前局限**：跨卷考点身份依赖现有 LLM 给出的 `knowledge_point_key`；聚合为**按 key 字面**统计，不做语义合并。

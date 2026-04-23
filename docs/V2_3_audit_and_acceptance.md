# V2.3 题库产品化：实现范围与验收

本文档与 `new/V2.3任务表.md` 中 `BKL-052`～`BKL-091` 对齐，描述当前仓库可验收范围。

## 1. 数据与迁移

- SQLite 轻量列迁移：[backend/app/db/migrate.py](backend/app/db/migrate.py) 中 `apply_sqlite_question_assets_v23_columns` 为 `question_assets` 追加 V2.3 字段并回填 `business_id`。
- 新表由 `Base.metadata.create_all` 在启动时创建：`app_users`、`knowledge_point_canonicals`、`knowledge_key_mappings`、`question_knowledge_links`、`paper_sets`、`paper_set_items`、`audit_logs` 等。定义见 [backend/app/db/models.py](backend/app/db/models.py)。
- 稳定常量 [backend/app/db/v23_ids.py](backend/app/db/v23_ids.py) 的 `DEFAULT_USER_ID`，与种子用户一致。

## 2. 核心 API

| 能力 | 方法 / 路径 |
|------|-------------|
| 题库列表 | `GET /api/question-bank` |
| 题目详情 | `GET /api/question-bank/{id}` |
| 纠错/审核 | `PATCH /api/question-bank/{id}` |
| 考点字典 | `GET /api/knowledge-master` |
| 考点别名归并 | `POST /api/knowledge-master/merge-alias` |
| 题单列表 | `GET /api/conversations/{cid}/paper-sets` |
| 创建题单 | `POST /api/conversations/{cid}/paper-sets` |
| 题单详情 | `GET /api/conversations/{cid}/paper-sets/{set_id}` |
| 加入题单 | `POST /api/paper-sets/{set_id}/items` |
| 组卷起步 | `POST /api/compile-paper` |
| 多卷分析（增强筛选） | `POST /api/conversations/{cid}/multi-paper-analysis` 请求体含 `use_canonical_knowledge_points`、`created_after`/`created_before`/`paper_id_subset` 等 |
| 当前用户 | `GET /api/me` |
| 审计 | `GET /api/audit-logs`（`role=admin`） |

## 3. 前端

- `react-router-dom` 单页多路由，入口 [frontend/src/App.tsx](frontend/src/App.tsx)，壳 [frontend/src/layout/WorkspaceShell.tsx](frontend/src/layout/WorkspaceShell.tsx)。
- 主要路径：`/workbench`、`/multi`、`/question-bank`、`/governance`、`/org`。
- 默认在请求头携带 `X-User-Id`（见 [frontend/src/api/client.ts](frontend/src/api/client.ts)），与种子默认用户一致。

## 4. 自动化测试

- 后端：在 `backend` 下执行 `python -m pytest tests/ -q`。

## 5. 手工烟测建议

- 工作台完成结构化确认后，数据库存在 `question_assets`；打开「题库」页可检索到题目行。
- 「多卷分析」页勾选 2+ 份材料，勾选「使用标准考点主数据口径」，可得到与 `knowledge_key_mappings` 一致口径的统计（需先经同步产生映射）。
- 「治理」页可对待确认质量题修改 `review_status`。
- 「组织」页使用默认 `X-User-Id` 时应能访问 `/api/me`；审计列表在 admin 下可见（默认种子用户为 `admin`）。

## 6. 已知限制

- 题单与组卷为 MVP 策略（随机+考点约束），题型配比等可后续加强。
- 组织权限为单租户默认用户+角色字段；多租户可在此基础上扩展。

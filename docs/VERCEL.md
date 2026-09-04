# Vercel 部署指南 · exam-agent

把本仓库推到 GitHub 后，在 [Vercel](https://vercel.com) Import，即可得到 `https://<project>.vercel.app`。  
他人打开链接即可使用，**无需本地启动**。

## 架构（与栏目站同类）

| 层 | 实现 |
|----|------|
| 前端 | Vite 构建 → `public/`，由 Vercel CDN / FastAPI SPA 回退托管 |
| API | 根目录 `main.py` → FastAPI（Vercel Python + Fluid Compute；Hobby 默认 `maxDuration` 60s，Pro 可在 `vercel.json` 提到 300） |
| 数据库 | **必须**配置 `DATABASE_URL`（Neon / Supabase Postgres） |
| 文件 | `/tmp/exam-agent-data`（同实例内可用；冷启动可能丢上传原件，正文已进库仍可继续分析） |
| Agent 检查点 | MemorySaver（无持久 graph 状态） |

本地 Docker / `start.bat` 流程不变；本分支只是多了一条 **Vercel 托管路径**。

## 1. 准备 Neon（免费即可）

1. 打开 [neon.tech](https://neon.tech) 新建项目  
2. 复制 **Connection string**（推荐带 `sslmode=require`）  
3. 形如：`postgresql://user:pass@ep-xxx.region.aws.neon.tech/neondb?sslmode=require`  
   应用会自动改成 `postgresql+asyncpg://...`

也可用 Supabase 的 Postgres URI（Transaction pooler 亦可）。

## 2. 在 Vercel 导入仓库

1. Vercel → **Add New Project** → 选中 `exam-agent`  
2. Framework 应自动识别为 **FastAPI**（根目录有 `main.py` + `requirements.txt`）  
3. Build Command 已在 `vercel.json`：`python scripts/vercel_build.py`  
4. 配置环境变量（Production + Preview 都建议填）：

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | ✅ | Neon/Supabase Postgres URI |
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek 密钥 |
| `DEEPSEEK_BASE_URL` | 否 | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-chat` |
| `CORS_ORIGINS` | 否 | 额外前端源；已默认放行 `*.vercel.app` |
| `EXAM_AGENT_SERVERLESS` | 否 | 设 `1` 可强制 serverless 行为（Vercel 上自动生效） |
| `PRACTICE_PDF_LATEX_RENDERER` | 否 | **保持 `off`**（Playwright 不可用） |

5. Deploy → 等待构建完成  
6. 打开 `https://<project>.vercel.app`，再访问 `/api/health` 应返回 `{"status":"ok"}`

## 3. 本地用 Vercel CLI 试跑（可选）

```powershell
cd exam-agent
# 前端构建到 public/
python scripts/vercel_build.py

# 需已安装 Vercel CLI 并登录
$env:DATABASE_URL="postgresql://..."
$env:DEEPSEEK_API_KEY="sk-..."
vercel dev
```

## 4. 已知限制（相对本机 / Docker）

- **长任务**：Hobby 默认 60s；大批量出题/长对话可能超时。Pro 可将 `vercel.json` 里 `maxDuration` 调到 300。过大试卷建议拆分。  
- **上传原件**：落在 `/tmp`，实例回收后按页拆分等依赖原文件的操作可能失败；结构化正文已写入 Postgres 的流程不受影响。  
- **练习 PDF LaTeX / Playwright**：云上关闭；配图走 matplotlib 默认路径。  
- **并发实例**：内存中的「进行中 Agent 任务」不跨实例共享。  

若需要 24×7 大文件 / 强持久磁盘，仍可用原有 **Docker + VPS**（`docs/plan-b-vps-24x7.md`）。

## 5. 验证清单

- [ ] `/api/health` → ok  
- [ ] 打开站点 → 工作台可新建会话  
- [ ] 上传一小份 PDF → 能出结构化结果  
- [ ] 题库 / 多卷分析 Tab 可打开（依赖已确认入库的题）

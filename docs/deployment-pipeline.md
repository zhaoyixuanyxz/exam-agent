# exam-agent 发布流水线设计

> 面向：老师公网可用（挂 IP / 域名）。日常本机 Harness 重启是另一条「开发机更新」，不替代本流水线。  
> 现状：单容器 FastAPI+静态前端（`Dockerfile`）、`docker compose`、数据卷、`scripts/vps-deploy.sh`；**尚无** GitHub Actions。

## 1. 拓扑与约束

| 项 | 选择 |
|----|------|
| 应用 | 单体：Python 3.12 + 已构建 React；SQLite + 文件在 `DATA_DIR` |
| 目标 | 一台轻量云主机（Ubuntu）+ Docker Compose；端口 80→8000 |
| 停机 | 可接受约 1～3 分钟（单机重建镜像） |
| 灰度 | 暂不做流量拆分（无第二台机 / 无 K8s） |
| 密钥 | 仅服务器 `.env.deploy`；CI 用 GitHub Secrets，不进镜像层 |

## 2. 流水线阶段

```
Source (main) → Build & Test → Image → Deploy (VPS) → Smoke → (可选) HTTPS 域名
                     ↑ fail = 不部署
```

| 阶段 | 做什么 | 失败时 |
|------|--------|--------|
| **Build & Test** | `frontend`：`npm ci` + `npm run build`；`backend`：`pytest`（与本地冒烟同集） | 阻断，不构建镜像 |
| **Image** | `docker build`（沿用现有多阶段 Dockerfile） | 阻断 |
| **Deploy** | SSH 到 VPS：`git pull` + `docker compose up -d --build`（或拉取预构建镜像） | 不覆盖成功卷；见回滚 |
| **Smoke** | `curl -f http://127.0.0.1/`；`POST /api/conversations` 期望 200 | 触发回滚 |
| **HTTPS（可选）** | Caddy/Nginx 反代 + Let’s Encrypt | 不影响 HTTP 试点 |

首版推荐：**手动批准后再 Deploy**（GitHub Environment `production` + Required reviewers = 你本人）。

## 3. 部署策略（单机滚动）

无蓝绿机时的稳妥做法：

1. `docker compose build`（新镜像）
2. `docker compose up -d`（替换同名容器）
3. 数据卷 `exam-agent-data` **不删**
4. Smoke 失败 → 回滚到上一镜像 tag

镜像打标签：`exam-agent:sha-<短 SHA>`，同时动 `exam-agent:latest`。回滚只改 tag 再 `up -d`，不动 volume。

## 4. 健康检查

| 层级 | 检查 | 用途 |
|------|------|------|
| 浅 | `GET /` → 200（静态壳） | Compose / 负载探活 |
| 深 Smoke | `POST /api/conversations` → 200 且返回 `conversation_id` | 发布门禁 |
| 依赖 | 进程内能读 `DEEPSEEK_API_KEY`（启动时校验非空，勿把 key 打进日志） | 避免「页面开了但 AI 全挂」 |

SSE 长连接：前置反代须加大 `proxy_read_timeout`（仓库 Dockerfile 注释已提示）。

## 5. 门禁

| 门 | 规则 |
|----|------|
| 合并门 | `main` 仅接受已过 pytest 的 PR（后续 Actions 强制） |
| 发布门 | Environment `production` 人工点 Approve |
| 自动回滚门 | Smoke 任一失败 → 切回上一 `sha-*` 并再 Smoke |

不做：覆盖率硬阈值、DAST（首版过重）。

## 6. 回滚手册（人工）

在 VPS 上：

```bash
cd /opt/exam-agent
# 假设曾标记 previous
docker tag exam-agent:sha-<上一短SHA> exam-agent:latest   # 或 compose image 字段指向旧 tag
docker compose up -d
curl -sf http://127.0.0.1/ >/dev/null && echo OK
```

注意：SQLite **向前兼容**迁移可保留；若某版做过破坏性 schema，回滚代码前须确认迁移可逆（当前 migrate 以 ADD COLUMN 为主，符合「只增不删」）。

## 7. 密钥与域名

- **密钥**：服务器 `.env.deploy`；CI SSH 用 Deploy key / `VPS_SSH_KEY` Secret。
- **域名（可选）**：DNS A 记录 → 公网 IP；Caddy `reverse_proxy localhost:8000`；安全组放行 80/443。
- **无域名**：继续 `http://公网IP` 试点（勿长期裸奔敏感数据）。

## 8. 与「发到 Harness」的关系

| 路径 | 何时用 |
|------|--------|
| **本流水线 / VPS** | 老师用浏览器上网访问 |
| **Harness 本机更新** | 你自己日常跑服务的那台：拉 `main`、装依赖、重启 uvicorn；不经公网 |

两条可并存；公网上线以本设计为准。

## 9. 落地清单（下一批）

1. 加 GitHub Actions：`test`（PR + main）+ `deploy`（main + environment 批准）
2. VPS 装好 Docker，clone 私仓，写好 `.env.deploy`
3. 第一次手动 `./scripts/vps-deploy.sh` 打通
4. （可选）域名 + HTTPS
5. 把 Smoke 脚本收成 `scripts/smoke.sh` 供 CI 与本机共用

下一步 skill：`github-actions-templates`（把上述阶段写成可合并的 workflow YAML）。

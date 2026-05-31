# 方案 B：云主机 24 小时在线（成本低 · 部署最简）

> **你不开机，同事也能用**：程序跑在便宜云服务器上，同事只打开 `http://公网IP`（或域名），**不用装 Tailscale、不用装 Python**。

---

## 和方案 A 怎么选？

| | 方案 A（本机 + Tailscale） | **方案 B（云主机 + Docker）** |
|--|---------------------------|-------------------------------|
| 你电脑要常开 | ✅ 要 | ❌ **不用** |
| 同事要装 Tailscale | ✅ 要 | ❌ **不用** |
| 月成本 | 电费 | **约 ¥40～70**（轻量服务器） |
| 部署难度 | 已会 | **买机 + 复制 4 条命令** |
| 适合 | 临时试点 | **长期给教研组用** |

---

## 要花多少钱？（结合你现状）

| 项目 | 费用 | 说明 |
|------|------|------|
| **云服务器** | ¥48～68/月 常见 | 腾讯云 / 阿里云 **轻量 2核2G** 即可 |
| **DeepSeek API** | 按用量 | 和你本机一样，Key 写在服务器 `.env.deploy` |
| **域名** | 可选 ¥50/年 | 没有也能用 **公网 IP** 访问 |
| **Tailscale** | 可不用 | 方案 B 不依赖 Tailscale |

新用户常有 **首月优惠 / 新客券**，买前在控制台领券。

**比 24 小时开自己电脑更省**：笔记本常开耗电、损耗更大；轻量机专做服务更稳。

---

## 你需要准备什么？

| 物品 | 你有吗 |
|------|--------|
| GitHub 私有仓库（已 push 代码） | ✅ 已有 |
| DeepSeek API Key | ✅ 本机 `backend/.env` 里已有 |
| 本机 Windows | 用来 **SSH 上传配置**，不要求常开 |
| 云厂商账号 | 需注册（微信/支付宝实名） |

**不需要**：在本机装 Docker（可选）；同事不需要任何开发环境。

---

## 总流程（一张图）

```mermaid
flowchart LR
    Buy[买轻量服务器 Ubuntu] --> SSH[SSH 登录服务器]
    SSH --> Clone[git clone 私有仓库]
    Clone --> Env[配置 .env.deploy]
    Env --> Docker[docker compose up -d]
    Docker --> URL[http://公网IP]
    URL --> Users[同事浏览器打开]
```

---

## 第 1 步：买一台最便宜的 Linux 服务器

任选其一（界面类似）：

- [腾讯云轻量应用服务器](https://cloud.tencent.com/product/lighthouse)
- [阿里云轻量应用服务器](https://www.aliyun.com/product/swas)

**购买时注意：**

| 选项 | 建议 |
|------|------|
| 地域 | 选离你同事近的（如华东） |
| 镜像 | **Ubuntu 22.04** |
| 规格 | **2核 2GB** 内存 |
| 带宽 | 3～5M 够用 |
| 登录 | 设 **root 密码** 或绑定 SSH 密钥 |

买好后在控制台记下 **公网 IP**（例如 `123.56.78.90`）。

---

## 第 2 步：放行 80 端口（必做）

在云平台 **防火墙 / 安全组** 里添加：

| 协议 | 端口 | 来源 |
|------|------|------|
| TCP | **80** | 0.0.0.0/0 |

否则外网打不开网页。

---

## 第 3 步：SSH 登录服务器

在你 **Windows** 上打开 PowerShell：

```powershell
ssh root@你的公网IP
```

第一次会问 `yes/no`，输入买机器时设的密码。

> 也可用腾讯云网页里的 **「登录」→ OrcaTerm**，不用装 SSH 客户端。

---

## 第 4 步：在服务器上拉代码并启动

### 4.1 安装 Docker（只需一次）

```bash
apt-get update -qq
apt-get install -y docker.io docker-compose-v2 git
systemctl enable --now docker
```

### 4.2 克隆你的私有仓库

**方式 A — HTTPS + 个人访问令牌（推荐）**

1. GitHub → **Settings → Developer settings → Personal access tokens** → 生成 token（勾选 `repo`）
2. 在服务器上：

```bash
cd /opt
git clone https://github.com/zhaoyixuanyxz/exam-agent.git
cd exam-agent
```

提示用户名填 `zhaoyixuanyxz`，密码处 **粘贴 token**（不是 GitHub 登录密码）。

**方式 B — 本机已能 push 的电脑生成部署密钥**  
在服务器生成 SSH key 加到 GitHub Deploy keys，再用 `git@github.com:...` clone。

### 4.3 配置 API 密钥

```bash
cp .env.deploy.example .env.deploy
nano .env.deploy
```

填入（和本机 `backend/.env` 相同即可）：

```env
DEEPSEEK_API_KEY=sk-你的密钥
```

`Ctrl+O` 保存，`Ctrl+X` 退出。

### 4.4 一键构建并后台运行

```bash
chmod +x scripts/vps-deploy.sh
./scripts/vps-deploy.sh
```

或：

```bash
docker compose up -d --build
```

首次构建约 **5～15 分钟**（取决于网速）。完成后：

```bash
docker compose ps
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/
```

返回 `200` 即成功。

---

## 第 5 步：发给同事

```text
试卷考点助手（在线版）：
http://你的公网IP

用 Chrome / Edge 打开即可。
第一次使用：顶栏「操作指南」→ 工作台上传试卷 → 确认结构化。
```

**不需要** Tailscale、不需要装软件。

---

## 把本机已有题库迁到服务器（可选）

你 Windows 上若已有 `data/`（题库、SQLite），可打包上传：

**在本机 PowerShell：**

```powershell
cd "c:\Users\zhaoy\Desktop\试卷考点解析式agent\exam-agent"
# 需安装 OpenSSH 客户端
scp -r data root@你的公网IP:/opt/exam-agent/
```

**在服务器上：**

```bash
cd /opt/exam-agent
docker compose down
# 确保 data 目录权限
chown -R root:root data
docker compose up -d
```

> 若服务器是全新 volume，可把本机 `data` 拷到 volume 挂载路径；简单做法如上，直接放到项目 `data/` 需在 compose 里改挂载为 `./data:/app/data`（见下「进阶」）。

默认 compose 使用 **Docker 卷** `exam-agent-data`。导入旧数据：

```bash
docker compose down
docker run --rm -v exam-agent_exam-agent-data:/data -v /opt/exam-agent/data:/backup alpine cp -a /backup/. /data/
docker compose up -d
```

（先把本机 `data` 传到服务器 `/opt/exam-agent/data`。）

---

## 日常运维（你会用到的 3 条命令）

在服务器 `/opt/exam-agent` 目录：

```bash
# 看是否在跑
docker compose ps

# 拉最新代码并重启（你 push GitHub 之后）
git pull
docker compose up -d --build

# 看日志（排查 AI 不回复）
docker compose logs -f --tail 100
```

---

## 更新程序（你在本机改完 push 之后）

```bash
ssh root@公网IP
cd /opt/exam-agent
git pull
docker compose up -d --build
```

同事 **不用** 做任何事，刷新网页即可。

---

## 安全建议（公网必看）

| 风险 | 建议 |
|------|------|
| 谁都能访问 | 尽快加 **HTTPS + 简单密码**（见下） |
| API Key 在服务器 | 勿泄露 `.env.deploy` |
| 默认无登录 | 仅发链接给信任同事；后期可加 Nginx 基础认证 |

**免费 HTTPS（有域名时）**：在服务器装 Caddy 或 Certbot 反代 80→8000。  
**无域名**：可继续 `http://IP` 内网试点；敏感环境勿长期裸 IP。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 外网打不开 | 检查安全组 **80**、服务器 `docker compose ps` |
| 构建失败 | `docker compose logs`，多半是内存不足，换 2G+ |
| AI 不工作 | `docker compose exec exam-agent cat /app/backend/.env` 勿进容器；查 `.env.deploy` 和 DeepSeek 余额 |
| 想关机回家 | **随便关自己电脑**，服务在云上 |

---

## 和你本机 / MCP 的关系

| 工具 | 作用 |
|------|------|
| **本机 Windows** | 开发、`git push`；**不必 24 小时开机** |
| **GitHub** | 代码中心；服务器 `git pull` 更新 |
| **Cursor MCP（GitHub 等）** | 帮你管仓库；**同事用不到** |
| **Tailscale** | 方案 B **可停用**；同事直接访问公网 IP |

---

## 进阶（以后有需要再做）

- 绑定域名 + HTTPS  
- 自动备份 `exam-agent-data` 卷  
- 把 `docker-compose.yml` 的 volume 改成 `./data:/app/data` 方便直接拷文件夹  

---

*方案 B · 仓库内 `Dockerfile`、`docker-compose.yml`、`.env.deploy.example`、`scripts/vps-deploy.sh`*

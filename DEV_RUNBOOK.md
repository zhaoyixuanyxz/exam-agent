# 开发与排障手册（手动操作指南）

当自动化脚本 `scripts\run-checks.ps1` 或 `start.ps1` 失败时，按下列顺序自查。

## 环境要求

- **Python**：3.11+（推荐 3.11–3.12）。若使用 3.14，可能出现 LangChain 相关告警，一般仍可运行。
- **Node.js**：18+（用于前端 Vite）。
- **操作系统**：Windows 10/11（脚本为 PowerShell；也可在 macOS/Linux 中手动执行等价命令）。

### PowerShell 脚本乱码或「字符串缺少终止符」

Windows PowerShell 5.x 默认按**系统代码页**读取脚本；UTF-8（无 BOM）中文易乱码并可能触发解析错误。根目录 **`start.ps1` 现为纯 ASCII**（提示语为英文），不依赖 BOM 即可在 PS 5.x 下稳定解析。其他脚本若含中文，请用「UTF-8 with BOM」保存，或改用 **PowerShell 7+**（`pwsh`）。

## 一键检查（推荐先跑）

在 `exam-agent` 根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-checks.ps1
```

若某一步失败，根据下方章节处理。

## 后端：虚拟环境与依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest tests -q
```

常见错误：

- **`python` 不是内部或外部命令**：将 Python 安装目录加入 PATH，或使用 `py -3.12 -m venv .venv`。
- **pip 安装超时**：配置国内 PyPI 镜像后重试。

## 后端：环境变量与 DeepSeek

在 `backend` 目录创建 `.env`（可复制仓库根目录的 `.env.example`）：

- `DEEPSEEK_API_KEY`：必填，否则 Agent 调用模型会失败。
- `KAITI_FONT_PATH`：可选；未设置时会在 Windows 常见路径查找楷体。PDF 生成报字体错误时，设为本地 `.ttf` 绝对路径。

若出现 **401** 且提示里带 `****-key`：多半是系统里曾配置过 **`OPENAI_API_KEY=missing-key`** 等错误值。本应用会**优先使用 `backend/.env` 文件中的 `DEEPSEEK_API_KEY`**；仍异常时请打开「系统属性 → 环境变量」检查用户/系统中是否有多余的 `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`，删掉或改正后重启终端与后端。

## 后端：手动启动 API

```powershell
cd backend
.\.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **端口 8000 被占用**：改用 `--port 8001`，并同步修改 `frontend\vite.config.ts` 里 `proxy` 的目标端口。

## 前端：依赖与构建

```powershell
cd frontend
npm install
npm run build
```

- **`npm` 不可用**：安装 [Node.js LTS](https://nodejs.org/) 并重新打开终端。
- **构建报 TypeScript 错误**：执行 `npm run build` 查看具体文件与行号，对照仓库内 `tsconfig.json`。

## 一键体验界面

- **方式 A**：双击 `start.bat`。
- **方式 B**：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

若提示无法运行脚本，以管理员 PowerShell 执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 测试数据库说明

运行 `pytest` 时，`tests\conftest.py` 会设置 `EXAM_AGENT_TEST_DB_PATH`，使用临时 SQLite 文件，**不会**覆盖你日常使用的 `data\app.db`。

## 仍无法解决时

请保留完整终端输出（含报错栈），并说明：操作系统版本、Python/Node 版本、是否已配置 `.env`、失败命令是哪一条。

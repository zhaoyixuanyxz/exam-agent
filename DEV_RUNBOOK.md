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
- `FIGURE_EXPORT_DPI`：可选；练习 PDF 中 matplotlib 栅格图（及 composite 内 SVG 栅格）的导出分辨率，默认 `168`，有效范围约 `72`～`600`。印刷试跑时可提高到 `200`～`300`。
- `FIGURE_TEXTBOOK_STYLE`：可选；设为 `1` / `true` / `yes` 时略微压低网格透明度、加大标题与轴间距，使折线/柱状等更像教材排版。直角坐标图（plot/bar/histogram 等）的网格透明度另由 `practice_figure_theme.chart_grid_alpha` 与上述开关共同决定。

练习配图线宽、流程图箭头、场线/光路线型等集中在 `backend/app/services/practice_figure_theme.py`，修改风格时优先改该文件再视需要微调渲染逻辑。

`circuit_simple` 支持的元件类型见 `PracticeCircuitElement`（含 wire、resistor、cell、capacitor、lamp、switch、ammeter、voltmeter、generic）；节点为数据坐标，可用 `via` 折点绘制非直导线。

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

## 分块练习 PDF 支持的 figure_kind（概要）

出题 JSON 中 `figure_kind` / `figure_spec` 经解析与 clamp 后，可由后端渲染并嵌入练习 PDF 的种类包括：`plot`（`fill_between`、`draw_as` line/scatter、`y_err`、可选 `series_right` 双 y 轴）、`bar`、`grouped_bar`、`pie`、`geometry`（点线标签及可选 `circles` / `polygons` / `arcs`；标签可选 `use_mathtext` 走 matplotlib **mathtext**，与正文 `_flatten_math_to_text` 不同）、`flowchart`（`layout`: `circular` | `layered`；节点可选 `use_mathtext`）、`force_diagram`（箭头 `label` 可选 `use_mathtext`）、`circuit_simple`、`svg`（内联 `<svg>...</svg>`，经消毒后以矢量嵌入 PDF）、`composite`（`panels` 内嵌下列**非 composite** 种类含 `svg`，至多 6 格；**svg 子图**需 **cairosvg + 系统 cairo** 栅格化，见下节）、`table`、`timeline`、`number_line`、`venn`、`histogram`，以及 **Phase 10** 学科配图：`solid_wireframe`（立几线框，`isometric`/`cabinet`；**Phase 11** 可选 `section_faces`、`auxiliary_edges`）、`field_lines`（手写 **lines**、可选 **presets** 点电荷/螺线管/长直导线示意、可选 **uniform_field**；三者至少其一）、`probability_tree`（单根概率树）、`pedigree`（遗传系谱）、`energy_profile`（能垒折线）、`electrochemical_cell`（原电池/电解池示意）、`unit_circle_trig`（单位圆与三角函数线）、`optics_ray`（**Phase 11**：`interface_orientation` horizontal/vertical/angled、可选主光轴与薄透镜符号；`rays` 非空），以及 **Phase 11** `directed_graph`（节点 `layer` + `layout` layered/circular，边可选 `label`）。**圆锥曲线 / 波动叠加**：无单独 kind，用高密度 `plot` 或 `composite` 组合（如 `plot` + `geometry` 标注）。**食物链/网**：优先 `directed_graph`（layered）或 `flowchart` + `layered`。详情以 [`app/services/paper_ai.py`](backend/app/services/paper_ai.py) 中 `_PRACTICE_SCHEMA` 与 [`app/models/schemas.py`](backend/app/models/schemas.py) 为准。非像素级烟测见 `tests/test_phase10_figure_kinds.py`、`tests/test_phase11_figure_gaps.py`。

## 分块练习配图：cairosvg 与系统 cairo（composite 内 SVG 子图）

`composite` 某一格为 `svg` 时，后端用 **cairosvg** 把该子图栅格成 PNG，再贴进整图；**默认依赖不包含 cairosvg**。安装与系统库如下（最短路径）。

| 环境 | 步骤 |
|------|------|
| **Windows** | 在 `backend` 虚拟环境中：`pip install -e ".[svg]"`（或 `pip install cairosvg>=2.7`）。若导入或运行时报缺 **cairo-2.dll** / `OSError: no library called "cairo-2"`：需安装带 cairo 的运行库（常见做法：安装 [GTK3 Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) 并把其 `bin` 加入 PATH，或使用已打包好 cairo 的 Python 发行渠道）。**未就绪时**：该格会显示「(子图略)」，其余子图仍可出图；pytest 中带 composite+SVG 的用例会 `skip`。 |
| **Linux (Debian/Ubuntu 等)** | `sudo apt install libcairo2-dev pkg-config`（或发行版等价包），再 `pip install -e ".[svg]"`。 |
| **macOS** | `brew install cairo pango pkg-config`，再 `pip install -e ".[svg]"`。 |

**无 cairo / cairosvg 时的预期**：composite 中非 SVG 子图正常；**仅 SVG 子图**为占位，与有 cairo 的机器对比同一份 JSON 时，composite 整图可能不同——属预期差异。

### 彩印与出图默认值（Phase 9）

- 程序配图默认 **DPI 168**（`practice_figure_render._FIG_DPI`），与 composite 内 SVG 栅格化一致；彩印可适当提高纸张质量设置，无需改代码即可受益。
- 避免整版**浅 pastel 大色块**叠印发灰；示意填充与透明度已在默认渲染中收敛。
- 线宽、字号、系列色以模块内常量为准（`PRINT_SERIES_PALETTE`、`LW_*`、`FS_*`）；大改版后可用 `tests/test_phase9_golden_figures.py`、`tests/test_phase10_figure_kinds.py`、`tests/test_phase11_figure_gaps.py` 做非像素级回归。

### CI 建议

若流水线镜像已含 cairo：安装 `.[svg]` 并跑全量 pytest。无 cairo 的 job 保持当前策略即可（composite SVG 用例 skip）。

## 练习 PDF：LaTeX 公式子系统（可选 KaTeX / TeX）

默认 **`PRACTICE_PDF_LATEX_RENDERER=off`**，行为与仅 Unicode 扁平化一致，无额外依赖。

| 模式 | 说明 |
|------|------|
| **katex** | Python 可选依赖 `pip install -e ".[latex]"`，再执行 `playwright install chromium`。渲染时通过 **CDN** 加载 KaTeX 静态资源（需外网）。栅格 PNG 缓存在 `data/<PRACTICE_PDF_LATEX_CACHE_DIR>`。 |
| **tex** | 本机安装 TeX Live / MiKTeX，`pdflatex` / `xelatex` 在 PATH；含中文内层时优先 `xelatex`。 |

环境变量见仓库根目录 `.env.example`（`PRACTICE_PDF_LATEX_*`、`PRACTICE_PDF_WRITE_FORMULA_DIAGNOSTICS`）。

与 **`PRACTICE_PDF_INLINE_MATHTEXT`** 同时开启时的优先级：**先 LaTeX 子系统（分流命中）→ 再 matplotlib mathtext → 再 Unicode 扁平化**。

集成测试：`pytest -m katex`（需 `RUN_KATEX_INTEGRATION=1` 且已安装 Playwright 与浏览器）。

## SSE 与反向代理超时

对话接口 `POST /api/chat/stream` 为 **长连接 SSE**。若经 **Nginx / Caddy / 云网关** 转发，默认 `proxy_read_timeout`（或等价项）过短时，可能在模型或工具仍在执行时**被中间层断开**，前端表现为请求失败或流中断。

**缓解**（按所用代理查阅官方文档核对指令名）：

- **Nginx**：对转发到本后端的 `location` 增大 `proxy_read_timeout`（例如 `300s` 或更高），并确保 `proxy_buffering off` 或合理缓冲以免首包延迟。
- **Caddy**：使用 `flush_interval`、适当增大与上游读相关的超时（版本差异大，以当前 Caddyfile 文档为准）。

本地直连 `uvicorn` 一般无此问题。整体响应速度优化与模型侧专项无关，本条仅作部署层缓解说明。

## 仍无法解决时

请保留完整终端输出（含报错栈），并说明：操作系统版本、Python/Node 版本、是否已配置 `.env`、失败命令是哪一条。

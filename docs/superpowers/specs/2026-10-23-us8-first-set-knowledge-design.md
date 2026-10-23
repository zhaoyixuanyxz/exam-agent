---
artifact: design
story: US-8
version: "1.0"
created: 2026-10-23
status: draft
---

# US-8 设计：分套后至少一套能出该套考点说明

对应故事：`docs/2026-10-23-合订本多卷-stories.md` 的 US-8。  
对应 PRD：`docs/2026-10-23-合订本多卷-prd.md`（FR-4～FR-6）。  
任务单：`docs/2026-10-23-合订本多卷-任务单.md` 的 US-8 行。  
依赖：US-7 已验收（PR #8）；考点彩色 PDF 能力来自 US-2 / US-4。

本设计经 brainstorming 选定「方案 1：薄体验」。

## 做法

在现有「选中材料 → 拆题 → 确认 → 对齐 → 考点说明 PDF」路径上加薄引导与父本硬挡，不重做考点引擎，不做产品内秒表。

1. **切开后选中第一套**  
   `split-by-pages` 成功且返回 `new_papers` 非空时：前端 `setTargetPaperId(new_papers[0].id)`（与 ranges 顺序第一条一致），并短提示：「已选第一套（{label}），请拆题并确认后出考点说明。」  
   不自动调用 `structure_exam_paper`，不自动确认结构化。

2. **父本 `done` 硬挡考点/练习**  
   当材料 `anthology_split_status == "done"` 时，下列工具拒绝并返回固定中文短句（勿带密钥/堆栈）：  
   - `run_knowledge_analysis`  
   - `generate_chunk_practice_pdf`  
   - `generate_chunk_practice_pdfs_batch`  
   - `generate_all_practice_pdfs`  
   文案示例：「该材料为已切开的合订本原件，请改选切开后的子材料再出考点/练习。」  
   抽共用判断（如 `refuse_if_anthology_parent_done`），避免复制。  
   父本「确认结构化」继续由 US-7 门禁负责；本行不放宽。

3. **子材料走现有路径**  
   对选中的子 `paper_id`：拆题 → 老师确认（套内题号自洽）→ 对齐 → 考点分析生成彩色 PDF，artifact 绑定该 `paper_id`。  
   验收判定：不是父本上的整本说明冒充通过。

4. **20 分钟**  
   仅验收秒表：从上传合订 PDF 起，到首套「结构化已确认 + 该套考点说明 PDF 入库」。产品不做计时 UI。

5. **超时**  
   沿用 US-6：「连接超时建议重试」；已切开材料与已入库文件保留。本行回归抽查即可。

## 怎样算过（对照 US-8 AC）

- AC-1：选中子套拆题并确认；无跨套重复题号作为完成态。  
- AC-2：该套考点说明 PDF 可打开且绑定子材料。  
- AC-3：含 US-7 分套在内，秒表 ≤ 20 分钟达首套。  
- AC-4：超时文案与保留行为符合 US-6。

## 不改什么

- 不自动拆题/自动确认/自动出考点。  
- 不重做分套 UI（US-7）。  
- 不要求全部年份都出说明；不默认多卷分析。  
- 不新增 MCP；不改删除 PDF 语义；不做产品内秒表。

## 测试

- 单元/API：父本 `done` 调考点与练习工具 → 拒绝文案；子本 `none` 不受影响。  
- 前端：拆分成功后目标材料为 `new_papers[0]`（可用手动验收）。  
- 真人：广州合订本计时走通首套 AC-1～3。

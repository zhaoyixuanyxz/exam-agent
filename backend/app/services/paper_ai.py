"""LLM extraction: plain completion + JSON parse (no LangChain json_schema)."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.models.schemas import (
    KnowledgeAnalysisResult,
    PracticeQuestion,
    PracticeSet,
    StructuredPaper,
)
from app.services.json_from_llm import parse_pydantic_from_llm_text
from app.services.practice_clamp import clamp_practice_set
from app.services.practice_parse import parse_practice_set_from_llm_text

MAX_CHARS = 48_000

_JSON_ONLY = (
    "你必须只输出一个 JSON 对象，不要 markdown 说明，不要代码块标记以外的文字。"
    "JSON 必须可被 Python json.loads 解析。"
)


def _chat(*, max_tokens: int | None = None) -> ChatOpenAI:
    kwargs: dict = dict(
        model=settings.deepseek_model,
        api_key=settings.require_deepseek_api_key(),
        base_url=settings.deepseek_base_url,
        temperature=0.2,
    )
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


def _invoke_text(system: str, human: str, *, max_tokens: int | None = None) -> str:
    llm = _chat(max_tokens=max_tokens)
    msg = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
    if isinstance(msg, AIMessage):
        c = msg.content
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            parts = []
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "".join(parts)
    return str(msg.content)


_STRUCTURE_SCHEMA = (
    "根对象字段：title(string)；sections(数组)，每项 title、questions；"
    "questions 每项含 order_index、qtype、stem、options(字符串数组)、blocks(数组可空)。"
    '示例：{"title":"","sections":[{"title":"","questions":['
    '{"order_index":1,"qtype":"选择题","stem":"...","options":["A","B"],"blocks":[]}]}]}'
)


def structure_paper_text(raw_text: str) -> StructuredPaper:
    text = raw_text[:MAX_CHARS]
    system = (
        "你是试卷结构化助手。将给定试卷文本拆分为章节与题目；保留公式为 LaTeX，用 $...$ 包裹。"
        "表格可写入 stem 纯文本。题型用简短中文。"
        f"{_JSON_ONLY}\n{_STRUCTURE_SCHEMA}"
    )
    raw = _invoke_text(system, text)
    return parse_pydantic_from_llm_text(raw, StructuredPaper)


_KNOWLEDGE_SCHEMA = """
根对象字段：
- theme_title: string，给家长/学生看的简短中文主题（如「2021广州中考数学考点分布」）
- knowledge_points: 数组，每项含 key(英文小写+下划线，仅系统内部用)、name(中文考点名)、summary(中文50字内)、book_chapter_hint(中文，如「七下·三角形」或「通用体系」)
- mappings: 数组，每项含 question_order(整数)、knowledge_point_key(string，须与上列某 key 一致)
"""


def analyze_knowledge(
    paper_summary: str,
    alignment: dict,
) -> KnowledgeAnalysisResult:
    sys = (
        "结合中国大陆初高中教学体系，为每道题标注考点。"
        "**name、summary、theme_title、book_chapter_hint 必须通顺自然的中文**，不要英文句子。"
        "key 仅用英文小写+下划线，供程序关联，不要在 name 里写英文 key。"
        "若无法确定具体书目，book_chapter_hint 写「通用体系」加简要范围即可。"
        f"{_JSON_ONLY}\n{_KNOWLEDGE_SCHEMA}"
    )
    human = f"对齐信息：{alignment}\n\n试卷内容摘要与题目：\n{paper_summary[:MAX_CHARS]}"
    raw = _invoke_text(sys, human)
    return parse_pydantic_from_llm_text(raw, KnowledgeAnalysisResult)


_PRACTICE_QTYPES_LINE = "单选、多选、填空、简答、判断（qtype 字段必须恰好为这五个词之一，勿写「选择题」「主观题」等别名）。"

_PRACTICE_SCHEMA = f"""
根对象字段（类型必须严格）：
- knowledge_point_key: string
- knowledge_point_name: string
- questions: 数组；每项为对象，必须含：
  - order_index: 数字整数（不要用字符串 "1"）
  - qtype: string，仅限 {_PRACTICE_QTYPES_LINE}
  - stem: string
  - options: 字符串数组；单选/多选须为非空选项数组，填空/简答/判断一般为 []
  - answer_outline: string
  - figure_kind: string，仅限 "none"、"plot"、"bar"、"grouped_bar"、"pie"、"geometry"、"flowchart"、"composite"、"table"、"timeline"、"number_line"、"venn"、"histogram"、"force_diagram"、"circuit_simple"、"svg"、"solid_wireframe"、"field_lines"、"probability_tree"、"pedigree"、"energy_profile"、"electrochemical_cell"、"unit_circle_trig"、"optics_ray"、"directed_graph"；无示意图时为 "none"
  - **配图风格（总）**：拓扑清晰、符号在枚举内的示意用结构化 figure_kind；**精细几何、复杂光路、非枚举电路符号**等优先 **figure_kind: svg**（完整 `<svg>...</svg>`，仅用 path/rect/circle/line 等常见标签，勿 script）；**circuit_simple** 仅用于节点坐标明确的教材式电路拓扑（wire/resistor/cell/battery/capacitor/lamp/switch/rheostat/fuse/diode/ammeter/voltmeter 等），勿勉强塞复杂原图。
  - figure_spec: 当 figure_kind 为 none 时不要写该字段或设为 null；否则须与种类一致：
    - plot：title, x_label, y_label, y_label_right, caption 可空；series 非空数组，每项 label、x、y（x/y 等长且**每条至少 2 个点**，数字）；每项可选 draw_as 为 "line" 或 "scatter"；可选 y_err 与 x 等长（非负，误差棒）；可选 series_right 数组（右 y 轴曲线，结构同 series，与 series_right 同时存在时勿再用 log_y）；可选 log_y(boolean)、show_legend(boolean)，默认 true；可选 fill_between 数组，每项 x、y_lower、y_upper（或 y1/y2）等长且至少 2 点，可选 alpha、color、label，用于曲线间阴影/面积示意。
      **连续函数图象**（二次函数、抛物线、反比例、指对数、幂函数、三角函数图像等）：若要用 plot，每条 series 的 x 须在合理区间内**等距取不少于 20 个点**，y 须按**题干同一关系式严格计算**；**禁止**用少于 12 个点折线冒充光滑曲线；无把握则 **figure_kind 必须为 none**。
    - bar / grouped_bar / pie：与此前一致；**数据须与题干一致，勿虚构**。
    - geometry：点 points（id,x,y）、线段 segments（a,b 为点 id）、标签 labels（每项 text、x、y；**可选 use_mathtext**，为 true 时 text 按 matplotlib **mathtext** 子集解析，须写 $...$，JSON 内反斜杠双写如 $\\\\frac{{a}}{{b}}$；为 false 或未写时 $ 视为普通字符）；可选 circles、polygons、arcs 同前。**题干若写角平分线、高线、中线与边的交点等，图中须用线段画出该线且交点须在对应边上（坐标与几何关系一致），不得只画外包多边形而省略题干所述辅助线。**
    - flowchart：nodes（id,text，**可选 use_mathtext** 含义同上）、edges（source,target）；可选 layout 为 "circular"（默认）或 "layered"（自上而下，**无环** DAG，有环则勿用 layered）。
    - force_diagram：forces 非空数组，每项 x0,y0 与 x1,y1（或 dx,dy）为数字箭头，可选 label、**use_mathtext**、color；可选 object_dot(boolean)、object_x/object_y 表受力中心；**object_style** 为 "dot"（默认）或 "block"（方块物体）；**show_axes_hint** 为 true 时绘浅色正交参考轴；**normalize_force_lengths** 为 true 时将各力箭头缩放到同一长度（方向不变，共点于物体中心或各箭尾均值）。
    - circuit_simple：至少 2 个 nodes（id,x,y 数字坐标）、edges（source,target 为 node id、element 为 wire/resistor/cell/battery/**capacitor**/lamp/switch/rheostat/fuse/diode/ammeter/voltmeter/generic，可选 via 折点数组每项 x,y）；switch 可选 **switch_state** 为 "open"/"closed"；rheostat 可选 **slider_position** 为 0~1 表示滑片相对位置。
    - svg：**内联矢量**；figure_spec 须含非空 **svg** 字符串（完整 `<svg ...>...</svg>`，勿外链脚本）；title、caption 可空；仅用常见图形标签（path/rect/circle 等），勿 script/foreignObject。
    - composite：**多子图合一**；title、caption 可空；ncols 为 1～3；panels 为非空数组（**至多 6 项**），每项 kind（plot/bar/grouped_bar/pie/geometry/flowchart/table/timeline/number_line/venn/histogram/force_diagram/circuit_simple/svg/**solid_wireframe**/**field_lines**/**probability_tree**/**pedigree**/**energy_profile**/**electrochemical_cell**/**unit_circle_trig**/**optics_ray**/**directed_graph**，**勿嵌套 composite**）、subtitle 可空（如「甲」「①」）、spec 与同 kind 顶层 figure_spec 结构一致；**svg 子图在服务端栅格化**，勿过大。
    - table：title、caption 可空；rows 为非空二维字符串数组；headers 可空，若给出则列数应与每行一致。
    - timeline：title、caption 可空；items 非空，每项 label、t（数字时刻）；可选 t_min、t_max、connect(boolean)。
    - number_line：title、caption 可空；x_min、x_max 数字且 x_max>x_min；marks 可空（每项 x、label）；intervals 可空（每项 a、b、open_left/open_right 布尔）。
    - venn：title、caption 可空；n_sets 为 2 或 3；label_a/b/c 可空；文字区 only_a、only_b、only_c、ab、ac、bc、abc 可空（按集合数填写）。
    - histogram：title、caption、x_label、y_label 可空；edges 为升序边界数组（长度 bins+1）；counts 为非负数组且长度等于 len(edges)-1。
    - solid_wireframe：立体线框；projection 为 "isometric"、"cabinet" 或 **"oblique"**（斜二测，教材常用）；vertices 至少 2 项（每项 id,x,y,z）；edges 至少 1 条（a,b 为顶点 id）；可选 faces（vertex_ids 环、alpha、fill_color、edge_color）；可选 **section_faces**（截面等，语义同 faces，渲染对比更强）；可选 **auxiliary_edges**（a,b、style 为 solid/dashed、可选 label）；labels 可空（text,x,y，可选 use_mathtext）。
    - field_lines：须至少具备下列之一——**lines**（每项 x、y 等长且至少 2 点，可选 color、arrow）、**presets**（物理示意数组，每项 kind 为 "point_charge"（cx,cy,sign±1,n_lines,r_max,r_min 可选）、"solenoid"（x0,y0,w,h,b_direction 为 up/down/left/right,nx,ny,draw_frame）、"long_straight_wire"（cx,cy,n_circles,r_max,current_out_of_page,arc_fraction））、或 **uniform_field**（dx,dy,label）；lines 与 presets 可同图叠加。
    - probability_tree：nodes 非空；每项 id、text；**恰一个根**：parent_id 为空或指向不存在 id；非根须 parent_id 指向已有 id；edge_label 为枝上条件概率文案；leaf_note 可空（叶下说明）。
    - pedigree：individuals 非空（id、generation、sex 为 male/female/unknown、affected、carrier、**deceased**、可选 x_hint 0～1）；marriages 可空（left,right）；descents 可空（mother,father,child）；可选 **proband_id**（先证者 id，须存在于 individuals）；**show_legend** 为 true 时在图内角标符号说明（默认 false，系谱简单时可省略）。
    - energy_profile：x、y 等长至少 2 点；可选 barrier_i、barrier_j 为状态点下标与 barrier_label 表活化能双箭头。
    - electrochemical_cell：left_label、right_label、electrolyte_label 可空；mode 为 "galvanic" 或 "electrolytic"；electron_cw 表外电路电子沿上导线方向；cation_to/anion_to 为 "left"/"right"/"none"；**salt_bridge_u** 为 true 时绘制倒 U 形盐桥连接两侧液面。
    - unit_circle_trig：angle_deg；show_sin/show_cos/show_tan 布尔；angle_label 可空。
    - optics_ray：rays 非空（x0,y0,x1,y1、可选 label、color、style solid/dashed）；**interface_orientation** 为 "horizontal"（默认，**interface_y** 为水平界面）、"vertical"（**interface_x** 竖直界面）或 "angled"（**interface_pivot_x/y**、**interface_angle_deg** 定义倾斜界面）；medium_top_label/medium_bottom_label 可空（水平时表上下介质，竖直时可表左右侧说明）；show_normal 布尔；可选 **principal_axis**（x0,y0,x1,y1 点划线主光轴）；可选 **thin_lens**（center_x,center_y,diameter,convex_toward_right）。
    - directed_graph：有向图（食物链/物质流等）；**nodes** 非空（id,text，**layer** 0～40 用于分层，可选 use_mathtext）；**edges** 可空（source,target，可选 label）；**layout** 为 "layered"（按 layer 分行）或 "circular"。
      **圆锥曲线 / 波动叠加**：无单独 kind；主体用 **plot**（x 密采样）+ **composite** 第二格 **geometry** 标焦点/准线，或双 **plot** 子图，勿用少点折线冒充光滑曲线。
      **食物链/网**：优先 **directed_graph**（layered + layer 字段）或 **flowchart**（layered DAG）。
  - source_question_order: 可选整数，表示对应原卷题号（仅在需要引用原卷附图时使用）
  - use_paper_figure: 可选 boolean，为 true 时表示本题尝试使用原卷该题附图（须与 source_question_order 或用户给定索引一致）
  - paper_image_ref: 可选 string，data 目录下已存在的图片相对路径（一般不要用，除非确有路径）
"""


def _subject_figure_hints(subject: str) -> str:
    s = (subject or "").strip()
    hints: list[str] = []
    if any(x in s for x in ("数学", "数", "奥数")):
        hints.append(
            "数学：solid_wireframe（立几线框）、probability_tree、unit_circle_trig、number_line、histogram、plot、fill_between、geometry、svg、composite；圆锥曲线以高密度 plot 为主，可 composite 加 geometry 标注。"
        )
    if any(x in s for x in ("物理", "物")):
        hints.append(
            "物理：field_lines（场线族）、optics_ray（界面与光路）、plot、force_diagram、circuit_simple、bar/grouped_bar、histogram、flowchart、svg、composite。"
        )
    if any(x in s for x in ("化学", "化")):
        hints.append(
            "化学：energy_profile（能垒/历程）、electrochemical_cell（原电池/电解池，可选 salt_bridge_u 盐桥）、solid_wireframe（晶体/装置透视）、table、flowchart、plot、composite；装置复杂图优先原卷或 svg。"
        )
    if any(x in s for x in ("生物", "生")):
        hints.append("生物：pedigree（系谱）、directed_graph（食物链 layered）、venn、flowchart、table、bar、composite。")
    if any(x in s for x in ("语文", "语", "英语", "英", "政治", "政", "历史", "史", "地理", "地", "文综", "理综")):
        hints.append("文史语言类：table、timeline、venn、bar/pie（材料统计）、composite（多材料并列）。")
    if not hints:
        hints.append("通用：按题干可选 table、timeline、venn、composite 等；无把握则 none。")
    return "【本科目配图参考】" + "".join(hints)


def generate_practice_set(
    knowledge_point_name: str,
    knowledge_point_summary: str,
    subject: str,
    grade_range: str,
    n: int = 10,
    *,
    use_original_figures: bool = False,
    include_figures: bool = True,
    original_figure_hint: str | None = None,
) -> PracticeSet:
    _practice_max_tokens = settings.effective_practice_max_output_tokens

    brief = (
        "为防输出截断：每题 stem 控制在约 400 汉字内，answer_outline 约 500 汉字内；"
        "解题步骤精炼，禁止在 JSON 字符串里再嵌套第二段 JSON 或 ``` 代码块。"
        "公式若在 $...$ 内写 LaTeX，JSON 字符串里每个反斜杠须双写（例：\\\\frac{a}{b}、\\\\angle ABC）。"
        "复杂式子（多行对齐、cases、矩阵等）可使用标准 amsmath 环境（如 aligned、cases、bmatrix），服务端可选 KaTeX/TeX 栅格渲染。"
        "角度须写 $90^\\\\circ$ 或 $90^{\\\\circ}$，禁止写 ^\\\\wedge\\\\circ；分式与根式须写完整如 $\\\\frac{\\\\sqrt{2}}{2}$，勿输出裸 frac 与空根号。"
    )

    def _one_batch(n_use: int, attempt: int, order_hint: str = "") -> PracticeSet:
        no_fig_rule = ""
        if not include_figures:
            no_fig_rule = (
                "本题集**禁止任何配图**：每题 figure_kind 必须为 none，不要写 figure_spec，"
                "use_paper_figure 为 false，不要 paper_image_ref。"
            )
        paper_ctx = ""
        if include_figures and use_original_figures and original_figure_hint:
            paper_ctx = (
                "\n【原卷附图索引】下列为题号与解析得到的附图路径，可将某题 source_question_order 对上题号并设 use_paper_figure 为 true；"
                "无对应条目时不要编造路径：\n"
                f"{original_figure_hint}\n"
            )
        sys = (
            f"你是资深命题教师。请为考点「{knowledge_point_name}」设计恰好 {n_use} 道练习题。"
            f"题型只能使用：{_PRACTICE_QTYPES_LINE}"
            "整套题中须覆盖多种题型（不必五种俱全、数量不必均等）。"
            "单选题为单项正确答案；多选题 qtype 须为「多选」且 options 给出多个备选项；判断题用对错或正确/错误类表述。"
            "单选、多选题：备选项**只能**写在 options 数组中；stem 只写提问与已知条件，**切勿**在 stem 末尾再写 A. B. C. D. 行（否则会与 options 重复排版）。"
            "题目要有区分度；answer_outline 写清晰解题要点即可，勿写冗长推演。公式用 LaTeX $...$。"
            + no_fig_rule
            + (
                ""
                if not include_figures
                else (
                    "配图：若题干含「如图」「如图所示」「如下图」「右图」等，**必须**给出 figure_kind 为 geometry、svg 或 composite 的配图，"
                    "且图中须完整呈现题干所述点、线（含角平分线、高、中线等）、交点及字母标注；**禁止**仅有外框而缺题干提到的线。"
                    "无「如图」类字样时：仅当题干**明确写出或表格中给出**可作图数据时才配图；数据不足且无把握时 figure_kind 可为 none，不要强行配图。"
                    "图中数字、类别、点列必须与 stem 中可读信息一致，禁止为凑图虚构数据。"
                    "先判断图种：统计/类别→柱、饼或 histogram；离散折线→plot；材料表→table；进程时间→timeline；集合关系→venn；区间数轴→number_line；"
                    "多幅并列或甲乙图→composite（panels 每项 kind+spec）；几何点线圆弧多边形→geometry；算法/过程→flowchart（可用 layout layered）；受力分析→force_diagram；简易电路→circuit_simple。"
                    "二次函数、抛物线、反比例、指对数等**连续曲线**：要么不配 plot（none），要么 plot 每条线**至少 20 个等距 x** 且 y 按同一式子算对；**严禁**五六个点折线冒充抛物线。"
                    "plot 可用 fill_between 表示两曲线间阴影/面积（数据须与题干一致）。"
                    "figure_spec 必须与 figure_kind 一致；composite 的 panels 不得再嵌套 composite。"
                )
                + (_subject_figure_hints(subject) if subject else "")
            )
            + f"{brief}\n{_JSON_ONLY}\n{_PRACTICE_SCHEMA}"
        )
        human = (
            f"科目：{subject}；年级范围：{grade_range}\n"
            f"考点概述：{knowledge_point_summary[:2000]}\n"
            + paper_ctx
            + f"请输出符合字段的 JSON，questions 数组长度恰好 {n_use}。"
            + order_hint
        )
        if attempt > 0:
            human += (
                "\n（上一轮未通过校验：务必将 order_index 写成纯数字；"
                "options 一律为 JSON 数组如 [\"A\",\"B\"]；不要省略 stem；"
                "LaTeX 命令在 JSON 字符串内须双反斜杠；"
                "若用 plot，每条 series 的 x、y 须等长且**至少 2 个数**，且为数字；"
                "若用 bar，categories 与 values 须等长；若用 grouped_bar，每条 series 的 values 与 categories 须等长；"
                "若用 pie，labels 与 values 须等长、非负且总和大于 0；"
                "若题干为二次函数/抛物线/反比例/指对数等连续曲线，plot 每条 series 须至少约 20 个等距点且 y 与式子一致，否则改为 none；"
                "若用 force_diagram，每条力须为非零向量（x0,y0 到 x1,y1 或 dx,dy）；"
                "若用 circuit_simple，须至少 2 个节点与 1 条有效边且 source/target 均为已有 node id；"
                "geometry 中 polygon 的 vertex_ids 须对应已给出的 points.id；flowchart 的 layered 须无环；"
                "若用 svg，svg 字段须为合法 <svg> 片段且无 script；"
                "use_mathtext 为 true 时图内公式为 mathtext 子集（非正文 LaTeX），反斜杠在 JSON 内须双写。）"
            )
        raw = _invoke_text(sys, human, max_tokens=_practice_max_tokens)
        return parse_practice_set_from_llm_text(raw)

    last_err: Exception | None = None
    ps: PracticeSet | None = None

    def _multi_batch_generate(total: int, chunk: int = 12) -> PracticeSet:
        merged: list[PracticeQuestion] = []
        kp_key, kp_nm = "", ""
        while len(merged) < total:
            need = total - len(merged)
            take = min(chunk, need)
            start = len(merged) + 1
            end = len(merged) + take
            hint = (
                f"整套练习目标共约 {total} 题；本段请恰好输出 {take} 题，"
                f"order_index 从 {start} 连续写到 {end}，勿合并到其他题号。"
            )
            part = _one_batch(take, 0, order_hint=hint)
            got = list(part.questions)[:take]
            if not got:
                raise ValueError("分批出题时某一档返回为空。")
            kp_key = kp_key or part.knowledge_point_key
            kp_nm = kp_nm or part.knowledge_point_name
            merged.extend(got)
        return PracticeSet(
            knowledge_point_key=kp_key,
            knowledge_point_name=kp_nm,
            questions=merged[:total],
        )

    # 9～12 题单次 JSON 常被截断，末尾题丢失；按较小 chunk 分批可显著减少缺题。
    def _chunk_for_n(total: int) -> int | None:
        if total > 12:
            return 12
        if total >= 9:
            return 5
        return None

    chunk0 = _chunk_for_n(n)
    if chunk0 is not None:
        try:
            ps = _multi_batch_generate(n, chunk=chunk0)
        except ValueError as e:
            last_err = e
            ps = None

    if ps is None and n <= 12:
        for attempt, n_use in enumerate(
            (n, max(1, n - 2), max(1, n - 4), min(4, max(1, n)))
        ):
            if n_use < 1:
                continue
            try:
                ps = _one_batch(n_use, attempt)
                break
            except ValueError as e:
                last_err = e
                continue

    if ps is None and n >= 8:
        half = n // 2
        rest = n - half
        try:
            a = _one_batch(
                half,
                0,
                "本批为上半套；order_index 从 1 连续递增。",
            )
            b = _one_batch(
                rest,
                0,
                f"本批为下半套；order_index 从 {half + 1} 连续递增，题型与上一批错开、难度相当。",
            )
            ps = PracticeSet(
                knowledge_point_key=a.knowledge_point_key or b.knowledge_point_key,
                knowledge_point_name=a.knowledge_point_name or b.knowledge_point_name,
                questions=list(a.questions) + list(b.questions),
            )
        except ValueError as e:
            last_err = e

    if ps is None:
        raise ValueError(str(last_err) if last_err else "练习 JSON 解析失败") from last_err
    qs = list(ps.questions)[:n]
    # 重试时会降为 n-2、n-4 题，或模型 JSON 截断导致题数不足；先整批补缺再逐题补缺；最终可少于 n 题，不插入占位题。
    if len(qs) < n:
        need = n - len(qs)
        start_idx = len(qs) + 1
        try:
            extra_hint = (
                f"本批仅补全缺题：请恰好输出 {need} 道，order_index 从 {start_idx} 连续写到 {n}，"
                "与整套卷同一考点、难度相近，题干不得与常见题重复。"
            )
            extra = _one_batch(need, 0, order_hint=extra_hint)
            for eq in list(extra.questions)[:need]:
                qs.append(eq)
        except ValueError:
            pass
    # 仍缺则按单题多次请求（小输出不易截断）；不设上限时用较高重试次数直至题数凑满或接口持续失败
    _max_single_fills = max(40, (n - len(qs)) * 8)
    fill_attempts = 0
    while len(qs) < n and fill_attempts < _max_single_fills:
        fill_attempts += 1
        idx = len(qs) + 1
        try:
            hint_1 = (
                f"仅生成第 {idx} 题一道题：JSON 里 questions 长度必须为 1，"
                f"order_index={idx}，与同一考点、难度与卷内已有题相当，避免重复题干。"
                "题干若含「如图」须带完整配图（含题干所述全部辅助线与交点）。"
            )
            one = _one_batch(1, 0, order_hint=hint_1)
            if one.questions:
                qs.append(one.questions[0])
        except ValueError:
            continue
    if not qs:
        raise ValueError(
            str(last_err) if last_err else "练习 JSON 解析后题目为空，请重试。"
        ) from last_err
    # 能出几题出几题：不凑满 n 也可导出 PDF，禁止用占位题充数
    ps.questions = qs[:n]
    for i, q in enumerate(ps.questions, start=1):
        q.order_index = i
    return clamp_practice_set(ps, include_figures=include_figures)

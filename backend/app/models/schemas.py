from typing import Annotated, Any, Literal, Self, Union

from pydantic import BaseModel, Discriminator, Field, model_validator

# 分块练习 PDF 仅使用以下五种题型（与出题提示、解析归一化一致）
PracticeQtype = Literal["单选", "多选", "填空", "简答", "判断"]
PRACTICE_QTYPE_VALUES: tuple[str, ...] = ("单选", "多选", "填空", "简答", "判断")


class ContentBlock(BaseModel):
    type: Literal["text", "image_ref", "table", "math_latex"]
    content: str = ""
    ref: str | None = None


class QuestionItem(BaseModel):
    order_index: int
    qtype: str = Field(description="选择/填空/判断/主观等")
    stem: str
    options: list[str] = Field(default_factory=list)
    blocks: list[ContentBlock] = Field(default_factory=list)
    # V2.3 题库主数据：可选，用于答案/解析落库
    answer: str | None = None
    explanation: str | None = None
    difficulty: str | None = None
    textbook_version: str | None = None
    chapter_path: str | None = None


class PaperSection(BaseModel):
    title: str = ""
    questions: list[QuestionItem] = Field(default_factory=list)


class StructuredPaper(BaseModel):
    title: str = ""
    sections: list[PaperSection] = Field(default_factory=list)


class AlignmentMeta(BaseModel):
    grade_min: str = Field(description="初一|初二|...|高三")
    grade_max: str
    subject: Literal["数学", "物理", "化学", "生物"] | str
    type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="如 {'选择题':3,'填空题':2}",
    )


class KnowledgePointItem(BaseModel):
    key: str = Field(description="稳定英文或拼音键，用于文件名")
    name: str
    summary: str = Field(max_length=80, description="考点概述50字以内")
    book_chapter_hint: str = ""


class QuestionKnowledgeMapping(BaseModel):
    question_order: int
    knowledge_point_key: str


class KnowledgeAnalysisResult(BaseModel):
    theme_title: str = Field(description="试题考点集结主题名")
    knowledge_points: list[KnowledgePointItem]
    mappings: list[QuestionKnowledgeMapping]


PracticeFigureKind = Literal[
    "none",
    "plot",
    "bar",
    "grouped_bar",
    "pie",
    "geometry",
    "flowchart",
    "composite",
    "table",
    "timeline",
    "number_line",
    "venn",
    "histogram",
    "force_diagram",
    "circuit_simple",
    "svg",
    "solid_wireframe",
    "field_lines",
    "probability_tree",
    "pedigree",
    "energy_profile",
    "electrochemical_cell",
    "unit_circle_trig",
    "optics_ray",
    "directed_graph",
]


class PracticePlotFillBetween(BaseModel):
    """折线图下方或两曲线之间的阴影域；x 与 y_lower、y_upper 等长。"""

    x: list[float] = Field(min_length=2)
    y_lower: list[float] = Field(min_length=2)
    y_upper: list[float] = Field(min_length=2)
    alpha: float = Field(default=0.28, ge=0.0, le=1.0)
    color: str = ""
    label: str = ""

    @model_validator(mode="after")
    def _same_len(self) -> Self:
        n = len(self.x)
        if len(self.y_lower) != n or len(self.y_upper) != n:
            raise ValueError("fill_between: x, y_lower, y_upper must have the same length")
        return self


class PracticePlotSeries(BaseModel):
    """单条折线或散点（x/y 等长）；至少 2 点方可表示折线趋势。"""

    label: str = ""
    x: list[float] = Field(min_length=2)
    y: list[float] = Field(min_length=2)
    draw_as: Literal["line", "scatter"] = "line"
    y_err: list[float] | None = None

    @model_validator(mode="after")
    def _same_len(self) -> Self:
        if len(self.x) != len(self.y):
            raise ValueError("plot series: x and y must have the same length")
        if self.y_err is not None and len(self.y_err) != len(self.x):
            raise ValueError("plot series: y_err length must match x")
        return self


class PracticePlotSpec(BaseModel):
    """折线图参数。"""

    title: str = ""
    x_label: str = ""
    y_label: str = ""
    y_label_right: str = ""
    caption: str = ""
    series: list[PracticePlotSeries] = Field(min_length=1)
    series_right: list[PracticePlotSeries] = Field(default_factory=list)
    log_y: bool = False
    show_legend: bool = True
    fill_between: list[PracticePlotFillBetween] = Field(default_factory=list)


class PracticeBarSpec(BaseModel):
    """单组柱状图：类别与柱高等长。"""

    title: str = ""
    x_label: str = ""
    y_label: str = ""
    caption: str = ""
    categories: list[str] = Field(min_length=1)
    values: list[float] = Field(min_length=1)
    show_values: bool = True

    @model_validator(mode="after")
    def _same_len(self) -> Self:
        if len(self.categories) != len(self.values):
            raise ValueError("bar: categories and values must have the same length")
        return self


class PracticeGroupedBarSeries(BaseModel):
    """分组柱的一条序列：values 与 categories 等长。"""

    label: str = ""
    values: list[float] = Field(min_length=1)


class PracticeGroupedBarSpec(BaseModel):
    """分组柱状图：多组柱子共享同一套类别轴。"""

    title: str = ""
    x_label: str = ""
    y_label: str = ""
    caption: str = ""
    categories: list[str] = Field(min_length=1)
    series: list[PracticeGroupedBarSeries] = Field(min_length=1)
    show_legend: bool = True
    show_values: bool = True

    @model_validator(mode="after")
    def _series_align(self) -> Self:
        n = len(self.categories)
        for i, s in enumerate(self.series):
            if len(s.values) != n:
                raise ValueError(
                    f"grouped_bar series[{i}]: values length must match categories ({n})"
                )
        return self


class PracticePoint2D(BaseModel):
    id: str = ""
    x: float = 0.0
    y: float = 0.0
    style: Literal["auto", "filled", "hollow", "none"] = "auto"


class PracticeSegment(BaseModel):
    a: str = ""
    b: str = ""
    style: Literal["solid", "dashed", "dotted"] = "solid"
    role: Literal["main", "auxiliary", "hidden", "ray", "extension"] = "main"
    color: str = ""


class PracticeGeometryLabel(BaseModel):
    text: str = ""
    x: float = 0.0
    y: float = 0.0
    use_mathtext: bool = Field(
        default=False,
        description="为 true 时按 matplotlib mathtext 解析 text（如 $\\\\frac{a}{b}$）；"
        "false 时 $ 视为字面量。",
    )


class PracticeGeometryCircle(BaseModel):
    """圆：圆心引用点 id，或显式 cx, cy；不完整项在 parse/clamp 中剔除。"""

    center_id: str = ""
    cx: float | None = None
    cy: float | None = None
    r: float = Field(default=1.0, gt=0, le=1e6)
    fill: bool = False
    fill_color: str = ""
    edge_color: str = ""


class PracticeGeometryPolygon(BaseModel):
    """闭合多边形：顶点按顺序为点 id。"""

    vertex_ids: list[str] = Field(min_length=3)
    fill: bool = False
    alpha: float = Field(default=0.22, ge=0.0, le=1.0)
    edge_color: str = ""
    fill_color: str = ""


class PracticeGeometryArc(BaseModel):
    """圆弧：圆心同圆；theta 为度数，逆时针自 x 轴正向起。"""

    center_id: str = ""
    cx: float | None = None
    cy: float | None = None
    r: float = Field(default=1.0, gt=0, le=1e6)
    theta1_deg: float = 0.0
    theta2_deg: float = 90.0
    fill: bool = False
    fill_color: str = ""
    edge_color: str = ""


class PracticeGeometryAngleMarker(BaseModel):
    """角标注：顶点 b，边由 ba 与 bc 构成。"""

    a: str = ""
    b: str = ""
    c: str = ""
    label: str = ""
    right_angle: bool = False


class PracticeGeometrySpec(BaseModel):
    """平面几何草图；由 matplotlib 渲染为 PNG 嵌入 PDF。"""

    title: str = ""
    caption: str = ""
    points: list[PracticePoint2D] = Field(default_factory=list)
    segments: list[PracticeSegment] = Field(default_factory=list)
    labels: list[PracticeGeometryLabel] = Field(default_factory=list)
    circles: list[PracticeGeometryCircle] = Field(default_factory=list)
    polygons: list[PracticeGeometryPolygon] = Field(default_factory=list)
    arcs: list[PracticeGeometryArc] = Field(default_factory=list)
    angle_markers: list[PracticeGeometryAngleMarker] = Field(default_factory=list)
    show_grid: bool = True


class PracticeFlowchartNode(BaseModel):
    id: str = ""
    text: str = ""
    use_mathtext: bool = False
    shape: Literal["process", "start_end", "decision", "data"] = "process"


class PracticeFlowchartEdge(BaseModel):
    source: str = ""
    target: str = ""
    label: str = ""


class PracticeFlowchartSpec(BaseModel):
    """流程图；circular 为圆周布局，layered 为自上而下分层。"""

    title: str = ""
    caption: str = ""
    layout: Literal["circular", "layered"] = "circular"
    nodes: list[PracticeFlowchartNode] = Field(default_factory=list)
    edges: list[PracticeFlowchartEdge] = Field(default_factory=list)


class PracticeForceItem(BaseModel):
    """受力箭头：从 (x0,y0) 指向 (x1,y1)（数据坐标）。"""

    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    label: str = ""
    use_mathtext: bool = False
    color: str = ""
    zorder: int = 2
    label_offset: float | None = Field(
        default=None,
        description="标签沿箭头法线偏移量（数据坐标）；为空时渲染层自动估算。",
    )


class PracticeForceDiagramSpec(BaseModel):
    """共点力示意；不要求数值仿真。"""

    title: str = ""
    caption: str = ""
    forces: list[PracticeForceItem] = Field(default_factory=list)
    object_dot: bool = False
    object_x: float = 0.0
    object_y: float = 0.0
    object_style: Literal["dot", "block"] = "dot"
    show_axes_hint: bool = False
    normalize_force_lengths: bool = False


PracticeCircuitElement = Literal[
    "wire",
    "resistor",
    "cell",
    "battery",
    "capacitor",
    "lamp",
    "switch",
    "rheostat",
    "fuse",
    "diode",
    "ammeter",
    "voltmeter",
    "generic",
]

PracticeCircuitSwitchState = Literal["default", "open", "closed"]


class PracticeCircuitNode(BaseModel):
    id: str = ""
    x: float = 0.0
    y: float = 0.0


class PracticeCircuitVia(BaseModel):
    x: float = 0.0
    y: float = 0.0


class PracticeCircuitEdge(BaseModel):
    source: str = ""
    target: str = ""
    element: PracticeCircuitElement = "wire"
    via: list[PracticeCircuitVia] = Field(default_factory=list)
    switch_state: PracticeCircuitSwitchState = "default"
    slider_position: float | None = Field(default=None, ge=0.0, le=1.0)
    label: str = ""


class PracticeCircuitSpec(BaseModel):
    """简易电路拓扑示意（非 SPICE）。"""

    title: str = ""
    caption: str = ""
    nodes: list[PracticeCircuitNode] = Field(default_factory=list)
    edges: list[PracticeCircuitEdge] = Field(default_factory=list)


class PracticeSvgSpec(BaseModel):
    """内联 SVG 矢量图；须经服务端消毒后再嵌入 PDF。"""

    title: str = ""
    caption: str = ""
    svg: str = Field(min_length=1, description="完整 <svg>...</svg> 片段，UTF-8 文本。")


class PracticePieSpec(BaseModel):
    """饼图：扇区标签与数值等长；渲染时按数值归一化。"""

    title: str = ""
    caption: str = ""
    labels: list[str] = Field(min_length=1)
    values: list[float] = Field(min_length=1)
    percent_digits: int = Field(default=1, ge=0, le=2)

    @model_validator(mode="after")
    def _same_len(self) -> Self:
        if len(self.labels) != len(self.values):
            raise ValueError("pie: labels and values must have the same length")
        return self


class PracticeTableSpec(BaseModel):
    """表格示意图（matplotlib table）。"""

    title: str = ""
    caption: str = ""
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(min_length=1)

    @model_validator(mode="after")
    def _non_empty_rows(self) -> Self:
        if not self.rows:
            raise ValueError("table: rows must be non-empty")
        return self


class PracticeTimelineItem(BaseModel):
    label: str = ""
    t: float = 0.0
    row: int | None = Field(
        default=None,
        ge=-3,
        le=3,
        description="可选行号（负数在轴下、正数在轴上）；为空时自动交错。",
    )


class PracticeTimelineSpec(BaseModel):
    """时间轴（横向节点）。"""

    title: str = ""
    caption: str = ""
    t_min: float | None = None
    t_max: float | None = None
    items: list[PracticeTimelineItem] = Field(min_length=1)
    connect: bool = True
    show_ticks: bool = True


class PracticeNumberLineInterval(BaseModel):
    a: float
    b: float
    open_left: bool = False
    open_right: bool = False


class PracticeNumberLineMark(BaseModel):
    x: float
    label: str = ""


class PracticeNumberLineSpec(BaseModel):
    """数轴与区间示意。"""

    title: str = ""
    caption: str = ""
    x_min: float = 0.0
    x_max: float = 1.0
    marks: list[PracticeNumberLineMark] = Field(default_factory=list)
    intervals: list[PracticeNumberLineInterval] = Field(default_factory=list)
    auto_ticks: bool = True
    tick_count: int = Field(default=8, ge=2, le=16)
    show_axis_arrows: bool = True

    @model_validator(mode="after")
    def _range_order(self) -> Self:
        if self.x_max <= self.x_min:
            raise ValueError("number_line: x_max must be greater than x_min")
        return self


class PracticeVennSpec(BaseModel):
    """韦恩图示意（2 或 3 个集合文字区）。"""

    title: str = ""
    caption: str = ""
    n_sets: Literal[2, 3] = 2
    label_a: str = "A"
    label_b: str = "B"
    label_c: str = "C"
    only_a: str = ""
    only_b: str = ""
    only_c: str = ""
    ab: str = ""
    ac: str = ""
    bc: str = ""
    abc: str = ""


class PracticeHistogramSpec(BaseModel):
    """直方图：edges 长度为 bins+1，counts 长度为 bins。"""

    title: str = ""
    caption: str = ""
    x_label: str = ""
    y_label: str = ""
    edges: list[float] = Field(min_length=2)
    counts: list[float] = Field(min_length=1)
    show_values: bool = True

    @model_validator(mode="after")
    def _bins_match(self) -> Self:
        if len(self.counts) != len(self.edges) - 1:
            raise ValueError("histogram: len(counts) must be len(edges) - 1")
        return self


class PracticeSolidVertex3D(BaseModel):
    """立体线框顶点：逻辑 id + 三维坐标（渲染时投影到平面）。"""

    id: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class PracticeSolidEdge(BaseModel):
    a: str = ""
    b: str = ""
    style: Literal["solid", "dashed", "hidden"] = "solid"
    label: str = ""


class PracticeSolidFace(BaseModel):
    """弱填充面：顶点为顶点 id 环（外轮廓）。"""

    vertex_ids: list[str] = Field(min_length=3)
    alpha: float = Field(default=0.35, ge=0.0, le=1.0)
    fill_color: str = ""
    edge_color: str = ""


class PracticeSolidAuxiliaryEdge(BaseModel):
    """截面/二面角等辅助棱线（虚线或实线）。"""

    a: str = ""
    b: str = ""
    style: Literal["solid", "dashed"] = "dashed"
    label: str = ""


class PracticeSolidWireframeSpec(BaseModel):
    """立体几何线框（轴测/斜二测投影）；适合棱柱、棱锥、简单旋转体示意。"""

    title: str = ""
    caption: str = ""
    projection: Literal["isometric", "cabinet", "oblique"] = "isometric"
    vertices: list[PracticeSolidVertex3D] = Field(min_length=2)
    edges: list[PracticeSolidEdge] = Field(min_length=1)
    faces: list[PracticeSolidFace] = Field(default_factory=list)
    section_faces: list[PracticeSolidFace] = Field(
        default_factory=list,
        description="截面等多强调外轮廓；渲染时与 faces 分层绘制。",
    )
    auxiliary_edges: list[PracticeSolidAuxiliaryEdge] = Field(default_factory=list)
    labels: list[PracticeGeometryLabel] = Field(default_factory=list)


class PracticeFieldLine(BaseModel):
    """单条场线折线；数据坐标系由全体点自动包围盒定标。"""

    x: list[float] = Field(min_length=2)
    y: list[float] = Field(min_length=2)
    color: str = ""
    arrow: Literal["end", "start", "none"] = "end"

    @model_validator(mode="after")
    def _same_len(self) -> Self:
        if len(self.x) != len(self.y):
            raise ValueError("field line: x and y must have the same length")
        return self


class PracticeUniformField(BaseModel):
    """匀强场方向示意（箭头），与 field lines 同图。"""

    dx: float = 1.0
    dy: float = 0.0
    label: str = ""


class PracticeFieldPresetPointCharge(BaseModel):
    """点电荷电场线示意（射线族，非严格数值解）。"""

    kind: Literal["point_charge"] = "point_charge"
    cx: float = 0.0
    cy: float = 0.0
    sign: Literal[1, -1] = 1
    n_lines: int = Field(default=12, ge=3, le=48)
    r_max: float = Field(default=1.6, gt=0, le=12.0)
    r_min: float = Field(default=0.1, ge=0.02, le=2.0)
    color: str = ""


class PracticeFieldPresetSolenoid(BaseModel):
    """螺线管内部 B 方向示意（矩形区域 + 平行箭头族）。"""

    kind: Literal["solenoid"] = "solenoid"
    x0: float = 0.0
    y0: float = 0.0
    w: float = Field(default=1.8, gt=0, le=12.0)
    h: float = Field(default=2.2, gt=0, le=12.0)
    b_direction: Literal["up", "down", "left", "right"] = "right"
    nx: int = Field(default=4, ge=1, le=12)
    ny: int = Field(default=5, ge=1, le=12)
    draw_frame: bool = True
    color: str = ""


class PracticeFieldPresetLongStraightWire(BaseModel):
    """长直导线磁场同心圆示意（右手螺旋）。"""

    kind: Literal["long_straight_wire"] = "long_straight_wire"
    cx: float = 0.0
    cy: float = 0.0
    n_circles: int = Field(default=6, ge=2, le=20)
    r_max: float = Field(default=2.0, gt=0, le=12.0)
    current_out_of_page: bool = True
    arc_fraction: float = Field(default=0.92, ge=0.5, le=1.0)
    color: str = ""


PracticeFieldPreset = Annotated[
    Union[
        PracticeFieldPresetPointCharge,
        PracticeFieldPresetSolenoid,
        PracticeFieldPresetLongStraightWire,
    ],
    Discriminator("kind"),
]


class PracticeFieldLinesSpec(BaseModel):
    """电场/磁场场线族；手写 lines 与物理 presets 可并存；可选匀强场。"""

    title: str = ""
    caption: str = ""
    lines: list[PracticeFieldLine] = Field(default_factory=list)
    presets: list[PracticeFieldPreset] = Field(default_factory=list)
    uniform_field: PracticeUniformField | None = None

    @model_validator(mode="after")
    def _need_content(self) -> Self:
        if not self.lines and not self.presets and self.uniform_field is None:
            raise ValueError("field_lines: at least one of lines, presets, or uniform_field is required")
        return self


class PracticeProbabilityTreeNode(BaseModel):
    """概率树节点；parent_id 为空表示根；edge_label 为从父到本枝上的条件概率文案。"""

    id: str = ""
    text: str = ""
    parent_id: str = ""
    edge_label: str = ""
    leaf_note: str = ""
    order: int = 0
    use_mathtext: bool = False


class PracticeProbabilityTreeSpec(BaseModel):
    title: str = ""
    caption: str = ""
    nodes: list[PracticeProbabilityTreeNode] = Field(min_length=1)


class PracticePedigreeIndividual(BaseModel):
    id: str = ""
    generation: int = Field(default=0, ge=0, le=20)
    sex: Literal["male", "female", "unknown"] = "unknown"
    affected: bool = False
    carrier: bool = False
    deceased: bool = False
    x_hint: float | None = Field(default=None, ge=0.0, le=1.0)
    note: str = ""


class PracticePedigreeMarriage(BaseModel):
    left: str = ""
    right: str = ""


class PracticePedigreeDescent(BaseModel):
    mother: str = ""
    father: str = ""
    child: str = ""


class PracticePedigreeSpec(BaseModel):
    """遗传系谱示意（代际、婚配、亲子）。"""

    title: str = ""
    caption: str = ""
    individuals: list[PracticePedigreeIndividual] = Field(min_length=1)
    marriages: list[PracticePedigreeMarriage] = Field(default_factory=list)
    descents: list[PracticePedigreeDescent] = Field(default_factory=list)
    proband_id: str = ""
    show_legend: bool = False


class PracticeEnergyProfileSpec(BaseModel):
    """反应历程/能垒：折线 + 可选活化能标注（两状态点索引）。"""

    title: str = ""
    caption: str = ""
    x_label: str = ""
    y_label: str = ""
    x: list[float] = Field(min_length=2)
    y: list[float] = Field(min_length=2)
    barrier_i: int | None = Field(default=None, ge=0)
    barrier_j: int | None = Field(default=None, ge=0)
    barrier_label: str = ""
    reactants_label: str = "反应物"
    products_label: str = "生成物"

    @model_validator(mode="after")
    def _same_len(self) -> Self:
        if len(self.x) != len(self.y):
            raise ValueError("energy_profile: x and y must have the same length")
        return self


class PracticeElectrochemicalCellSpec(BaseModel):
    """原电池/电解池示意：两极、外电路电子方向、液相离子方向。"""

    title: str = ""
    caption: str = ""
    left_label: str = ""
    right_label: str = ""
    electrolyte_label: str = ""
    mode: Literal["galvanic", "electrolytic"] = "galvanic"
    electron_cw: bool = Field(
        default=True,
        description="外电路电子箭头沿上导线从左到右为 True；反之为 False。",
    )
    cation_to: Literal["left", "right", "none"] = "right"
    anion_to: Literal["left", "right", "none"] = "left"
    salt_bridge_u: bool = Field(
        default=False,
        description="为 True 时在两侧液面间绘制倒 U 形盐桥示意。",
    )
    half_reaction_left: str = ""
    half_reaction_right: str = ""


class PracticeUnitCircleTrigSpec(BaseModel):
    """单位圆与三角函数线模板。"""

    title: str = ""
    caption: str = ""
    angle_deg: float = 45.0
    show_sin: bool = True
    show_cos: bool = True
    show_tan: bool = False
    angle_label: str = ""


class PracticeOpticsRaySegment(BaseModel):
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 1.0
    y1: float = 0.0
    label: str = ""
    color: str = ""
    style: Literal["solid", "dashed"] = "solid"
    use_mathtext: bool = False


class PracticeOpticsPrincipalAxis(BaseModel):
    """主光轴（点划线线段）。"""

    x0: float = 0.0
    y0: float = 0.0
    x1: float = 1.0
    y1: float = 0.0


class PracticeOpticsThinLens(BaseModel):
    """薄透镜符号（竖直透镜线 + 凹凸示意，非精确成像计算）。"""

    center_x: float = 0.0
    center_y: float = 0.0
    diameter: float = Field(default=1.2, gt=0, le=10.0)
    convex_toward_right: bool = True


class PracticeOpticsRaySpec(BaseModel):
    """几何光学：界面 + 可选主光轴/薄透镜 + 若干射线。"""

    title: str = ""
    caption: str = ""
    interface_orientation: Literal["horizontal", "vertical", "angled"] = "horizontal"
    interface_y: float = 0.0
    interface_x: float = 0.0
    interface_pivot_x: float = 0.0
    interface_pivot_y: float = 0.0
    interface_angle_deg: float = 0.0
    medium_top_label: str = ""
    medium_bottom_label: str = ""
    show_normal: bool = True
    principal_axis: PracticeOpticsPrincipalAxis | None = None
    thin_lens: PracticeOpticsThinLens | None = None
    rays: list[PracticeOpticsRaySegment] = Field(min_length=1)


class PracticeDirectedGraphNode(BaseModel):
    """有向图节点（食物链/物质循环等）；layer 用于分层布局。"""

    id: str = ""
    text: str = ""
    layer: int = Field(default=0, ge=0, le=40)
    use_mathtext: bool = False
    x_hint: float | None = Field(default=None, ge=0.0, le=1.0)
    y_hint: float | None = None


class PracticeDirectedGraphEdge(BaseModel):
    source: str = ""
    target: str = ""
    label: str = ""


class PracticeDirectedGraphSpec(BaseModel):
    """有向图示意；layout 为 layered 时按 layer 字段分行，circular 时圆周排布。"""

    title: str = ""
    caption: str = ""
    layout: Literal["layered", "circular"] = "layered"
    nodes: list[PracticeDirectedGraphNode] = Field(min_length=1)
    edges: list[PracticeDirectedGraphEdge] = Field(default_factory=list)


class PracticeCompositePanelPlot(BaseModel):
    kind: Literal["plot"] = "plot"
    subtitle: str = ""
    spec: PracticePlotSpec


class PracticeCompositePanelBar(BaseModel):
    kind: Literal["bar"] = "bar"
    subtitle: str = ""
    spec: PracticeBarSpec


class PracticeCompositePanelGroupedBar(BaseModel):
    kind: Literal["grouped_bar"] = "grouped_bar"
    subtitle: str = ""
    spec: PracticeGroupedBarSpec


class PracticeCompositePanelPie(BaseModel):
    kind: Literal["pie"] = "pie"
    subtitle: str = ""
    spec: PracticePieSpec


class PracticeCompositePanelGeometry(BaseModel):
    kind: Literal["geometry"] = "geometry"
    subtitle: str = ""
    spec: PracticeGeometrySpec


class PracticeCompositePanelFlowchart(BaseModel):
    kind: Literal["flowchart"] = "flowchart"
    subtitle: str = ""
    spec: PracticeFlowchartSpec


class PracticeCompositePanelTable(BaseModel):
    kind: Literal["table"] = "table"
    subtitle: str = ""
    spec: PracticeTableSpec


class PracticeCompositePanelTimeline(BaseModel):
    kind: Literal["timeline"] = "timeline"
    subtitle: str = ""
    spec: PracticeTimelineSpec


class PracticeCompositePanelNumberLine(BaseModel):
    kind: Literal["number_line"] = "number_line"
    subtitle: str = ""
    spec: PracticeNumberLineSpec


class PracticeCompositePanelVenn(BaseModel):
    kind: Literal["venn"] = "venn"
    subtitle: str = ""
    spec: PracticeVennSpec


class PracticeCompositePanelHistogram(BaseModel):
    kind: Literal["histogram"] = "histogram"
    subtitle: str = ""
    spec: PracticeHistogramSpec


class PracticeCompositePanelForceDiagram(BaseModel):
    kind: Literal["force_diagram"] = "force_diagram"
    subtitle: str = ""
    spec: PracticeForceDiagramSpec


class PracticeCompositePanelCircuit(BaseModel):
    kind: Literal["circuit_simple"] = "circuit_simple"
    subtitle: str = ""
    spec: PracticeCircuitSpec


class PracticeCompositePanelSvg(BaseModel):
    kind: Literal["svg"] = "svg"
    subtitle: str = ""
    spec: PracticeSvgSpec


class PracticeCompositePanelSolidWireframe(BaseModel):
    kind: Literal["solid_wireframe"] = "solid_wireframe"
    subtitle: str = ""
    spec: PracticeSolidWireframeSpec


class PracticeCompositePanelFieldLines(BaseModel):
    kind: Literal["field_lines"] = "field_lines"
    subtitle: str = ""
    spec: PracticeFieldLinesSpec


class PracticeCompositePanelProbabilityTree(BaseModel):
    kind: Literal["probability_tree"] = "probability_tree"
    subtitle: str = ""
    spec: PracticeProbabilityTreeSpec


class PracticeCompositePanelPedigree(BaseModel):
    kind: Literal["pedigree"] = "pedigree"
    subtitle: str = ""
    spec: PracticePedigreeSpec


class PracticeCompositePanelEnergyProfile(BaseModel):
    kind: Literal["energy_profile"] = "energy_profile"
    subtitle: str = ""
    spec: PracticeEnergyProfileSpec


class PracticeCompositePanelElectrochemicalCell(BaseModel):
    kind: Literal["electrochemical_cell"] = "electrochemical_cell"
    subtitle: str = ""
    spec: PracticeElectrochemicalCellSpec


class PracticeCompositePanelUnitCircleTrig(BaseModel):
    kind: Literal["unit_circle_trig"] = "unit_circle_trig"
    subtitle: str = ""
    spec: PracticeUnitCircleTrigSpec


class PracticeCompositePanelOpticsRay(BaseModel):
    kind: Literal["optics_ray"] = "optics_ray"
    subtitle: str = ""
    spec: PracticeOpticsRaySpec


class PracticeCompositePanelDirectedGraph(BaseModel):
    kind: Literal["directed_graph"] = "directed_graph"
    subtitle: str = ""
    spec: PracticeDirectedGraphSpec


PracticeCompositePanel = Annotated[
    Union[
        PracticeCompositePanelPlot,
        PracticeCompositePanelBar,
        PracticeCompositePanelGroupedBar,
        PracticeCompositePanelPie,
        PracticeCompositePanelGeometry,
        PracticeCompositePanelFlowchart,
        PracticeCompositePanelTable,
        PracticeCompositePanelTimeline,
        PracticeCompositePanelNumberLine,
        PracticeCompositePanelVenn,
        PracticeCompositePanelHistogram,
        PracticeCompositePanelForceDiagram,
        PracticeCompositePanelCircuit,
        PracticeCompositePanelSvg,
        PracticeCompositePanelSolidWireframe,
        PracticeCompositePanelFieldLines,
        PracticeCompositePanelProbabilityTree,
        PracticeCompositePanelPedigree,
        PracticeCompositePanelEnergyProfile,
        PracticeCompositePanelElectrochemicalCell,
        PracticeCompositePanelUnitCircleTrig,
        PracticeCompositePanelOpticsRay,
        PracticeCompositePanelDirectedGraph,
    ],
    Discriminator("kind"),
]


class PracticeCompositeSpec(BaseModel):
    """多子图合成一张 PNG；子图不得再嵌套 composite。"""

    title: str = ""
    caption: str = ""
    ncols: int = Field(default=2, ge=1, le=3)
    panels: list[PracticeCompositePanel] = Field(min_length=1, max_length=6)


PracticeFigureSpec = (
    PracticePlotSpec
    | PracticeBarSpec
    | PracticeGroupedBarSpec
    | PracticePieSpec
    | PracticeGeometrySpec
    | PracticeFlowchartSpec
    | PracticeCompositeSpec
    | PracticeTableSpec
    | PracticeTimelineSpec
    | PracticeNumberLineSpec
    | PracticeVennSpec
    | PracticeHistogramSpec
    | PracticeForceDiagramSpec
    | PracticeCircuitSpec
    | PracticeSvgSpec
    | PracticeSolidWireframeSpec
    | PracticeFieldLinesSpec
    | PracticeProbabilityTreeSpec
    | PracticePedigreeSpec
    | PracticeEnergyProfileSpec
    | PracticeElectrochemicalCellSpec
    | PracticeUnitCircleTrigSpec
    | PracticeOpticsRaySpec
    | PracticeDirectedGraphSpec
)


class PracticeQuestion(BaseModel):
    order_index: int
    qtype: PracticeQtype
    stem: str
    options: list[str] = Field(default_factory=list)
    answer_outline: str = ""
    figure_kind: PracticeFigureKind = "none"
    figure_spec: PracticeFigureSpec | None = None
    source_question_order: int | None = Field(
        default=None,
        description="原卷题号；与 use_paper_figure 配合，从结构化试卷中解析附图路径。",
    )
    use_paper_figure: bool = Field(
        default=False,
        description="为 true 时尝试嵌入原卷附图（须通过路径校验）。",
    )
    paper_image_ref: str | None = Field(
        default=None,
        description="显式图片路径（相对 data_dir 或已许可的绝对路径）；优先于按题号查找。",
    )

    @model_validator(mode="after")
    def _figure_consistency(self) -> Self:
        if self.figure_kind == "none":
            self.figure_spec = None
            return self
        if self.figure_spec is None:
            self.figure_kind = "none"
            return self
        kind = self.figure_kind
        spec = self.figure_spec
        mismatch = (
            (kind == "plot" and not isinstance(spec, PracticePlotSpec))
            or (kind == "bar" and not isinstance(spec, PracticeBarSpec))
            or (kind == "grouped_bar" and not isinstance(spec, PracticeGroupedBarSpec))
            or (kind == "pie" and not isinstance(spec, PracticePieSpec))
            or (kind == "geometry" and not isinstance(spec, PracticeGeometrySpec))
            or (kind == "flowchart" and not isinstance(spec, PracticeFlowchartSpec))
            or (kind == "composite" and not isinstance(spec, PracticeCompositeSpec))
            or (kind == "table" and not isinstance(spec, PracticeTableSpec))
            or (kind == "timeline" and not isinstance(spec, PracticeTimelineSpec))
            or (kind == "number_line" and not isinstance(spec, PracticeNumberLineSpec))
            or (kind == "venn" and not isinstance(spec, PracticeVennSpec))
            or (kind == "histogram" and not isinstance(spec, PracticeHistogramSpec))
            or (kind == "force_diagram" and not isinstance(spec, PracticeForceDiagramSpec))
            or (kind == "circuit_simple" and not isinstance(spec, PracticeCircuitSpec))
            or (kind == "svg" and not isinstance(spec, PracticeSvgSpec))
            or (kind == "solid_wireframe" and not isinstance(spec, PracticeSolidWireframeSpec))
            or (kind == "field_lines" and not isinstance(spec, PracticeFieldLinesSpec))
            or (kind == "probability_tree" and not isinstance(spec, PracticeProbabilityTreeSpec))
            or (kind == "pedigree" and not isinstance(spec, PracticePedigreeSpec))
            or (kind == "energy_profile" and not isinstance(spec, PracticeEnergyProfileSpec))
            or (kind == "electrochemical_cell" and not isinstance(spec, PracticeElectrochemicalCellSpec))
            or (kind == "unit_circle_trig" and not isinstance(spec, PracticeUnitCircleTrigSpec))
            or (kind == "optics_ray" and not isinstance(spec, PracticeOpticsRaySpec))
            or (kind == "directed_graph" and not isinstance(spec, PracticeDirectedGraphSpec))
        )
        if mismatch:
            self.figure_kind = "none"
            self.figure_spec = None
        return self


class PracticeSet(BaseModel):
    knowledge_point_key: str
    knowledge_point_name: str
    questions: list[PracticeQuestion] = Field(min_length=1)


class ChatStreamEvent(BaseModel):
    event: Literal["token", "tool", "artifact", "error", "done"]
    data: dict[str, Any] = Field(default_factory=dict)


# --- V2.2 题目资产与多卷聚合分析（预研包） ---


class QuestionAssetDTO(BaseModel):
    """题目资产 API / 分析用 DTO。"""

    id: str
    business_id: str = Field(description="题库业务稳定标识，默认等于 id")
    paper_id: str
    conversation_id: str
    structured_version: int
    question_order: int
    section_title: str = ""
    qtype: str = ""
    stem: str = ""
    options: list[str] = Field(default_factory=list)
    knowledge_point_keys: list[str] = Field(default_factory=list)
    knowledge_point_ids: list[str] = Field(
        default_factory=list,
        description="标准考点主数据 id 列表（V2.3）",
    )
    alignment_snapshot: dict[str, Any] | None = None
    content_fingerprint: str = ""
    answer: str | None = None
    explanation: str | None = None
    difficulty: str | None = None
    textbook_version: str | None = None
    chapter_path: str | None = None
    grade_label: str | None = None
    subject_label: str | None = None
    source_paper_name: str | None = None
    quality_status: str = "pending"
    review_status: str = "pending_review"
    created_at: str | None = None
    updated_at: str | None = None


class MultiPaperAnalysisRequest(BaseModel):
    paper_ids: list[str] = Field(..., min_length=2, description="至少两份材料 id")
    subject: str | None = Field(default=None, description="可选：仅纳入 alignment 中学科匹配的材料")
    grade_contains: str | None = Field(
        default=None,
        description="可选：年级字符串子串匹配（如 初二），对 grade_min/grade_max 做包含判断",
    )
    # V2.3 教研分析：高级筛选
    created_after: str | None = Field(
        default=None,
        description="可选：仅纳入 exam_papers.created_at >= 该 ISO 日期时间的材料",
    )
    created_before: str | None = Field(
        default=None,
        description="可选：仅纳入 exam_papers.created_at <= 该 ISO 日期时间的材料",
    )
    paper_id_subset: list[str] | None = Field(
        default=None,
        description="可选：仅分析该 id 列表与 paper_ids 的交集（用于来源范围）",
    )
    use_canonical_knowledge_points: bool = Field(
        default=True,
        description="为 True 时重复考点/覆盖等优先使用标准考点主数据口径",
    )


class PaperSummaryInAnalysis(BaseModel):
    paper_id: str
    display_name: str | None = None
    structured_title: str = ""
    structured_version: int = 0
    question_count: int = 0
    knowledge_point_count: int = 0


class KnowledgeCoveragePaperSlice(BaseModel):
    paper_id: str
    display_name: str | None = None
    knowledge_point_keys: list[str] = Field(default_factory=list)
    unique_vs_others: list[str] = Field(
        default_factory=list,
        description="仅出现在本卷、未出现在其它所选卷中的考点 key",
    )


class KnowledgeCoverageDiff(BaseModel):
    """考点覆盖：各卷集合与共有考点。"""

    per_paper: list[KnowledgeCoveragePaperSlice] = Field(default_factory=list)
    common_across_selected: list[str] = Field(default_factory=list)


class QuestionTypeCount(BaseModel):
    qtype: str
    count: int


class QuestionTypeDistributionSlice(BaseModel):
    paper_id: str
    display_name: str | None = None
    counts: list[QuestionTypeCount] = Field(default_factory=list)


class RepeatedKnowledgePoint(BaseModel):
    knowledge_point_key: str
    name: str = ""
    paper_count: int = Field(description="所选卷中有多少份卷包含该考点")
    total_question_hits: int = Field(description="跨卷题目行上该考点出现次数之和")


class ChapterHintCount(BaseModel):
    hint: str
    count: int


class ChapterDistributionSlice(BaseModel):
    paper_id: str
    display_name: str | None = None
    chapters: list[ChapterHintCount] = Field(default_factory=list)


class MultiPaperAnalysisResponse(BaseModel):
    conversation_id: str
    paper_summaries: list[PaperSummaryInAnalysis] = Field(default_factory=list)
    knowledge_coverage_diff: KnowledgeCoverageDiff
    question_type_distribution: list[QuestionTypeDistributionSlice] = Field(default_factory=list)
    repeated_knowledge_points: list[RepeatedKnowledgePoint] = Field(default_factory=list)
    chapter_distribution: list[ChapterDistributionSlice] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, description="如无考点分析 JSON 等时的提示")


# --- V2.3 题库 / 题单 / 治理 / 组织 ---


class QuestionBankListResponse(BaseModel):
    items: list[QuestionAssetDTO] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class KnowledgePointCanonicalDTO(BaseModel):
    id: str
    standard_key: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    chapter_path: str | None = None
    subject: str | None = None
    grade_min: str | None = None
    grade_max: str | None = None


class KnowledgePointListResponse(BaseModel):
    items: list[KnowledgePointCanonicalDTO] = Field(default_factory=list)
    total: int = 0


class PaperSetDTO(BaseModel):
    id: str
    conversation_id: str
    name: str
    config_json: dict[str, Any] = Field(default_factory=dict)
    item_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class PaperSetItemDTO(BaseModel):
    id: str
    question_asset_id: str
    sort_order: int = 0


class PaperSetDetailDTO(BaseModel):
    paper_set: PaperSetDTO
    items: list[QuestionAssetDTO] = Field(default_factory=list)


class PaperSetCreateRequest(BaseModel):
    name: str = Field(default="题单")
    config_json: dict[str, Any] = Field(default_factory=dict)


class PaperSetAddItemsRequest(BaseModel):
    question_asset_ids: list[str] = Field(..., min_length=1)


class CompilePaperRequest(BaseModel):
    """组卷起步：题量/题型/考点/难度等参数，结果写入 exports 可后续扩展。"""

    target_count: int = Field(default=10, ge=1, le=200)
    qtype_ratio: dict[str, float] = Field(
        default_factory=dict,
        description="题型名 -> 权重 0~1，未指定部分均分",
    )
    knowledge_point_ids: list[str] = Field(default_factory=list, description="限定考点 id，空=不限")
    difficulty_min: str | None = None
    difficulty_max: str | None = None


class CompilePaperResponse(BaseModel):
    selected_question_ids: list[str] = Field(default_factory=list)
    message: str = ""


class QuestionAssetPatchRequest(BaseModel):
    qtype: str | None = None
    knowledge_point_ids: list[str] | None = None
    difficulty: str | None = None
    chapter_path: str | None = None
    quality_status: str | None = None
    review_status: str | None = None
    answer: str | None = None
    explanation: str | None = None


class AppUserDTO(BaseModel):
    id: str
    display_name: str = ""
    role: str = "teacher"
    data_scope: str = "own"


class AuditLogEntryDTO(BaseModel):
    id: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str = ""
    detail_json: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None

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


class PracticeSegment(BaseModel):
    a: str = ""
    b: str = ""


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


class PracticeFlowchartNode(BaseModel):
    id: str = ""
    text: str = ""
    use_mathtext: bool = False


class PracticeFlowchartEdge(BaseModel):
    source: str = ""
    target: str = ""


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


class PracticeForceDiagramSpec(BaseModel):
    """共点力示意；不要求数值仿真。"""

    title: str = ""
    caption: str = ""
    forces: list[PracticeForceItem] = Field(default_factory=list)
    object_dot: bool = False
    object_x: float = 0.0
    object_y: float = 0.0


PracticeCircuitElement = Literal[
    "wire",
    "resistor",
    "cell",
    "lamp",
    "switch",
    "ammeter",
    "voltmeter",
    "generic",
]


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


class PracticeTimelineSpec(BaseModel):
    """时间轴（横向节点）。"""

    title: str = ""
    caption: str = ""
    t_min: float | None = None
    t_max: float | None = None
    items: list[PracticeTimelineItem] = Field(min_length=1)
    connect: bool = True


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
    projection: Literal["isometric", "cabinet"] = "isometric"
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
    x_hint: float | None = Field(default=None, ge=0.0, le=1.0)


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

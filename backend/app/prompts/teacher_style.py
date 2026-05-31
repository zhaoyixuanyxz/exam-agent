"""朱老师命题与解析风格：难度量表、解析模板、few-shot（源自训练数据）。"""

from __future__ import annotations

from app.config import settings

Difficulty = str  # "easy" | "medium" | "hard"


def _detect_subject(subject: str) -> str:
    s = (subject or "").strip()
    if any(x in s for x in ("数学", "数", "奥数")):
        return "math"
    if any(x in s for x in ("物理", "物")):
        return "physics"
    if any(x in s for x in ("化学", "化")):
        return "chemistry"
    return "generic"


def _is_senior_high(grade_range: str, subject: str = "") -> bool:
    """判断是否高中（高考）阶段。"""
    s = (grade_range or "").lower()
    if any(x in s for x in ("高一", "高二", "高三", "高中", "gaokao", "高考")):
        return True
    # 也支持在 subject 中出现“高中”
    if "高中" in (subject or ""):
        return True
    return False


def _normalize_difficulty(difficulty: str) -> Difficulty:
    d = (difficulty or "medium").strip().lower()
    if d in ("简单", "易", "easy"):
        return "easy"
    if d in ("困难", "难", "hard"):
        return "hard"
    return "medium"


_MATH_DIFFICULTY: dict[Difficulty, str] = {
    "easy": (
        "【数学·简单（基础题，约占 65-70%）】严格 1-2 个核心知识点，思维转换 ≤2 步，无隐藏条件，直接套用通性通法。"
        "典型：顶点式直接读坐标、垂径定理+勾股、弧长公式、整式化简求值。"
        "解析必须写明「直接套用哪个公式/定理」+ 易错点提醒（h 前符号、弦非直径等）。"
        "严禁出现参数讨论、分类、多解法或跨学科元素。"
    ),
    "medium": (
        "【数学·中等（中档题，约占 20-30%）】涉及 3-4 个知识点，思维转换 2-3 步，需建立模型或进行参数/整体思想处理，可能有 1 个隐藏条件。"
        "典型：二次函数实际应用（利润=销量×单价-成本，需求定义域）、圆内接四边形+圆周角、方程与不等式整数解、规律探究。"
        "解析必须写清「如何从实际情境建立等量关系」+「参数讨论或取值范围约束」+ 解题模板。"
        "可出现真实情境，但不得跨学科。"
    ),
    "hard": (
        "【数学·难题（压轴题，约占 10%）】≥4 个知识板块或 2 个大板块深度融合，思维转换 ≥4 步，多解法/分类讨论/隐藏条件≥2，计算量大，常含跨学科或陌生情境。"
        "典型：抛物线+一次函数+三角形面积综合、函数与几何变换+跨学科（物理杠杆）、含参数的分类讨论最值问题、陌生图形需信息提取后建模。"
        "解析必须分情况讨论每种可能性、展示至少两种不同思路、指出计算量差异与易错点。"
        "必须体现「由浅入深、分步得分」的压轴特征。"
    ),
}

_PHYSICS_DIFFICULTY: dict[Difficulty, str] = {
    "easy": (
        "【物理·简单（基础题）】单一知识点直接套用，单一情境，无需信息提取。"
        "典型：凸透镜成像条件 u>2f、光的反射定律画光路、杠杆平衡 F1l1=F2l2 直接计算。"
        "解析按「已知→公式→代入→结论」写清，力臂必须说明「支点到力的作用线的垂直距离」。"
    ),
    "medium": (
        "【物理·中等（中档题）】2-3 个知识点整合，真实生活情境建模，需从题干提取隐含信息。"
        "典型：斜拉桥简化为杠杆模型、多挡位电热器（P=U²/R 判断并联/串联）、电热+比热容+物态变化综合。"
        "解析必须写「情境→物理模型→公式链」+ 实验原理迁移。"
    ),
    "hard": (
        "【物理·难题（压轴/综合题）】≥3 个知识点或多过程，陌生情境/实验数据需大量信息提取，开放性或跨学科。"
        "典型：浮力+液体密度随温度变化+受力分析、多过程能量转化+电路动态变化、真实情境下的实验设计与误差分析。"
        "解析必须分过程画受力/状态图、标注易混概念、讨论边界条件。"
    ),
}

_CHEMISTRY_DIFFICULTY: dict[Difficulty, str] = {
    "easy": (
        "【化学·简单（基础题）】1-2 个基础知识点直接应用，题干信息明确。"
        "典型：化学式意义（原子个数比 vs 质量比）、溶质质量分数定义与均一性、元素质量分数计算。"
        "解析必须逐选项或分步写清「原子个数比≠质量比」等易错点。"
    ),
    "medium": (
        "【化学·中等（中档题）】2-3 个知识点串联，真实情境或表格/微观图需信息提取。"
        "典型：催化剂+微观示意图写方程式、环境空气质量数据提取+质量分数、溶液配制计算+均一性。"
        "解析须先写「反应本质/实验原理」再计算。"
    ),
    "hard": (
        "【化学·难题（综合题）】多步计算或工业/环境/跨学科综合，陌生物质或新定义需信息迁移。"
        "典型：原子守恒配平原料质量比+绿色化学、污染物与 O₃ 生成机理+物质两面性、古代工艺或前沿材料的信息提取与分析。"
        "解析必须分问作答、带单位、讨论实际意义或局限性。"
    ),
}

_GENERIC_DIFFICULTY: dict[Difficulty, str] = {
    "easy": "【通用·简单】1-2 知识点直接套用，单一情境，无隐藏。",
    "medium": "【通用·中等】2-3 知识点整合，需情境建模或信息提取。",
    "hard": "【通用·难题】≥3 知识点或多过程，陌生情境、分类讨论或跨学科。",
}

# ===================== 高中（高考）难度描述 =====================
# 基于 2025-2026 高考命题趋势：反套路、新情境、跨模块、思维品质、开放性

_MATH_DIFFICULTY_HS: dict[Difficulty, str] = {
    "easy": (
        "【高中数学·简单（基础题）】核心概念直接应用，运算准确快速。"
        "典型：集合与逻辑、复数运算、基础三角函数值、简单概率。"
        "解析强调「又快又准」+ 基本概念准确性。"
    ),
    "medium": (
        "【高中数学·中等（中档题）】跨模块综合（函数+导数、向量+几何、概率+统计），常见模型应用，需信息提取与多步推理。"
        "典型：导数应用最值、解析几何弦长/中点、概率模型、统计推断。"
        "解析须写清「模型建立→推理链→结论」。"
    ),
    "hard": (
        "【高中数学·难题（压轴题）】反套路、新定义情境、跨模块深度融合或跨学科，强调逻辑推理、化归转化、创新思维。"
        "典型：新定义数列/函数、概率事件关系研究、三角与不等式综合、立体几何+空间向量、真实情境建模（帆船风速、疾病筛查）。"
        "解析必须展示「情境转化→自主建模→多角度验证」或「存在性证明」，体现探索性与开放性。"
    ),
}

_PHYSICS_DIFFICULTY_HS: dict[Difficulty, str] = {
    "easy": (
        "【高中物理·简单】单一核心规律直接套用，单一情境。"
        "典型：牛顿定律、能量守恒、电路欧姆定律、磁场基本规律。"
    ),
    "medium": (
        "【高中物理·中等】2-3 模块整合，真实情境建模，实验数据处理。"
        "典型：动力学+能量+圆周运动综合、电场+磁场+电磁感应、热力学+气体实验。"
    ),
    "hard": (
        "【高中物理·难题】多过程动态变化、陌生情境或实验设计、开放性探究。"
        "典型：电磁感应+力学综合动态过程、量子/近代物理信息迁移、真实科技情境（人工心脏泵、风光互补）下的建模与误差分析。"
    ),
}

_CHEMISTRY_DIFFICULTY_HS: dict[Difficulty, str] = {
    "easy": (
        "【高中化学·简单】基础概念与简单计算。"
        "典型：物质结构基础、化学计量、简单反应类型。"
    ),
    "medium": (
        "【高中化学·中等】多模块综合（热化学+平衡+电化学、有机推断），真实生产/生活情境。"
        "典型：电化学装置分析、有机合成路线设计、溶液平衡计算。"
    ),
    "hard": (
        "【高中化学·难题】陌生物质/新反应机理、信息大量提取、多步推理或跨学科。"
        "典型：新材料/前沿科技情境下的机理分析、工业流程优化、环境/安全社会议题的辩证分析。"
    ),
}

_FEW_SHOT: dict[str, dict[Difficulty, str]] = {
    "math": {
        "easy": (
            "【解析示范·数学简单】"
            "【思路】考察二次函数顶点式，直接套用 y=a(x-h)²+k 顶点为 (h,k)。"
            "【解答】h 前为负号时顶点横坐标即 h，本题顶点 (2,1)，选 A。"
            "【相关知识点】顶点式性质；易错：h 前符号为负才可直接读坐标。"
        ),
        "medium": (
            "【解析示范·数学中等】"
            "【思路】考查圆内接四边形与圆周角、圆心角；需考虑 A 点两种位置。"
            "【解答】连接 OB、OC，∠BOC=90°；A 在同侧时 ∠A=45°，在异侧时 ∠A'=135°。"
            "【相关知识点】圆周角=同弧圆心角一半；圆内接四边形对角互补；易错：漏讨论 A 的位置。"
        ),
        "hard": (
            "【解析示范·数学难题（压轴特征）】"
            "【思路】抛物线与一次函数+三角形面积综合，含参数分类讨论与跨学科思维。"
            "【解答】(1) 代入 C(1,-3a+c) 得 b=-4a。(2) 利用对称性与面积关系得 E(0,2)，直线 y=-x+2。(3) 联立抛物线与直线，当 x₁<x₂ 且 c=3a 时，分类讨论交点个数：a≥1/3 时恰有一个交点。"
            "【相关知识点】对称性、面积关系、参数分类讨论、函数与几何综合；易错：漏讨论 a>0 及区间端点。"
        ),
        # 高中 hard 示例（反套路 + 新情境）
        "hard_hs": (
            "【解析示范·高中数学难题（反套路·新定义情境）】"
            "【思路】新定义「可以分数列」，研究其与等差/等比数列的关系，需自主建模与存在性证明。"
            "【解答】(1) 由新定义构造辅助函数；(2) 证明存在性而非求具体值；(3) 用数形结合或化归思想验证。"
            "【相关知识点】数列新定义、存在性证明、逻辑严谨性；反套路特征：不依赖传统导数/解析几何模板。"
        ),
    },
    "physics": {
        "easy": (
            "【解析示范·物理简单】"
            "【思路】凸透镜成倒立缩小实像，物距 u>2f。"
            "【解答】u=20cm，故 20>2f，f<10cm，选 5cm。"
            "【相关知识点】u>2f 倒立缩小实像；f<u<2f 倒立放大实像；u<f 正立放大虚像。"
        ),
        "medium": (
            "【解析示范·物理中等】"
            "【思路】多挡位电热器；U 不变时 P=U²/R，总电阻越小功率越大。"
            "【解答】(1) 接 de 时 R₂∥R₃ 为高温挡。(2) W=33000J。(3) I=0.1A。(4) cd 串联 P=22W。"
            "【相关知识点】串并联总电阻；P=UI、P=U²/R。"
        ),
        "hard": (
            "【解析示范·物理难题（多过程+陌生情境）】"
            "【思路】浮力+液体密度随温度变化+受力分析，需从实验数据提取信息并讨论边界条件。"
            "【解答】(1) 悬浮：F浮=G=mg，V排=F浮/(ρ液g)；(2) 温度升高后 ρ 减小，小球由悬浮变为漂浮，浮力仍等于重力，但排开体积增大。"
            "【相关知识点】浮沉条件、阿基米德原理、密度-温度关系、实验数据处理；易混：浮力与重力大小关系在不同状态下的异同。"
        ),
    },
    "chemistry": {
        "easy": (
            "【解析示范·化学简单】"
            "【思路】考察化学式意义，核心是区分原子个数比与元素质量比。"
            "【解答】A. 蔗糖是有机物，A 错。B. 12:22:11 是原子个数比，B 错。C. 分子中无水分子，C 错。D. 氧元素质量分数公式正确，D 对。"
            "【相关知识点】有机物定义；化学式意义；质量比与质量分数；易错：勿把原子个数比当质量比。"
        ),
        "medium": (
            "【解析示范·化学中等】"
            "【思路】结合表格与微观示意图，考察污染物、化学式计算与物质分类。"
            "【解答】(1) PM2.5、O₃ 超标。(2) 硫元素 3μg。(3) 化合物分子 2 种。(4) 示例 CO₂ 利弊分析。"
            "【相关知识点】空气质量标准；质量分数；化合物判定；条件概率树。"
        ),
        "hard": (
            "【解析示范·化学难题（陌生情境+多步综合）】"
            "【思路】催化剂+微观示意图+原子守恒配平+绿色化学，涉及工业原料配比与实际意义讨论。"
            "【解答】(1) 羟基磷灰石质量与性质不变→催化剂。(2) CH₂O+O₂→CO₂+H₂O。(3) 1.5g 甲醛需 O₂ 1.6g。(4) 由原子守恒配平 10CaO+2Ca(OH)₂+3P₂O₅=2Ca₅(PO₄)₃OH，质量比 280:74:213。"
            "【相关知识点】催化剂定义、微观示意图写方程式、原子守恒、原子利用率 100% 的绿色化学意义；易错：配平后仍需验算实际工业可行性。"
        ),
    },
    "generic": {
        "easy": (
            "【解析示范】"
            "【思路】点明单一考点与解题入口。"
            "【解答】分步推导或逐选项分析。"
            "【相关知识点】条目归纳含易错提醒。"
        ),
        "medium": (
            "【解析示范】"
            "【思路】点明 2–3 个知识点的结合方式与关键转化。"
            "【解答】分步推导，选择题逐选项分析。"
            "【相关知识点】条目归纳含易错提醒。"
        ),
        "hard": (
            "【解析示范】"
            "【思路】点明综合板块与分类讨论入口。"
            "【解答】完整分步推导，不跳步。"
            "【相关知识点】条目归纳含易错提醒与拓展衔接。"
        ),
    },
}


def difficulty_temperature(difficulty: str) -> float:
    """按难度返回 LLM temperature（可被 config 覆盖）。"""
    d = _normalize_difficulty(difficulty)
    if d == "easy":
        return settings.practice_difficulty_temperature_easy
    if d == "hard":
        return settings.practice_difficulty_temperature_hard
    return settings.practice_difficulty_temperature_medium


def _subject_difficulty_hints(subject: str, difficulty: str, *, grade_range: str = "") -> str:
    d = _normalize_difficulty(difficulty)
    kind = _detect_subject(subject)
    is_hs = _is_senior_high(grade_range, subject)

    if is_hs:
        tables = {
            "math": _MATH_DIFFICULTY_HS,
            "physics": _PHYSICS_DIFFICULTY_HS,
            "chemistry": _CHEMISTRY_DIFFICULTY_HS,
        }
        framework = "朱老师高中（高考）框架"
    else:
        tables = {
            "math": _MATH_DIFFICULTY,
            "physics": _PHYSICS_DIFFICULTY,
            "chemistry": _CHEMISTRY_DIFFICULTY,
        }
        framework = "朱老师初中框架"

    hint = tables.get(kind, _GENERIC_DIFFICULTY).get(d, _GENERIC_DIFFICULTY[d])
    grade_note = ""
    if grade_range.strip():
        grade_note = (
            f"难度标准参照{framework}，但出题与解析须严格匹配年级范围「{grade_range.strip()}」，不超纲。"
        )
    else:
        grade_note = f"难度标准参照{framework}，出题须匹配给定年级范围，不超纲。"
    return f"{hint}{grade_note}"


def _answer_outline_template() -> str:
    return (
        "【朱老师解析格式】每题 answer_outline 须写完整三段（用小标题，约 800–1500 汉字）："
        "①【思路】点明考查核心、解题入口与关键转化；"
        "②【解答】分步推导；单选/多选**必须**逐选项分析（A/B/C/D 各写对错及理由）；填空/简答/判断写完整计算或判定链；"
        "③【相关知识点】条目化归纳（含易错提醒、与教材衔接）。"
        "先在心中按上述结构推理，再全部写入 answer_outline 字符串；公式用 LaTeX $...$。"
        "禁止只写结论或一句带过；禁止省略选项分析。"
    )


def _few_shot_excerpt(subject: str, difficulty: str) -> str:
    kind = _detect_subject(subject)
    d = _normalize_difficulty(difficulty)
    bucket = _FEW_SHOT.get(kind) or _FEW_SHOT["generic"]
    return bucket.get(d, _FEW_SHOT["generic"][d])


def practice_style_prompt_block(
    subject: str,
    difficulty: str,
    *,
    grade_range: str = "",
) -> str:
    """组装注入 generate_practice_set 的风格段落。"""
    return (
        _subject_difficulty_hints(subject, difficulty, grade_range=grade_range)
        + _answer_outline_template()
        + _few_shot_excerpt(subject, difficulty)
    )


def chunk_size_for_practice_batch(total: int) -> int | None:
    """完整解析模式下减小 batch，降低 JSON 截断风险。"""
    if total >= 6:
        return 3
    return None

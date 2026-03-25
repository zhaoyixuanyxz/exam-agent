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
"""


def generate_practice_set(
    knowledge_point_name: str,
    knowledge_point_summary: str,
    subject: str,
    grade_range: str,
    n: int = 10,
) -> PracticeSet:
    _practice_max_tokens = settings.effective_practice_max_output_tokens

    brief = (
        "为防输出截断：每题 stem 控制在约 400 汉字内，answer_outline 约 500 汉字内；"
        "解题步骤精炼，禁止在 JSON 字符串里再嵌套第二段 JSON 或 ``` 代码块。"
        "公式若在 $...$ 内写 LaTeX，JSON 字符串里每个反斜杠须双写（例：\\\\frac{a}{b}、\\\\angle ABC）。"
        "角度须写 $90^\\\\circ$ 或 $90^{\\\\circ}$，禁止写 ^\\\\wedge\\\\circ；分式与根式须写完整如 $\\\\frac{\\\\sqrt{2}}{2}$，勿输出裸 frac 与空根号。"
    )

    def _one_batch(n_use: int, attempt: int, order_hint: str = "") -> PracticeSet:
        sys = (
            f"你是资深命题教师。请为考点「{knowledge_point_name}」设计恰好 {n_use} 道练习题。"
            f"题型只能使用：{_PRACTICE_QTYPES_LINE}"
            "整套题中须覆盖多种题型（不必五种俱全、数量不必均等）。"
            "单选题为单项正确答案；多选题 qtype 须为「多选」且 options 给出多个备选项；判断题用对错或正确/错误类表述。"
            "单选、多选题：备选项**只能**写在 options 数组中；stem 只写提问与已知条件，**切勿**在 stem 末尾再写 A. B. C. D. 行（否则会与 options 重复排版）。"
            "题目要有区分度；answer_outline 写清晰解题要点即可，勿写冗长推演。公式用 LaTeX $...$。"
            f"{brief}\n{_JSON_ONLY}\n{_PRACTICE_SCHEMA}"
        )
        human = (
            f"科目：{subject}；年级范围：{grade_range}\n"
            f"考点概述：{knowledge_point_summary[:2000]}\n"
            f"请输出符合字段的 JSON，questions 数组长度恰好 {n_use}。"
            + order_hint
        )
        if attempt > 0:
            human += (
                "\n（上一轮未通过校验：务必将 order_index 写成纯数字；"
                "options 一律为 JSON 数组如 [\"A\",\"B\"]；不要省略 stem；"
                "LaTeX 命令在 JSON 字符串内须双反斜杠。）"
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
    # 重试时会降为 n-2、n-4 题，或模型 JSON 截断导致题数不足；先整批补缺，再逐题补缺，尽量避免静默占位。
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
    # 仍缺则按单题多次请求（小输出不易截断）
    fill_attempts = 0
    while len(qs) < n and fill_attempts < 15:
        fill_attempts += 1
        idx = len(qs) + 1
        try:
            hint_1 = (
                f"仅生成第 {idx} 题一道题：JSON 里 questions 长度必须为 1，"
                f"order_index={idx}，与同一考点、难度与卷内已有题相当，避免重复题干。"
            )
            one = _one_batch(1, 0, order_hint=hint_1)
            if one.questions:
                qs.append(one.questions[0])
            else:
                break
        except ValueError:
            break
    while len(qs) < n:
        qs.append(
            PracticeQuestion(
                order_index=len(qs) + 1,
                qtype="填空",
                stem="请根据上述考点完成下列填空（占位题，可替换）。",
                options=[],
                answer_outline="根据定义与定理逐步推导即可。",
            )
        )
    ps.questions = qs[:n]
    for i, q in enumerate(ps.questions, start=1):
        q.order_index = i
    return clamp_practice_set(ps)

from app.models.schemas import KnowledgeAnalysisResult


def _esc_cell(s: str) -> str:
    return (s or "—").replace("|", "｜").replace("\n", " ")


def build_knowledge_markdown(ka: KnowledgeAnalysisResult, alignment: dict) -> str:
    """面向用户的中文考点说明，避免英文 key 与机器感排版。"""
    g1 = alignment.get("grade_min", "")
    g2 = alignment.get("grade_max", "")
    sub = alignment.get("subject", "")
    title = f"{g1}～{g2} · {sub} · 试卷考点分析"
    lines = [
        f"# {title}",
        "",
        f"**主题概述：** {ka.theme_title}",
        "",
        "> 说明：下表中的「教材章节」为结合通用教学体系的推断，仅供参考。",
        "",
        "## 一、考点一览",
        "",
        "| 序号 | 考点名称 | 要点摘要 | 教材章节参考 |",
        "| --- | --- | --- | --- |",
    ]
    for i, kp in enumerate(ka.knowledge_points, 1):
        hint = _esc_cell(kp.book_chapter_hint or "—")
        summary = _esc_cell(kp.summary)
        name = _esc_cell(kp.name)
        lines.append(f"| {i} | {name} | {summary} | {hint} |")

    key_to_name = {x.key: x.name for x in ka.knowledge_points}
    lines.extend(
        [
            "",
            "## 二、每道题对应的考点",
            "",
            "| 题号 | 对应考点 |",
            "| --- | --- |",
        ]
    )
    for m in sorted(ka.mappings, key=lambda x: x.question_order):
        nm = _esc_cell(key_to_name.get(m.knowledge_point_key, m.knowledge_point_key))
        lines.append(f"| 第 {m.question_order} 题 | {nm} |")

    lines.extend(
        [
            "",
            "---",
            "*本说明由试卷助手自动生成，便于复习与查漏补缺。*",
            "",
        ]
    )
    return "\n".join(lines)

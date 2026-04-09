"""LangChain tools — 内部使用同步 DB 会话。"""

from __future__ import annotations

import json

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Artifact, ExamPaper
from app.db.sync_session import sync_session
from app.models.schemas import KnowledgeAnalysisResult, KnowledgePointItem, StructuredPaper
from app.services.export_markdown import build_knowledge_markdown
from app.services.llm_errors import humanize_known_llm_message, tool_error_user_text
from app.services.paper_ai import analyze_knowledge, generate_practice_set, structure_paper_text
from app.services.pdf_render import render_answer_pdf, render_practice_pdf
from app.services.practice_figure_diagnostics import (
    FigureEmbedRecord,
    write_figure_embed_records_json,
)
from app.services.practice_paper_figures import collect_order_index_to_image_paths
from app.services.storage import export_dir_for_conversation


def _get_paper(session: Session, paper_id: str) -> ExamPaper | None:
    return session.get(ExamPaper, paper_id)


def _normalize_kp_query(raw: str) -> str:
    s = (raw or "").strip().strip('"').strip("'").strip("`")
    if "```" in s:
        s = s.replace("```json", "").replace("```", "").strip()
    return s.strip()


def _resolve_knowledge_point(
    ka: KnowledgeAnalysisResult, raw: str
) -> KnowledgePointItem | None:
    q = _normalize_kp_query(raw)
    if not q:
        return None
    for kp in ka.knowledge_points:
        if kp.key == q:
            return kp
    qn = q.lower().replace(" ", "_")
    for kp in ka.knowledge_points:
        if kp.key.lower() == qn:
            return kp
    for kp in ka.knowledge_points:
        if q == kp.name or q in kp.name or kp.name in q:
            return kp
    return None


@tool
def structure_exam_paper(paper_id: str) -> str:
    """【必选第一步】将数据库中该试卷的 raw_text 解析为结构化题目（选择/填空等）。
    参数 paper_id 必须与用户消息【系统上下文】中的 paper_id 完全一致。
    分析考点、对齐题型前必须先调用；失败时用简短中文说明原因，勿谎称工具不可用。"""
    with sync_session() as session:
        p = _get_paper(session, paper_id)
        if not p or not p.raw_text:
            return "错误：找不到试卷或尚未提取文本，请先上传 PDF/Word 或粘贴内容。"
        try:
            sp = structure_paper_text(p.raw_text)
        except Exception as e:
            detail = str(e)
            friendly = humanize_known_llm_message(detail)
            if friendly:
                return friendly
            return tool_error_user_text("拆题失败：", e)
        p.parsed_json = sp.model_dump()
        session.add(p)
        session.commit()
        n = sum(len(sec.questions) for sec in sp.sections)
        return f"成功：{len(sp.sections)} 个部分，{n} 道题。"


@tool
def save_alignment_metadata(
    paper_id: str,
    grade_min: str,
    grade_max: str,
    subject: str,
    type_counts_json: str,
) -> str:
    """保存年级区间、科目、题型数量。type_counts_json 如 {"选择题":3,"填空题":2}。"""
    with sync_session() as session:
        p = _get_paper(session, paper_id)
        if not p:
            return "错误：找不到试卷。"
        try:
            counts = json.loads(type_counts_json)
        except json.JSONDecodeError:
            return "错误：题型数量格式不对，请重试。"
        p.alignment_json = {
            "grade_min": grade_min,
            "grade_max": grade_max,
            "subject": subject,
            "type_counts": counts,
        }
        session.add(p)
        session.commit()
        return "成功：对齐信息已保存。"


@tool
def run_knowledge_analysis(paper_id: str) -> str:
    """结合结构化试卷与对齐标签，生成考点归类与 Markdown 文件路径。"""
    with sync_session() as session:
        p = _get_paper(session, paper_id)
        if not p or not p.parsed_json:
            return "请先 structure_exam_paper。"
        if not p.alignment_json:
            return "请先 save_alignment_metadata。"
        sp = StructuredPaper.model_validate(p.parsed_json)
        lines: list[str] = []
        for sec in sp.sections:
            lines.append(sec.title or "部分")
            for q in sec.questions:
                opt = " ".join(q.options) if q.options else ""
                lines.append(f"第{q.order_index}题({q.qtype})：{q.stem} {opt}")
        summary = "\n".join(lines)[:50_000]
        try:
            ka = analyze_knowledge(summary, p.alignment_json)
        except Exception as e:
            return tool_error_user_text("考点分析失败：", e)
        p.knowledge_analysis_json = ka.model_dump()
        conv_id = p.conversation_id
        md_path = export_dir_for_conversation(conv_id) / "考点说明.md"
        md_path.write_text(
            build_knowledge_markdown(ka, p.alignment_json),
            encoding="utf-8",
        )
        p.knowledge_markdown_path = md_path.as_posix()
        session.add(p)
        session.commit()
        return "成功：考点分析完成，说明文档已生成。"


@tool
def generate_chunk_practice_pdf(
    paper_id: str,
    knowledge_point_key: str,
    question_count: int = 10,
    use_original_figures: bool = False,
    include_figures: bool = True,
) -> str:
    """生成分块练习 PDF 与参考答案 PDF（默认 10 题；question_count 为正整数，题量多时会自动分批出题）。
    knowledge_point_key 可为分析结果里的英文 key，或与列表一致的考点中文名称。
    use_original_figures：为 true 时在提示中附带原卷附图索引，并在 PDF 中尝试嵌入（须结构化试卷含 image_ref）。
    include_figures：为 false 时不插入任何配图（仅文本）。"""
    with sync_session() as session:
        p = _get_paper(session, paper_id)
        if not p or not p.knowledge_analysis_json:
            return "请先完成考点分析。"
        ka = KnowledgeAnalysisResult.model_validate(p.knowledge_analysis_json)
        kp = _resolve_knowledge_point(ka, knowledge_point_key)
        if not kp:
            names = "、".join(x.name for x in ka.knowledge_points)
            return f"未匹配到考点。请从下列考点中选一个再试：{names}"
        align = p.alignment_json or {}
        grade = f"{align.get('grade_min', '?')}—{align.get('grade_max', '?')}"
        subject = str(align.get("subject", "数学"))
        n = max(1, int(question_count))
        order_map: dict[int, list[str]] = {}
        original_figure_hint: str | None = None
        if p.parsed_json:
            sp = StructuredPaper.model_validate(p.parsed_json)
            order_map = collect_order_index_to_image_paths(sp)
            if order_map:
                original_figure_hint = "\n".join(
                    f"  第{k}题: " + "；".join(paths[:12])
                    for k, paths in sorted(order_map.items())
                )
        try:
            practice = generate_practice_set(
                kp.name,
                kp.summary,
                subject,
                grade,
                n=n,
                use_original_figures=use_original_figures,
                include_figures=include_figures,
                original_figure_hint=original_figure_hint,
            )
            practice.knowledge_point_key = kp.key
            practice.knowledge_point_name = kp.name
        except Exception as e:
            return tool_error_user_text("出题失败：", e)
        out_dir = export_dir_for_conversation(p.conversation_id)
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in kp.key)[:80]
        q_path = out_dir / f"practice_{safe}.pdf"
        a_path = out_dir / f"practice_{safe}_answers.pdf"
        title = f"{align.get('grade_min', '')} {subject} · {kp.name} · 分块练习"
        diag_practice: list[FigureEmbedRecord] = []
        diag_answers: list[FigureEmbedRecord] = []
        write_diag = bool(settings.practice_pdf_write_figure_diagnostics)
        try:
            render_practice_pdf(
                practice,
                q_path,
                title=title,
                include_answers=False,
                include_figures=include_figures,
                use_original_figures=use_original_figures,
                order_index_to_paper_paths=order_map if use_original_figures else None,
                collect_figure_diagnostics=diag_practice if write_diag else None,
            )
            render_answer_pdf(
                practice,
                a_path,
                title=title,
                include_figures=include_figures,
                use_original_figures=use_original_figures,
                order_index_to_paper_paths=order_map if use_original_figures else None,
                collect_figure_diagnostics=diag_answers if write_diag else None,
            )
            if write_diag:
                write_figure_embed_records_json(
                    out_dir / f"practice_{safe}_figure_diag_practice.json",
                    diag_practice,
                )
                write_figure_embed_records_json(
                    out_dir / f"practice_{safe}_figure_diag_answers.json",
                    diag_answers,
                )
        except Exception as e:
            return f"PDF 渲染失败（检查楷体字体配置）：{e!s}"
        for kind, path in (
            ("pdf_question", q_path),
            ("pdf_answer", a_path),
        ):
            session.add(
                Artifact(
                    paper_id=paper_id,
                    kind=kind,
                    path=path.as_posix(),
                    knowledge_point_key=kp.key,
                )
            )
        session.commit()
        return "成功：练习卷与参考答案已生成。"


AGENT_TOOLS = [
    structure_exam_paper,
    save_alignment_metadata,
    run_knowledge_analysis,
    generate_chunk_practice_pdf,
]

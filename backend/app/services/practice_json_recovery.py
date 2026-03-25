"""当模型把 PracticeSet JSON 写进回复而未调用工具时，解析并生成 PDF 落库。"""

from __future__ import annotations

from pydantic import ValidationError

from app.db.models import Artifact, ExamPaper
from app.db.sync_session import sync_session
from app.models.schemas import PracticeSet
from app.services.json_from_llm import iter_candidate_dicts_from_llm
from app.services.practice_parse import repair_practice_dict
from app.services.pdf_render import render_answer_pdf, render_practice_pdf
from app.services.practice_clamp import clamp_practice_set
from app.services.storage import export_dir_for_conversation

_CORRUPT_MARKERS = (
    "出题失败",
    "技术说明",
    "Expecting",
    "```json",
    "Unterminated",
    "delimiter",
    "抱歉，系统",
)


def _corrupt_field(s: str | None) -> bool:
    if not s:
        return False
    return any(m in s for m in _CORRUPT_MARKERS)


def _score_practice_dict(d: dict) -> int:
    try:
        p = PracticeSet.model_validate(repair_practice_dict(d))
    except ValidationError:
        return -10**9
    if not p.questions:
        return -10**9
    score = len(p.questions) * 1000
    for q in p.questions:
        if _corrupt_field(q.stem) or _corrupt_field(q.answer_outline):
            return -10**9
        score -= len(q.stem) // 400
        score -= len(q.answer_outline) // 400
    return score


def pick_best_practice_set_dict(text: str) -> dict | None:
    """从杂乱回复中挑出最像一份完整练习卷的 JSON（多段 ```json```、多段 `{` 对象）。"""
    cands: list[dict] = []
    for d in iter_candidate_dicts_from_llm(text):
        if not isinstance(d, dict) or "questions" not in d:
            continue
        r = repair_practice_dict(d)
        try:
            PracticeSet.model_validate(r)
        except ValidationError:
            continue
        cands.append(r)
    if not cands:
        return None
    viable = [c for c in cands if _score_practice_dict(c) > -10**8]
    if not viable:
        return None
    return max(viable, key=_score_practice_dict)


def try_recover_practice_pdf_from_assistant_text(text: str, paper_id: str | None) -> tuple[str, bool]:
    """
    若正文内含可解析的 PracticeSet JSON，则渲染 PDF、写入 Artifact。
    成功时整段助手正文替换为简短说明（原消息常夹杂多段损坏 JSON，不宜保留）。
    """
    if not paper_id or not (text or "").strip():
        return text, False

    picked = pick_best_practice_set_dict(text)
    if not picked:
        return text, False

    try:
        practice = PracticeSet.model_validate(picked)
    except ValidationError:
        return text, False

    practice = clamp_practice_set(practice)
    if not practice.questions:
        return text, False

    with sync_session() as session:
        p = session.get(ExamPaper, paper_id)
        if not p:
            return text, False

        out_dir = export_dir_for_conversation(p.conversation_id)
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in practice.knowledge_point_key)[:80]
        q_path = out_dir / f"practice_{safe}.pdf"
        a_path = out_dir / f"practice_{safe}_answers.pdf"
        align = p.alignment_json or {}
        subj = str(align.get("subject", "数学"))
        gm = align.get("grade_min", "")
        title = f"{gm} {subj} · {practice.knowledge_point_name} · 分块练习"

        try:
            render_practice_pdf(practice, q_path, title=title, include_answers=False)
            render_answer_pdf(practice, a_path, title=title)
        except Exception:
            return text, False

        for kind, path in (("pdf_question", q_path), ("pdf_answer", a_path)):
            session.add(
                Artifact(
                    paper_id=paper_id,
                    kind=kind,
                    path=path.as_posix(),
                    knowledge_point_key=practice.knowledge_point_key,
                )
            )
        session.commit()

    n = len(practice.questions)
    replacement = (
        f"已为你生成「{practice.knowledge_point_name}」专项练习（共 {n} 题，"
        f"含习题卷与参考答案）。\n请在下方「生成文件」中点击下载。"
    )
    return replacement, True

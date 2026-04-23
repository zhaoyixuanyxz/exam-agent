"""基于 ExamPaper 与产物推导五步主流程状态（V2.0）。"""

from __future__ import annotations

from typing import Any, Literal

from app.db.models import ExamPaper

StepState = Literal["not_started", "in_progress", "pending_confirm", "completed", "failed"]


def _norm_status(p: ExamPaper) -> str:
    s = getattr(p, "structured_confirm_status", None) or "none"
    if s in ("", "None"):
        return "none"
    return s


def _effective_status(p: ExamPaper) -> str:
    """旧数据若已有 parsed_json 但状态仍为 none，视为待确认。"""
    st = _norm_status(p)
    if _has_parsed(p) and st == "none":
        return "pending"
    return st


def _has_parsed(p: ExamPaper) -> bool:
    return bool(p.parsed_json)


def _has_knowledge(p: ExamPaper) -> bool:
    return bool(p.knowledge_analysis_json)


def _has_practice_pdf(p: ExamPaper) -> bool:
    for a in p.artifacts or []:
        if a.kind in ("pdf_question", "pdf_answer"):
            return True
    return False


def _can_download(p: ExamPaper) -> bool:
    if p.knowledge_markdown_path or _has_practice_pdf(p):
        return True
    return False


def _step2_state(p: ExamPaper, agent_run_active: bool) -> StepState:
    st = _effective_status(p)
    if not _has_parsed(p):
        return "in_progress" if agent_run_active else "not_started"
    if st == "confirmed":
        return "completed"
    return "pending_confirm"


def _step3_state(p: ExamPaper, agent_run_active: bool) -> StepState:
    st = _effective_status(p)
    if st != "confirmed":
        return "not_started"
    if not _has_knowledge(p):
        return "in_progress" if agent_run_active else "not_started"
    return "completed"


def _step4_state(p: ExamPaper, agent_run_active: bool) -> StepState:
    st = _effective_status(p)
    if st != "confirmed":
        return "not_started"
    if not _has_knowledge(p):
        return "not_started"
    if not _has_practice_pdf(p):
        return "in_progress" if agent_run_active else "not_started"
    return "completed"


def _step5_state(p: ExamPaper) -> StepState:
    st = _effective_status(p)
    if st != "confirmed":
        return "not_started"
    if not _can_download(p):
        return "not_started"
    return "completed"


def _step1_state(p: ExamPaper) -> StepState:
    if p.raw_text or p.raw_path:
        return "completed"
    return "not_started"


def effective_structured_status(p: ExamPaper) -> str:
    """供 API 返回：与步骤推导一致的状态字符串。"""
    return _effective_status(p)


def infer_failed_step_key_from_error_text(text: str | None) -> str | None:
    """从助手/请求错误正文中推测失败步骤（与 BKL-016 重试一致）。"""
    if not text:
        return None
    s = str(text)
    if "（处理出错" not in s and "处理出错" not in s and "请求失败" not in s and "Error" not in s:
        return None
    low = s.lower()
    if "文件超过" in s or "413" in s or "解析失败" in s[:30]:
        return "upload"
    if "拆题" in s or "structure_exam" in low or ("结构化" in s and "失败" in s):
        return "structure"
    if "先确认" in s and "结构化" in s:
        return "structure"
    if "考点" in s or "knowledge" in low or "考点分析" in s or "分析失败" in s:
        return "analyze"
    if (
        "出题" in s
        or (("练习" in s) and ("失败" in s))
        or "pdf" in low
        or "render" in low
        or "练习卷" in s
    ):
        return "generate"
    if "网络" in s and "失败" in s:
        return None
    return "structure"


def _apply_failed_step_overlay(
    steps: list[dict[str, str]], failed_key: str | None, agent_run_active: bool
) -> None:
    """若存在最近一次运行失败提示，将对应非完成步骤标为 failed（助手不在跑时）。"""
    if not failed_key or agent_run_active:
        return
    for st in steps:
        if st.get("key") == failed_key and st.get("state") not in ("completed",):
            st["state"] = "failed"


def build_workflow_payload(
    p: ExamPaper,
    *,
    agent_run_active: bool,
    conversation_id: str,
    last_failed_step: str | None = None,
) -> dict[str, Any]:
    if p.conversation_id != conversation_id:
        raise ValueError("paper does not belong to conversation")

    steps: list[dict[str, str]] = [
        {"key": "upload", "name": "上传材料", "state": _step1_state(p)},
        {
            "key": "structure",
            "name": "结构化试卷",
            "state": _step2_state(p, agent_run_active),
        },
        {
            "key": "analyze",
            "name": "分析考点",
            "state": _step3_state(p, agent_run_active),
        },
        {
            "key": "generate",
            "name": "生成练习",
            "state": _step4_state(p, agent_run_active),
        },
        {
            "key": "download",
            "name": "下载产物",
            "state": _step5_state(p),
        },
    ]
    _apply_failed_step_overlay(steps, last_failed_step, agent_run_active)
    return {
        "conversation_id": conversation_id,
        "paper_id": p.id,
        "agent_run_active": agent_run_active,
        "last_failed_step": last_failed_step,
        "steps": steps,
    }

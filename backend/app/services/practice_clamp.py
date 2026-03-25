"""练习集字段过长时截断，避免 JSON 损坏与 PDF 渲染异常。"""

from __future__ import annotations

from app.models.schemas import PracticeSet

_MAX_STEM = 4000
_MAX_OUTLINE = 6000
_MAX_OPTION_LEN = 800


def clamp_practice_set(ps: PracticeSet) -> PracticeSet:
    for q in ps.questions:
        if len(q.stem) > _MAX_STEM:
            q.stem = q.stem[:_MAX_STEM] + "…（题干过长已截断）"
        if len(q.answer_outline) > _MAX_OUTLINE:
            q.answer_outline = q.answer_outline[:_MAX_OUTLINE] + "…（解析过长已截断）"
        if q.options:
            q.options = [
                (o[:_MAX_OPTION_LEN] + "…") if len(o) > _MAX_OPTION_LEN else o for o in q.options
            ]
    return ps

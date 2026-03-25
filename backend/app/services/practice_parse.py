"""将模型返回的松散 JSON 规整为可校验的 PracticeSet 结构。"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.models.schemas import PRACTICE_QTYPE_VALUES, PracticeSet
from app.services.json_from_llm import iter_candidate_dicts_from_llm


def normalize_practice_qtype(raw: str) -> str:
    """将模型返回的题型别名统一为五种标准名之一。"""
    t = (raw or "").strip()
    if t in PRACTICE_QTYPE_VALUES:
        return t
    if "多选" in t or "多项" in t:
        return "多选"
    if "判断" in t:
        return "判断"
    if "填空" in t or t in ("填",):
        return "填空"
    if any(x in t for x in ("简答", "主观", "解答", "计算", "证明", "问答", "应用", "综合", "论述")):
        return "简答"
    if "选择" in t or t in ("选",):
        return "单选"
    return "简答"


def repair_practice_dict(data: dict[str, Any]) -> dict[str, Any]:
    """修正常见类型错误：order_index 为字符串、options 为 null/单字符串等。"""
    out = dict(data)
    for k in ("knowledge_point_key", "knowledge_point_name"):
        v = out.get(k)
        if v is None:
            out[k] = ""
        else:
            out[k] = str(v).strip()

    qs = out.get("questions")
    if not isinstance(qs, list):
        out["questions"] = []
        return out

    fixed: list[dict[str, Any]] = []
    for i, raw in enumerate(qs):
        if not isinstance(raw, dict):
            continue
        q = dict(raw)
        oi = q.get("order_index", i + 1)
        if isinstance(oi, str):
            oi = oi.strip()
            try:
                oi = int(oi)
            except ValueError:
                oi = i + 1
        elif not isinstance(oi, int):
            try:
                oi = int(oi)
            except (TypeError, ValueError):
                oi = i + 1
        q["order_index"] = oi

        qt = q.get("qtype")
        q["qtype"] = normalize_practice_qtype(str(qt) if qt is not None else "填空")

        for sk in ("stem", "answer_outline"):
            v = q.get(sk)
            q[sk] = str(v) if v is not None else ""

        if not str(q.get("stem", "")).strip():
            q["stem"] = "（题干暂缺，请重新生成本题。）"

        opt = q.get("options")
        if opt is None:
            q["options"] = []
        elif isinstance(opt, str):
            q["options"] = [opt] if opt.strip() else []
        elif isinstance(opt, list):
            q["options"] = [str(x) for x in opt if x is not None and str(x).strip() != ""]
        else:
            q["options"] = []

        fixed.append(q)

    out["questions"] = fixed
    return out


def parse_practice_set_from_llm_text(text: str) -> PracticeSet:
    """扫描多段 JSON 候选，先 repair 再校验 PracticeSet。"""
    last_err: ValidationError | None = None
    for d in iter_candidate_dicts_from_llm(text):
        if not isinstance(d, dict) or "questions" not in d:
            continue
        try:
            return PracticeSet.model_validate(repair_practice_dict(d))
        except ValidationError as e:
            last_err = e
            continue
    if last_err is None:
        raise ValueError("未在模型输出中找到可识别的练习题 JSON。")
    n = last_err.error_count()
    raise ValueError(
        f"练习题 JSON 校验未通过（共 {n} 处字段问题）。"
        "常见原因：缺少 knowledge_point_key / questions、某题缺少题干 stem。"
    ) from last_err

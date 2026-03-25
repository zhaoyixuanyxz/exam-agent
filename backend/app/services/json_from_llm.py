"""Parse JSON from LLM text (DeepSeek may not support LangChain json_schema mode)."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# 模型常在 JSON 字符串里写 LaTeX 单反斜杠（如 \frac），会破坏 JSON；按长度降序优先匹配长命令。
_LATEX_CMD_PREFIXES: tuple[str, ...] = tuple(
    sorted(
        {
            r"\Rightarrow",
            r"\rightarrow",
            r"\overrightarrow",
            r"\overline",
            r"\operatorname",
            r"\mathrm",
            r"\mathbb",
            r"\mathbf",
            r"\mathcal",
            r"\parallel",
            r"\perp",
            r"\cdots",
            r"\ldots",
            r"\triangle",
            r"\approx",
            r"\infty",
            r"\sqrt",
            r"\widehat",
            r"\degree",
            r"\theta",
            r"\alpha",
            r"\beta",
            r"\gamma",
            r"\delta",
            r"\Delta",
            r"\frac",
            r"\leq",
            r"\geq",
            r"\neq",
            r"\text",
            r"\cdot",
            r"\times",
            r"\div",
            r"\circ",
            r"\odot",
            r"\sum",
            r"\int",
            r"\quad",
            r"\qquad",
            r"\sin",
            r"\cos",
            r"\tan",
            r"\cot",
            r"\log",
            r"\ln",
            r"\because",
            r"\therefore",
            r"\nabla",
            r"\vec",
            r"\prime",
            r"\left",
            r"\right",
            r"\pm",
            r"\pi",
            r"\mu",
            r"\sigma",
            r"\omega",
            r"\underbrace",
            r"\overbrace",
            r"\vert",
            r"\Vert",
            r"\subseteq",
            r"\supseteq",
            r"\subset",
            r"\supset",
            r"\emptyset",
            r"\partial",
            r"\ell",
            r"\wp",
            r"\notin",
            r"\angle",
            r"\hline",
            r"\cap",
            r"\cup",
            r"\in",
        },
        key=len,
        reverse=True,
    )
)


def repair_json_latex_escapes_in_strings(s: str) -> str:
    """在 JSON 文本的字符串字面量内，为单反斜杠 LaTeX 命令补成合法 JSON（双反斜杠）。"""
    out: list[str] = []
    i = 0
    n = len(s)
    in_string = False
    while i < n:
        c = s[i]
        if not in_string:
            if c == '"':
                in_string = True
            out.append(c)
            i += 1
            continue
        if c == '"':
            bs = 0
            for j in range(len(out) - 1, -1, -1):
                if out[j] != "\\":
                    break
                bs += 1
            if bs % 2 == 0:
                in_string = False
            out.append(c)
            i += 1
            continue
        if c == "\\":
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt == "\\":
                out.append("\\\\")
                i += 2
                continue
            matched = False
            for pref in _LATEX_CMD_PREFIXES:
                if s.startswith(pref, i):
                    out.append("\\")
                    out.append(pref)
                    i += len(pref)
                    matched = True
                    break
            if matched:
                continue
            if nxt == "u" and i + 6 <= n:
                hx = s[i + 2 : i + 6]
                if len(hx) == 4 and all(x in "0123456789aAbBcCdDeEfF" for x in hx):
                    out.append(s[i : i + 6])
                    i += 6
                    continue
            if nxt in "\"\\/bfnrt":
                out.append("\\")
                out.append(nxt)
                i += 2
                continue
            if nxt and nxt.isalpha():
                out.append("\\\\")
                i += 1
                continue
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _fenced_json_innards(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)]


def iter_decode_root_dicts(segment: str) -> list[dict]:
    """自左向右扫描，用 raw_decode 取出每一段里所有顶层 JSON 对象（避免 first{…last} 截断字符串内的 }）。"""
    out: list[dict] = []
    i = 0
    n = len(segment)
    while i < n:
        j = segment.find("{", i)
        if j == -1:
            break
        try:
            obj, end = json.JSONDecoder().raw_decode(segment, j)
        except json.JSONDecodeError:
            i = j + 1
            continue
        if isinstance(obj, dict):
            out.append(obj)
        i = end
    return out


def iter_candidate_dicts_from_llm(text: str):
    """优先解析 fenced ```json``` 块，再扫全文；同内容去重。"""
    seen: set[str] = set()

    def _emit_dicts(segment: str):
        for d in iter_decode_root_dicts(segment):
            key = json.dumps(d, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            yield d
        repaired = repair_json_latex_escapes_in_strings(segment)
        if repaired != segment:
            for d in iter_decode_root_dicts(repaired):
                key = json.dumps(d, sort_keys=True, ensure_ascii=False)
                if key in seen:
                    continue
                seen.add(key)
                yield d

    for inner in _fenced_json_innards(text):
        yield from _emit_dicts(inner)
    yield from _emit_dicts(text)


def extract_json_object(text: str) -> dict:
    for d in iter_candidate_dicts_from_llm(text):
        return d
    raise ValueError("模型未返回可解析的 JSON 对象")


def parse_pydantic_from_llm_text(text: str, model: type[T]) -> T:
    last_err: ValidationError | None = None
    for d in iter_candidate_dicts_from_llm(text):
        try:
            return model.model_validate(d)
        except ValidationError as e:
            last_err = e
            continue
    msg = f"无法将模型输出解析为 {model.__name__}"
    if last_err is not None:
        msg += f": {last_err.error_count()} 个字段错误"
    raise ValueError(msg) from last_err

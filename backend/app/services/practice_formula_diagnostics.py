"""练习 PDF 正文公式渲染：可检索记录与可选 JSON 导出。"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FormulaRenderRecord:
    order_index: int | None
    section: str
    outcome: str
    reason_code: str
    renderer: str
    inner_len: int
    cache_hit: bool
    duration_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def log_formula_render(
    log: logging.Logger,
    *,
    order_index: int | None,
    section: str,
    outcome: str,
    reason_code: str,
    renderer: str,
    inner_len: int,
    cache_hit: bool,
    duration_ms: float | None,
) -> None:
    log.info(
        "practice_formula_render order_index=%s section=%s outcome=%s reason_code=%s "
        "renderer=%s inner_len=%s cache_hit=%s duration_ms=%s",
        order_index,
        section,
        outcome,
        reason_code,
        renderer,
        inner_len,
        cache_hit,
        duration_ms,
    )


def append_formula_render_record(
    sink: list[FormulaRenderRecord] | None,
    *,
    order_index: int | None,
    section: str,
    outcome: str,
    reason_code: str,
    renderer: str,
    inner_len: int,
    cache_hit: bool,
    duration_ms: float | None,
) -> None:
    if sink is None:
        return
    sink.append(
        FormulaRenderRecord(
            order_index=order_index,
            section=section,
            outcome=outcome,
            reason_code=reason_code,
            renderer=renderer,
            inner_len=inner_len,
            cache_hit=cache_hit,
            duration_ms=duration_ms,
        )
    )


def write_formula_render_records_json(path: Path, records: list[FormulaRenderRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

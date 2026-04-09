"""分块练习 PDF 配图嵌入：可检索的结果码与日志辅助（Phase 9 可观测性）。"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FigureEmbedRecord:
    """单次「每题配图」结论，供可选收集或外部工具消费。"""

    order_index: int
    figure_kind: str
    outcome: str
    reason_code: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def log_figure_embed(
    log: logging.Logger,
    *,
    order_index: int,
    figure_kind: str,
    outcome: str,
    reason_code: str,
) -> None:
    """每题一行 INFO：固定键名顺序，便于 grep / 日志管道解析。"""
    log.info(
        "practice_figure_embed order_index=%s figure_kind=%s outcome=%s reason_code=%s",
        order_index,
        figure_kind,
        outcome,
        reason_code,
    )


def append_figure_embed_record(
    sink: list[FigureEmbedRecord] | None,
    *,
    order_index: int,
    figure_kind: str,
    outcome: str,
    reason_code: str,
) -> None:
    if sink is None:
        return
    sink.append(
        FigureEmbedRecord(
            order_index=order_index,
            figure_kind=figure_kind,
            outcome=outcome,
            reason_code=reason_code,
        )
    )


def write_figure_embed_records_json(path: Path, records: list[FigureEmbedRecord]) -> None:
    """将配图嵌入记录写入 JSON（UTF-8），便于对照哪题未出图。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.to_dict() for r in records]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

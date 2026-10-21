"""Decide which practice papers to skip, redo, or store."""

from __future__ import annotations

_FIGURE_MARKERS = ("几何", "函数图像", "函数图象", "电路", "化学装置")


def needs_figure(point_name: str, stems: list[str]) -> bool:
    blob = f"{point_name}\n" + "\n".join(stems)
    return any(marker in blob for marker in _FIGURE_MARKERS)

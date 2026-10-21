"""Decide which practice papers to skip, redo, or store."""

from __future__ import annotations

_FIGURE_MARKERS = ("几何", "函数图像", "函数图象", "电路", "化学装置")


def needs_figure(point_name: str, stems: list[str]) -> bool:
    blob = f"{point_name}\n" + "\n".join(stems)
    return any(marker in blob for marker in _FIGURE_MARKERS)


def _has_text(stems: list[str]) -> bool:
    return any((stem or "").strip() for stem in stems)


def _has_figure(figure_kinds: list[str], uses_paper_figure: list[bool]) -> bool:
    if any(kind and kind != "none" for kind in figure_kinds):
        return True
    return any(uses_paper_figure)


def practice_outcome(
    point_name: str,
    stems: list[str],
    figure_kinds: list[str],
    uses_paper_figure: list[bool],
) -> str:
    has_text = _has_text(stems)
    has_figure = _has_figure(figure_kinds, uses_paper_figure)
    if not has_text and not has_figure:
        return "retry"
    if needs_figure(point_name, stems) and not has_figure:
        return "retry"
    return "store"

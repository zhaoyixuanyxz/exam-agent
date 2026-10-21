"""Decide which practice papers to skip, redo, or store."""

from __future__ import annotations

from collections.abc import Callable

TIMEOUT_MESSAGE = "连接超时建议重试"


class PracticeFillTimeout(Exception):
    """The model call timed out while drafting one practice paper."""

    def __init__(self, stored_keys: list[str]):
        self.stored_keys = list(stored_keys)
        super().__init__(TIMEOUT_MESSAGE)


GenerateOne = Callable[[str, str], tuple[str, str]]


def fill_practice_pdfs(
    points: list[tuple[str, str]],
    stored_keys: list[str],
    generate_one: GenerateOne,
) -> list[str]:
    # Retry until the page is acceptable. There is no attempt cap.
    stored = list(stored_keys)
    stored_set = set(stored)
    while True:
        missing = [item for item in points if item[0] not in stored_set]
        if not missing:
            return [item[0] for item in points]
        key, name = missing[0]
        try:
            action, stored_key = generate_one(key, name)
        except PracticeFillTimeout:
            raise PracticeFillTimeout(stored) from None
        if action == "store":
            stored.append(stored_key)
            stored_set.add(stored_key)


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

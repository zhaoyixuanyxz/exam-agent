"""Decide which practice papers to skip, redo, or store."""

from __future__ import annotations

import re
from collections.abc import Callable

TIMEOUT_MESSAGE = "连接超时建议重试"
MAX_RETRIES_PER_POINT = 3


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
    stored = list(stored_keys)
    stored_set = set(stored)
    abandoned: set[str] = set()
    retries: dict[str, int] = {}
    while True:
        missing = [
            item
            for item in points
            if item[0] not in stored_set and item[0] not in abandoned
        ]
        if not missing:
            return [item[0] for item in points if item[0] in stored_set]
        key, name = missing[0]
        try:
            action, stored_key = generate_one(key, name)
        except PracticeFillTimeout:
            raise PracticeFillTimeout(stored) from None
        if action == "store":
            stored.append(stored_key)
            stored_set.add(stored_key)
            continue
        retries[key] = retries.get(key, 0) + 1
        if retries[key] >= MAX_RETRIES_PER_POINT:
            abandoned.add(key)


_FIGURE_MARKERS = ("几何", "电路", "化学装置")
_FUNCTION_GRAPH_RE = re.compile(r"函数.{0,6}图[象像]")


def needs_figure(point_name: str, stems: list[str]) -> bool:
    blob = f"{point_name}\n" + "\n".join(stems)
    if any(marker in blob for marker in _FIGURE_MARKERS):
        return True
    return bool(_FUNCTION_GRAPH_RE.search(blob))


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
    *,
    include_figures: bool = True,
) -> str:
    has_text = _has_text(stems)
    has_figure = _has_figure(figure_kinds, uses_paper_figure)
    if not has_text and not has_figure:
        return "retry"
    if include_figures and needs_figure(point_name, stems) and not has_figure:
        return "retry"
    return "store"


def generate_one_for_tool(
    key: str,
    name: str,
    *,
    draft,
    store,
    include_figures: bool = True,
) -> tuple[str, str]:
    stems, figure_kinds, uses_paper_figure, payload = draft(key, name)
    action = practice_outcome(
        name,
        stems,
        figure_kinds,
        uses_paper_figure,
        include_figures=include_figures,
    )
    if action == "store":
        store(payload)
    return action, key

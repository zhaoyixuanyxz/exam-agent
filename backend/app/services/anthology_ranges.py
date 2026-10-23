# backend/app/services/anthology_ranges.py
from __future__ import annotations

import re

EMPTY_SUGGEST_MESSAGE = "请按套填写页码"
CONFIRM_BLOCKED_NEEDED = "请先确认合订本分套（或选择按单套继续），再确认结构化。"
CONFIRM_BLOCKED_DONE = "该材料为已切开的合订本原件，请对切开后的各套确认结构化。"

_YEAR_LINE = re.compile(
    r"(?P<year>20[0-9]{2})\s*年?.{0,24}(中考|期末|一模|二模|三模|月考|调研)",
    re.MULTILINE,
)


def _marker_year(text: str) -> str | None:
    m = _YEAR_LINE.search(text or "")
    if m:
        return m.group("year")
    # 弱匹配：页首附近单独年份且含「考」
    m2 = re.search(r"(20[0-9]{2})", text or "")
    if m2 and ("考" in (text or "")[:80] or "中考" in (text or "")):
        return m2.group(1)
    return None


def suggest_ranges_from_page_texts(
    page_texts: list[str],
) -> tuple[list[list[int]], list[str], str]:
    """page_texts 下标 0 = 第 1 页。少于两个年份标记则返回空，禁止均分。"""
    markers: list[tuple[int, str]] = []  # 1-based page, year
    for i, t in enumerate(page_texts):
        y = _marker_year(t or "")
        if y:
            # 同一年连续页只保留首次
            if markers and markers[-1][1] == y and i + 1 == markers[-1][0] + 1:
                continue
            if markers and markers[-1][1] == y:
                continue
            markers.append((i + 1, y))
    # 去重：只保留年份变化的边界页
    boundary: list[tuple[int, str]] = []
    for page, year in markers:
        if not boundary or boundary[-1][1] != year:
            boundary.append((page, year))
    if len(boundary) < 2:
        return [], [], EMPTY_SUGGEST_MESSAGE
    n = len(page_texts)
    ranges: list[list[int]] = []
    labels: list[str] = []
    for idx, (start, year) in enumerate(boundary):
        end = (boundary[idx + 1][0] - 1) if idx + 1 < len(boundary) else n
        if end < start:
            end = start
        ranges.append([start, end])
        labels.append(f"{year}年试卷")
    return ranges, labels, ""


def confirm_blocked_message(status: str | None) -> str | None:
    s = (status or "none").strip() or "none"
    if s == "needed":
        return CONFIRM_BLOCKED_NEEDED
    if s == "done":
        return CONFIRM_BLOCKED_DONE
    return None

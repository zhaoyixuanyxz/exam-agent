"""Decide when a page needs vision and retry that page up to three times."""

from __future__ import annotations

from collections.abc import Callable

MAX_VISION_ATTEMPTS = 3
EMPTY_PAPER_MESSAGE = "这些页无法识别，请换清晰件再交。"
_TRANSIENT_VISION_ERRORS = (TimeoutError, ConnectionError, ConnectionResetError)
_TRANSIENT_VISION_MARKERS = ("timeout", "connection", "reset", "refused")


def _vision_attempt_is_transient(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSIENT_VISION_ERRORS):
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_VISION_MARKERS)


def page_text_is_sparse(text: str) -> bool:
    blob = text or ""
    cjk = sum(1 for ch in blob if "\u4e00" <= ch <= "\u9fff")
    letters = sum(1 for ch in blob if ch.isascii() and ch.isalpha())
    return cjk < 4 and letters < 4


def read_sparse_page(
    read_once: Callable[[], str],
    *,
    max_attempts: int = MAX_VISION_ATTEMPTS,
) -> str | None:
    for _ in range(max_attempts):
        try:
            text = (read_once() or "").strip()
        except Exception as exc:
            if _vision_attempt_is_transient(exc):
                continue
            raise
        if not page_text_is_sparse(text):
            return text
    return None

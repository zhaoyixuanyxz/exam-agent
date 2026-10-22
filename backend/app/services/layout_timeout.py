"""Connection-interrupt copy for practice PDFs and color knowledge layout."""

from __future__ import annotations

from collections.abc import Callable, Sequence

TIMEOUT_MESSAGE = "连接超时建议重试"

_INTERRUPT_MARKERS = (
    "timeout",
    "timed out",
    "connection",
    "connecterror",
    "reset",
    "refused",
)


def is_connection_timeout(exc: BaseException) -> bool:
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(marker in blob for marker in _INTERRUPT_MARKERS)


def user_text_for_layout_timeout(exc: BaseException) -> str | None:
    if is_connection_timeout(exc):
        return TIMEOUT_MESSAGE
    return None


def run_layout_write(write_fn: Callable[[], None]) -> str | None:
    """Run a color-knowledge (or other layout) write. Keep existing files on timeout."""
    try:
        write_fn()
    except Exception as exc:
        text = user_text_for_layout_timeout(exc)
        if text:
            return text
        raise
    return None


def assistant_text_after_layout_timeout(messages: Sequence[object]) -> str | None:
    for msg in messages:
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip() == TIMEOUT_MESSAGE:
            return TIMEOUT_MESSAGE
    return None

"""Validate image paths for practice PDF embedding (under application data_dir only)."""

from __future__ import annotations

from pathlib import Path

from app.config import settings


def is_allowed_data_path(path: Path) -> bool:
    """True if resolved path is under settings.data_dir (uploads/exports)."""
    try:
        root = settings.data_dir.resolve()
        p = path.resolve()
    except (OSError, ValueError):
        return False
    try:
        p.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_under_data_dir(raw: str) -> Path | None:
    """Join relative paths to data_dir; keep absolute only if still under data_dir."""
    if not (raw or "").strip():
        return None
    p = Path(raw.strip())
    if not p.is_absolute():
        p = (settings.data_dir / p).resolve()
    else:
        p = p.resolve()
    if not is_allowed_data_path(p):
        return None
    return p

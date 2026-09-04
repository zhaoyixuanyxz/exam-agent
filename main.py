"""Vercel / local ASGI entrypoint.

Vercel detects a FastAPI instance named `app` in main.py at the repo root.
The real application lives under backend/app — we only adjust sys.path here.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent / "backend"
if _BACKEND.as_posix() not in sys.path:
    sys.path.insert(0, _BACKEND.as_posix())

from app.main import app  # noqa: E402

__all__ = ["app"]

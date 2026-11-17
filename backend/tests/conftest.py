"""Pytest 入口：在任何 `app` 导入之前设置独立测试库路径。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_session_db_dir = Path(__file__).resolve().parent.parent / ".pytest_session_db"
_session_db_dir.mkdir(parents=True, exist_ok=True)
_fd, _tmp_db = tempfile.mkstemp(suffix=".db", dir=_session_db_dir)
os.close(_fd)
os.environ["EXAM_AGENT_TEST_DB_PATH"] = Path(_tmp_db).resolve().as_posix()

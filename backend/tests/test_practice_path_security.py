from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services.practice_path_security import is_allowed_data_path, resolve_under_data_dir


def test_resolve_under_data_dir_relative(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    (tmp_path / "uploads").mkdir(parents=True)
    f = tmp_path / "uploads" / "a.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
    p = resolve_under_data_dir("uploads/a.png")
    assert p is not None
    assert p.is_file()


def test_resolve_rejects_escape_path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "secret.txt"
    outside.write_text("x")
    p = resolve_under_data_dir(str(outside))
    assert p is None


def test_is_allowed_data_path_under_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    sub = tmp_path / "exports" / "c" / "f.png"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_bytes(b"x")
    assert is_allowed_data_path(sub)

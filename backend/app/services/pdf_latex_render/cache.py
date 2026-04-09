"""公式 PNG 磁盘缓存（sha256 键，临时文件 rename 防并发撕裂）。"""

from __future__ import annotations

import hashlib
from pathlib import Path


def cache_key(
    *,
    version: str,
    renderer: str,
    dpi: int,
    inner: str,
    display_mode: bool,
) -> str:
    raw = f"{version}|{renderer}|{dpi}|{int(display_mode)}|{inner}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_png_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.png"


def read_png_if_exists(path: Path) -> bytes | None:
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return data if len(data) > 80 else None


def write_png_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError:
        try:
            if tmp.is_file():
                tmp.unlink(missing_ok=True)
        except OSError:
            pass

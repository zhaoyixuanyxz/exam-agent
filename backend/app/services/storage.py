import shutil
import uuid
from pathlib import Path

from app.config import settings


def new_stored_path(original_name: str, subdir: str = "uploads") -> Path:
    ext = Path(original_name).suffix or ".bin"
    name = f"{uuid.uuid4().hex}{ext}"
    base = settings.data_dir / subdir
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def export_dir_for_conversation(conversation_id: str) -> Path:
    p = settings.export_dir / conversation_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

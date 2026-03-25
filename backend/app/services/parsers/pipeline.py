from pathlib import Path
from typing import Literal

from app.services.parsers.docx_parser import parse_docx
from app.services.parsers.pdf_parser import parse_pdf
from app.services.parsers.url_parser import parse_url

SourceType = Literal["pdf", "docx", "url", "text"]


def parse_input(
    source_type: SourceType,
    *,
    file_path: Path | None = None,
    url: str | None = None,
    text: str | None = None,
) -> tuple[str, list[str]]:
    """Returns (plain_text, auxiliary_image_paths)."""
    if source_type == "text" and text is not None:
        return text.strip(), []
    if source_type == "url" and url:
        return parse_url(url), []
    if file_path is None:
        return "", []
    suf = file_path.suffix.lower()
    if source_type == "pdf" or suf == ".pdf":
        return parse_pdf(file_path)
    if source_type == "docx" or suf in (".docx",):
        return parse_docx(file_path), []
    if suf == ".doc":
        raise ValueError("暂不支持 .doc，请另存为 .docx 或 PDF")
    return file_path.read_text(encoding="utf-8", errors="replace").strip(), []

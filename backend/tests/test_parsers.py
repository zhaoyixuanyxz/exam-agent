from __future__ import annotations

from pathlib import Path

from docx import Document

from app.services.parsers.pipeline import parse_input


def test_parse_text():
    text, imgs = parse_input("text", text="第一题 1+1=？")
    assert "1+1" in text
    assert imgs == []


def test_parse_docx(tmp_path: Path):
    p = tmp_path / "t.docx"
    doc = Document()
    doc.add_paragraph("选择题：下列正确的是")
    doc.save(p.as_posix())
    text, imgs = parse_input("docx", file_path=p)
    assert "选择题" in text
    assert imgs == []

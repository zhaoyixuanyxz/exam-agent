from pathlib import Path

import fitz
import pytest

from app.services.exam_ingest import MIXED_UPLOAD_MESSAGE, extract_exam_text
from app.services.page_text import EMPTY_PAPER_MESSAGE


def _pdf_with_text(path: Path, text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    # Helvetica cannot encode CJK, so the text layer would be dots and look sparse.
    page.insert_text((72, 72), text, fontname="china-s")
    doc.save(path.as_posix())
    doc.close()
    return path


def _pdf_blank(path: Path) -> Path:
    doc = fitz.open()
    doc.new_page()
    doc.save(path.as_posix())
    doc.close()
    return path


def test_extract_exam_text_uses_pdf_text_layer_without_vision(tmp_path: Path):
    pdf = _pdf_with_text(tmp_path / "e.pdf", "第一题 二次函数顶点坐标")
    calls = {"n": 0}

    def vision(_data: bytes) -> str:
        calls["n"] += 1
        return "should-not-run"

    out = extract_exam_text([pdf], read_image_text=vision)
    assert "二次函数" in out
    assert calls["n"] == 0


def test_extract_exam_text_visions_blank_pdf_page_and_merges(tmp_path: Path):
    pdf = _pdf_blank(tmp_path / "scan.pdf")
    calls = {"n": 0}

    def vision(_data: bytes) -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise TimeoutError("timed out")
        return "扫描第1题 几何面积"

    out = extract_exam_text([pdf], read_image_text=vision)
    assert "几何面积" in out
    assert calls["n"] == 2


def test_extract_exam_text_scraps_page_keeps_other_pages(tmp_path: Path):
    img_a = tmp_path / "a.png"
    img_b = tmp_path / "b.png"
    img_a.write_bytes(b"\x89PNG\r\n\x1a\n")
    img_b.write_bytes(b"\x89PNG\r\n\x1a\n")
    n = {"i": 0}

    def vision(_data: bytes) -> str:
        n["i"] += 1
        if n["i"] <= 3:
            return ""
        return "第二页 选择题"

    out = extract_exam_text([img_a, img_b], read_image_text=vision)
    assert "选择题" in out
    assert n["i"] == 4


def test_extract_exam_text_all_scrap_is_empty(tmp_path: Path):
    img = tmp_path / "blank.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    def vision(_data: bytes) -> str:
        return ""

    assert extract_exam_text([img], read_image_text=vision) == ""


def test_extract_exam_text_rejects_pdf_mixed_with_images(tmp_path: Path):
    pdf = _pdf_with_text(tmp_path / "e.pdf", "第一题")
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(ValueError, match="请分开交"):
        extract_exam_text([pdf, img], read_image_text=lambda _b: "x")
    assert MIXED_UPLOAD_MESSAGE == "请分开交"


def test_extract_exam_text_rejects_doc(tmp_path: Path):
    p = tmp_path / "old.doc"
    p.write_bytes(b"x")
    with pytest.raises(ValueError, match="docx"):
        extract_exam_text([p], read_image_text=lambda _b: "x")

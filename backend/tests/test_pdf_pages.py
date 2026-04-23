"""PDF 按页截取。"""

from pathlib import Path

import fitz

from app.services.parsers.pdf_pages import parse_pdf_page_range_text, pdf_page_count


def test_parse_pdf_page_range_text(tmp_path: Path):
    pdf_path = tmp_path / "t.pdf"
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), "hello page one")
        page2 = doc.new_page()
        page2.insert_text((72, 72), "second")
        doc.save(pdf_path.as_posix())
    finally:
        doc.close()

    assert pdf_page_count(pdf_path) == 2
    t1 = parse_pdf_page_range_text(pdf_path, 1, 1)
    assert "hello" in t1
    t12 = parse_pdf_page_range_text(pdf_path, 1, 2)
    assert "second" in t12

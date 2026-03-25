from pathlib import Path

import fitz  # PyMuPDF


def parse_pdf(path: Path) -> tuple[str, list[str]]:
    doc = fitz.open(path)
    parts: list[str] = []
    image_refs: list[str] = []
    for i, page in enumerate(doc):
        parts.append(page.get_text("text"))
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha < 4:
                    img_path = path.parent / f"{path.stem}_p{i}_img{img_index}.png"
                    pix.save(img_path.as_posix())
                    image_refs.append(img_path.as_posix())
                pix = None
            except Exception:
                continue
    doc.close()
    text = "\n\n".join(parts).strip()
    return text, image_refs

"""pdflatex/xelatex 极简文档 + PyMuPDF 栅格（期刊向；需本机 TeX）。"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import fitz  # PyMuPDF

from app.config import settings

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _pick_engine(inner: str) -> tuple[str, str]:
    if _CJK_RE.search(inner):
        cmd = (settings.practice_pdf_latex_xelatex_cmd or "xelatex").strip()
        return cmd, "xelatex"
    cmd = (settings.practice_pdf_latex_pdflatex_cmd or "pdflatex").strip()
    return cmd, "pdflatex"


def render_tex_to_png_bytes(
    inner: str,
    *,
    display_mode: bool,
    timeout_sec: float,
    dpi: int,
) -> bytes | None:
    tex_body = (inner or "").strip()
    if not tex_body:
        return None
    engine_cmd, kind = _pick_engine(tex_body)
    if not shutil.which(engine_cmd.split()[0]):
        logger.debug("pdf_latex_render: tex engine not in PATH: %s", engine_cmd)
        return None

    if display_mode:
        wrapped = (
            "\\[\n\\displaystyle\n"
            + tex_body.replace("%", "\\%")
            + "\n\\]\n"
        )
    else:
        wrapped = "$" + tex_body.replace("%", "\\%").replace("$", "\\$") + "$"

    doc = (
        "\\documentclass[border=12pt,varwidth]{standalone}\n"
        "\\usepackage{amsmath,amssymb}\n"
        "\\begin{document}\n"
        + wrapped
        + "\n\\end{document}\n"
    )
    if kind == "pdflatex":
        doc = (
            "\\documentclass[border=12pt,varwidth]{standalone}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\begin{document}\n"
            + wrapped
            + "\n\\end{document}\n"
        )

    png: bytes | None = None
    t0 = time.perf_counter()
    try:
        with tempfile.TemporaryDirectory(prefix="exam_tex_") as tmp:
            td = Path(tmp)
            tex_path = td / "job.tex"
            tex_path.write_text(doc, encoding="utf-8")
            cmd_base = engine_cmd.split()
            args = [
                *cmd_base,
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={td}",
                str(tex_path),
            ]
            r = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
                shell=False,
            )
            if r.returncode != 0:
                logger.debug(
                    "pdf_latex_render: %s failed rc=%s stderr=%s",
                    kind,
                    r.returncode,
                    (r.stderr or "")[:800],
                )
                return None
            pdf_path = td / "job.pdf"
            if not pdf_path.is_file():
                return None
            doc_pdf = fitz.open(pdf_path)
            try:
                page = doc_pdf[0]
                pix = page.get_pixmap(dpi=max(72, int(dpi)))
                png = pix.tobytes("png")
            finally:
                doc_pdf.close()
    except Exception as e:
        logger.debug("pdf_latex_render: tex pipeline failed: %s", e, exc_info=True)
        return None

    elapsed = (time.perf_counter() - t0) * 1000.0
    if not png or len(png) < 80:
        return None
    logger.debug("pdf_latex_render: tex ok engine=%s ms=%.1f bytes=%s", kind, elapsed, len(png))
    return png

"""Delete one stored PDF artifact without touching questions or other files."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Artifact, ExamPaper
from app.services.practice_path_security import resolve_under_data_dir

PDF_KINDS = frozenset({"pdf_question", "pdf_answer", "knowledge_pdf"})


def delete_stored_pdf(session: Session, artifact: Artifact) -> None:
    raw = (artifact.path or "").strip()
    if raw:
        resolved = resolve_under_data_dir(raw)
        target = resolved if resolved is not None else None
        if target is not None:
            target.unlink(missing_ok=True)
    if artifact.kind == "knowledge_pdf":
        paper = session.get(ExamPaper, artifact.paper_id)
        if paper is not None:
            setattr(paper, "knowledge_explanation_hidden", True)
            session.add(paper)
    session.delete(artifact)

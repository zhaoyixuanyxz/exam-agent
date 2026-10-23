from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

import fitz
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExamPaper
from app.db.session import get_session
from app.services.anthology_ranges import suggest_ranges_from_page_texts
from app.services.parsers.pdf_pages import parse_pdf_page_range_text, pdf_page_count

router = APIRouter(prefix="/api", tags=["exam-papers"])


class ConversationIdBody(BaseModel):
    conversation_id: str = Field(..., min_length=1)


class SplitByPagesBody(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    ranges: list[list[int]] = Field(..., min_length=1)
    labels: list[str] | None = None


@router.post("/exam-papers/{paper_id}/anthology-split/mark-needed")
async def mark_anthology_needed(
    paper_id: str,
    body: ConversationIdBody,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != body.conversation_id:
        raise HTTPException(404, "试卷不存在或不属于该会话")
    if (p.anthology_split_status or "") == "done":
        raise HTTPException(400, "该合订本已切开，请对子材料操作。")
    p.anthology_split_status = "needed"
    await session.commit()
    return {"ok": True, "anthology_split_status": "needed"}


@router.post("/exam-papers/{paper_id}/suggest-page-ranges")
async def suggest_page_ranges(
    paper_id: str,
    body: ConversationIdBody,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != body.conversation_id:
        raise HTTPException(404, "试卷不存在或不属于该会话")
    if not p.raw_path:
        raise HTTPException(400, "该材料无本地 PDF 路径")
    path = Path(p.raw_path)
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise HTTPException(400, "仅支持已上传且存在的 PDF 文件")
    try:
        doc = fitz.open(path.as_posix())
        try:
            texts = [
                (doc.load_page(i).get_text("text") or "") for i in range(doc.page_count)
            ]
        finally:
            doc.close()
    except Exception as e:
        raise HTTPException(400, f"无法读取 PDF：{e!s}") from e
    ranges, labels, message = suggest_ranges_from_page_texts(texts)
    return {
        "ranges": ranges,
        "labels": labels,
        "message": message,
        "page_count": len(texts),
    }


@router.post("/exam-papers/{paper_id}/split-by-pages")
async def split_exam_paper_by_pages(
    paper_id: str,
    body: SplitByPagesBody,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    p = await session.get(ExamPaper, paper_id)
    if not p or p.conversation_id != body.conversation_id:
        raise HTTPException(404, "试卷不存在或不属于该会话")
    if not p.raw_path:
        raise HTTPException(400, "该材料无本地 PDF 路径，无法按页拆分")
    path = Path(p.raw_path)
    if path.suffix.lower() != ".pdf" or not path.is_file():
        raise HTTPException(400, "仅支持已上传且存在的 PDF 文件")

    try:
        total = pdf_page_count(path)
    except Exception as e:
        raise HTTPException(400, f"无法读取 PDF：{e!s}") from e

    if body.labels is not None and len(body.labels) != len(body.ranges):
        raise HTTPException(400, "labels 须与 ranges 等长，或省略 labels")

    new_papers: list[dict] = []
    covered: set[int] = set()
    for idx, pair in enumerate(body.ranges):
        if len(pair) != 2:
            raise HTTPException(400, "每个 range 须为 [起始页, 结束页] 两个整数")
        a, b = int(pair[0]), int(pair[1])
        if a < 1 or b < 1 or a > b or a > total or b > total:
            raise HTTPException(
                400,
                f"第 {idx + 1} 段页码无效：文档共 {total} 页，收到 {a}-{b}",
            )
        try:
            from app.services.vision_read import read_image_text

            text = parse_pdf_page_range_text(
                path,
                a,
                b,
                read_image_text=read_image_text,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        label = None
        if body.labels and idx < len(body.labels) and str(body.labels[idx]).strip():
            label = str(body.labels[idx]).strip()
        display = label or f"片段{idx + 1}"
        npid = str(uuid.uuid4())
        session.add(
            ExamPaper(
                id=npid,
                conversation_id=p.conversation_id,
                raw_path=p.raw_path,
                source_type="pdf",
                raw_text=text,
                display_name=display,
                anthology_split_status="none",
            )
        )
        new_papers.append(
            {
                "id": npid,
                "label": display,
                "pages": [a, b],
            }
        )
        covered.update(range(a, b + 1))

    # 仅合订待分套切开后标记父材料 done；普通按页拆分不得永久挡确认
    if (getattr(p, "anthology_split_status", None) or "none").strip() == "needed":
        p.anthology_split_status = "done"
    missing = [i for i in range(1, total + 1) if i not in covered]
    hint = ""
    if missing:
        if len(missing) <= 5:
            pages_s = "、".join(str(i) for i in missing)
        else:
            pages_s = "、".join(str(i) for i in missing[:5]) + "…"
        hint = f"有页未纳入任何套（将排除）：{pages_s}"

    await session.commit()
    return {
        "new_papers": new_papers,
        "uncovered_pages_hint": hint,
        "message": (
            "已按页生成新材料记录。后续对话默认仍绑定本轮 paper_id；"
            "若需处理某条新材料，请在下一条消息中说明对应 paper_id（可抄下列 id 前 8 位）。"
        ),
    }

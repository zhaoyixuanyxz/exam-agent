from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExamPaper
from app.db.session import get_session
from app.services.parsers.pdf_pages import parse_pdf_page_range_text, pdf_page_count

router = APIRouter(prefix="/api", tags=["exam-papers"])


class SplitByPagesBody(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    ranges: list[list[int]] = Field(..., min_length=1)


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

    new_papers: list[dict] = []
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
            text = parse_pdf_page_range_text(path, a, b)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        npid = str(uuid.uuid4())
        session.add(
            ExamPaper(
                id=npid,
                conversation_id=p.conversation_id,
                raw_path=p.raw_path,
                source_type="pdf",
                raw_text=text,
            )
        )
        new_papers.append(
            {
                "id": npid,
                "label": f"片段{idx + 1}",
                "pages": [a, b],
            }
        )

    await session.commit()
    return {
        "new_papers": new_papers,
        "message": (
            "已按页生成新材料记录。后续对话默认仍绑定本轮 paper_id；"
            "若需处理某条新材料，请在下一条消息中说明对应 paper_id（可抄下列 id 前 8 位）。"
        ),
    }

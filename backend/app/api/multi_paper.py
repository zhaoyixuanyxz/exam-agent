"""V2.2 多卷聚合分析原型 API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation
from app.db.session import get_session
from app.models.schemas import MultiPaperAnalysisRequest, MultiPaperAnalysisResponse
from app.services.multi_paper_analysis import run_multi_paper_analysis

router = APIRouter(prefix="/api", tags=["multi-paper"])


@router.post(
    "/conversations/{conversation_id}/multi-paper-analysis",
    response_model=MultiPaperAnalysisResponse,
)
async def post_multi_paper_analysis(
    conversation_id: str,
    body: MultiPaperAnalysisRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    conv = await session.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "conversation not found")
    try:
        return run_multi_paper_analysis(conversation_id, body)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

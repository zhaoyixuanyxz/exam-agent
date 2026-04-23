"""题单 / 组卷篮操作。"""

from __future__ import annotations

import random
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, PaperSet, PaperSetItem, QuestionAsset, QuestionKnowledgeLink
from app.db.v23_ids import DEFAULT_USER_ID
from app.models.schemas import CompilePaperRequest, CompilePaperResponse, PaperSetAddItemsRequest, PaperSetDTO, PaperSetDetailDTO
from app.services.question_bank_query import question_asset_to_dto


def _dt_iso(t: Any) -> str | None:
    if t is None:
        return None
    if hasattr(t, "isoformat"):
        return t.isoformat()
    return str(t)


def list_paper_sets(
    session: Session, conversation_id: str, user: AppUser
) -> list[PaperSet]:
    stmt = select(PaperSet).where(PaperSet.conversation_id == conversation_id)
    if (user.role or "") != "admin":
        from sqlalchemy import or_

        stmt = stmt.where(
            or_(
                PaperSet.owner_user_id == str(user.id),
                PaperSet.owner_user_id.is_(None),
                PaperSet.owner_user_id == DEFAULT_USER_ID,
            )
        )
    rows = list(
        session.execute(
            stmt.order_by(PaperSet.updated_at.desc().nulls_last(), PaperSet.id.desc())
        ).scalars().all()
    )
    return list(rows)


def create_paper_set(
    session: Session, conversation_id: str, name: str, user: AppUser, config: dict
) -> PaperSet:
    now = datetime.utcnow()
    ps = PaperSet(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        owner_user_id=str(user.id),
        name=name or "题单",
        config_json=config,
        created_at=now,
        updated_at=now,
    )
    session.add(ps)
    session.commit()
    session.refresh(ps)
    return ps


def paper_set_to_dto(session: Session, ps: PaperSet) -> PaperSetDTO:
    c = int(
        session.execute(
            select(func.count())
            .select_from(PaperSetItem)
            .where(PaperSetItem.paper_set_id == ps.id)
        )
        .scalar() or 0
    )
    return PaperSetDTO(
        id=ps.id,
        conversation_id=ps.conversation_id,
        name=ps.name,
        config_json=ps.config_json or {},
        item_count=c,
        created_at=_dt_iso(ps.created_at),
        updated_at=_dt_iso(ps.updated_at),
    )


def get_detail(session: Session, set_id: str) -> PaperSetDetailDTO | None:
    ps = session.get(PaperSet, set_id)
    if not ps:
        return None
    items = list(
        session.execute(
            select(PaperSetItem, QuestionAsset)
            .join(QuestionAsset, QuestionAsset.id == PaperSetItem.question_asset_id)
            .where(PaperSetItem.paper_set_id == set_id)
            .order_by(PaperSetItem.sort_order, PaperSetItem.id)
        )
        .all()
    )
    dtos = [question_asset_to_dto(session, row[1]) for row in items]
    return PaperSetDetailDTO(paper_set=paper_set_to_dto(session, ps), items=dtos)


def add_items(
    session: Session,
    set_id: str,
    body: PaperSetAddItemsRequest,
) -> int:
    ps = session.get(PaperSet, set_id)
    if not ps:
        return 0
    mx = 0
    for row in session.execute(
        select(PaperSetItem.sort_order)
        .where(PaperSetItem.paper_set_id == set_id)
        .order_by(PaperSetItem.sort_order.desc())
        .limit(1)
    ).all():
        mx = int(row[0] or 0)
    n = 0
    for i, qid in enumerate(body.question_asset_ids):
        if not session.get(QuestionAsset, qid):
            continue
        ex = session.execute(
            select(PaperSetItem).where(
                PaperSetItem.paper_set_id == set_id, PaperSetItem.question_asset_id == qid
            )
        ).scalar_one_or_none()
        if ex:
            continue
        n += 1
        session.add(
            PaperSetItem(
                id=str(uuid.uuid4()),
                paper_set_id=set_id,
                question_asset_id=qid,
                sort_order=mx + i + 1,
                created_at=datetime.utcnow(),
            )
        )
    ps.updated_at = datetime.utcnow()
    session.commit()
    return n


def compile_paper(
    session: Session,
    user: AppUser,
    req: CompilePaperRequest,
) -> CompilePaperResponse:
    """从全库可访问题目中按参数抽样（MVP：随机+约束）。"""
    stmt = select(QuestionAsset)
    if (user.role or "") != "admin":
        from sqlalchemy import or_

        stmt = stmt.where(
            or_(
                QuestionAsset.owner_user_id == str(user.id),
                QuestionAsset.owner_user_id == DEFAULT_USER_ID,
                QuestionAsset.owner_user_id.is_(None),
                QuestionAsset.visibility == "public",
            )
        )
    rows = list(session.execute(stmt).scalars().all())
    cands: list[QuestionAsset] = []
    for r in rows:
        if req.knowledge_point_ids:
            links = list(
                session.execute(
                    select(QuestionKnowledgeLink.knowledge_point_id).where(
                        QuestionKnowledgeLink.question_asset_id == r.id
                    )
                )
                .scalars()
                .all()
            )
            lset = {str(x) for x in links}
            if not lset.intersection({str(x) for x in req.knowledge_point_ids}):
                continue
        cands.append(r)
    if not cands:
        return CompilePaperResponse(
            selected_question_ids=[],
            message="无可用题目，请检查考点筛选或先沉淀题目资产。",
        )
    random.shuffle(cands)
    take = cands[: int(req.target_count)]
    return CompilePaperResponse(
        selected_question_ids=[str(x.id) for x in take],
        message="已按题量与考点约束抽样（MVP 随机策略）。",
    )

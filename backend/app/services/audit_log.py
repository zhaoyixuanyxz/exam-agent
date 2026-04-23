"""审计日志。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def log_action(
    session: Session,
    *,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str = "",
    detail: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id or "",
            detail_json=detail,
        )
    )

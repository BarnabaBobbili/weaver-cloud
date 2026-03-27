from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Notification


async def create_notification(
    db: AsyncSession,
    user_id: str | None,
    notification_type: str,
    message: str,
) -> None:
    if not user_id or user_id == "guest":
        return
    db.add(
        Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            type=notification_type,
            message=message,
        )
    )

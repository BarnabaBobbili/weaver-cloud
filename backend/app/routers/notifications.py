from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.notifications import Notification
from app.models.user import User

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _to_dict(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "user_id": notification.user_id,
        "type": notification.type,
        "message": notification.message,
        "is_read": notification.is_read,
        "created_at": str(notification.created_at),
    }


@router.get("")
async def list_notifications(
    page: int = 1,
    limit: int = 10,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 50))
    offset = (page - 1) * limit
    filters = [Notification.user_id == current_user.id]
    if unread_only:
        filters.append(Notification.is_read == False)  # noqa: E712

    total = (
        await db.execute(select(func.count()).select_from(Notification).where(*filters))
    ).scalar() or 0
    rows = (
        await db.execute(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    unread_count = (
        await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == current_user.id,
                Notification.is_read == False,  # noqa: E712
            )
        )
    ).scalar() or 0

    return {
        "items": [_to_dict(row) for row in rows],
        "total": total,
        "page": page,
        "pages": ceil(total / limit) if limit else 1,
        "unread": unread_count,
    }


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id)
        .values(is_read=True)
    )
    return {"message": "Notification marked as read"}


@router.post("")
async def create_user_notification(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = str(data.get("message", "")).strip()
    notification_type = str(data.get("type", "info")).strip() or "info"
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    notification = Notification(
        user_id=current_user.id,
        type=notification_type,
        message=message,
    )
    db.add(notification)
    await db.flush()
    return _to_dict(notification)


@router.post("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id)
        .values(is_read=True)
    )
    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.delete(row)

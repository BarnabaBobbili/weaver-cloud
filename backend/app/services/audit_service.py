from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models.audit import AuditLog


async def log_event(
    db: AsyncSession,
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[dict] = None,
    severity: str = "info",
) -> None:
    """Write a structured audit log entry. Silent on failure to avoid blocking the main flow."""
    try:
        ip = None
        ua = None
        if request:
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else (
                request.client.host if request.client else None
            )
            ua = request.headers.get("User-Agent")

        log = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip,
            user_agent=ua,
            details=details,
            severity=severity,
        )
        db.add(log)
    except Exception:
        pass  # Audit failure must NOT break the main request

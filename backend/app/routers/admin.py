import csv
import io
import uuid
from datetime import date, datetime, time, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.audit import AuditLog
from app.models.classification import ClassificationRecord
from app.models.encryption import EncryptedPayload, ShareLink
from app.models.share_access import ShareAccessLog
from app.models.user import User
from app.security.password import hash_password
from app.security.rbac import require_roles
from app.services import crypto_service
from app.services.audit_service import log_event
from app.services.auth_service import revoke_all_refresh_tokens, validate_password_policy
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "mfa_enabled": user.mfa_enabled,
        "failed_login_attempts": user.failed_login_attempts,
        "created_at": str(user.created_at),
        "updated_at": str(user.updated_at),
    }


def _share_status(share: ShareLink) -> str:
    if share.is_revoked:
        return "revoked"
    if share.expires_at and share.expires_at < datetime.now(timezone.utc):
        return "expired"
    if share.max_access_count and share.current_access_count >= share.max_access_count:
        return "expired"
    return "active"


def _recover_share_url(token_encrypted: bytes | None) -> str | None:
    if not token_encrypted:
        return None
    try:
        raw_token = crypto_service.unwrap_dek_with_server_kek(token_encrypted).decode("utf-8")
    except Exception:
        return None
    return f"/decrypt/{raw_token}"


@router.get("/users")
async def list_users(
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    limit = 20
    total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    users = (
        await db.execute(
            select(User).order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
    ).scalars().all()
    return {"items": [_user_dict(user) for user in users], "total": total, "page": page, "pages": ceil(total / limit) if limit else 1}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    if not all(data.get(field) for field in ("email", "password", "full_name")):
        raise HTTPException(status_code=422, detail="email, password, and full_name are required")
    validate_password_policy(data["password"])
    existing = (await db.execute(select(User).where(User.email == data["email"].strip().lower()))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(
        id=str(uuid.uuid4()),
        email=data["email"].strip().lower(),
        password_hash=hash_password(data["password"]),
        full_name=data["full_name"].strip(),
        role=data.get("role", "analyst"),
    )
    db.add(user)
    await db.flush()
    await log_event(db, "admin_create_user", current_user.id, "user", user.id, request)
    return _user_dict(user)


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    data: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    allowed = {"role", "is_active"}
    updates = {key: value for key, value in data.items() if key in allowed}
    if not updates:
        raise HTTPException(status_code=422, detail="No valid fields to update")
    await db.execute(update(User).where(User.id == user_id).values(**updates))
    await log_event(db, "admin_update_user", current_user.id, "user", user_id, request, details=updates)
    return {"message": "User updated"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    await db.execute(update(User).where(User.id == user_id).values(is_active=False))
    await log_event(db, "admin_deactivate_user", current_user.id, "user", user_id, request)


@router.post("/users/{user_id}/reset-mfa")
async def reset_mfa(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    await db.execute(
        update(User).where(User.id == user_id).values(
            mfa_enabled=False,
            mfa_secret=None,
            mfa_recovery_codes=None,
        )
    )
    await create_notification(db, user_id, "admin_reset_mfa", "An administrator reset your MFA configuration.")
    await log_event(db, "admin_reset_mfa", current_user.id, "user", user_id, request)
    return {"message": "MFA reset"}


@router.post("/users/{user_id}/unlock")
async def unlock_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    await db.execute(update(User).where(User.id == user_id).values(failed_login_attempts=0, locked_until=None))
    await create_notification(db, user_id, "account_unlocked", "An administrator unlocked your account.")
    await log_event(db, "admin_unlock_user", current_user.id, "user", user_id, request)
    return {"message": "Account unlocked"}


@router.post("/users/{user_id}/force-logout")
async def force_logout_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    await revoke_all_refresh_tokens(db, user_id)
    await create_notification(db, user_id, "force_logout", "An administrator revoked your active sessions.")
    await log_event(db, "admin_force_logout", current_user.id, "user", user_id, request)
    return {"message": "All sessions revoked"}


@router.get("/shares")
async def list_all_shares(
    page: int = 1,
    search: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    limit = 20
    query = (
        select(ShareLink, User.email, ClassificationRecord.input_text_preview, EncryptedPayload.file_name, EncryptedPayload.content_type)
        .outerjoin(User, User.id == ShareLink.user_id)
        .outerjoin(EncryptedPayload, EncryptedPayload.id == ShareLink.payload_id)
        .outerjoin(ClassificationRecord, ClassificationRecord.id == EncryptedPayload.classification_id)
    )

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                ShareLink.token_prefix.ilike(search_term),
                User.email.ilike(search_term),
                ClassificationRecord.input_text_preview.ilike(search_term),
                EncryptedPayload.file_name.ilike(search_term),
            )
        )

    rows = (
        await db.execute(
            query.order_by(ShareLink.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
    ).all()
    total = len(rows) if page == 1 and len(rows) < limit else (await db.execute(select(func.count()).select_from(ShareLink))).scalar() or 0

    items = []
    for share, owner_email, preview, file_name, content_type in rows:
        items.append(
            {
                "id": share.id,
                "payload_id": share.payload_id,
                "token_prefix": share.token_prefix or "",
                "share_url": _recover_share_url(share.token_encrypted),
                "content_preview": preview or "",
                "file_name": file_name,
                "content_type": content_type,
                "expires_at": str(share.expires_at) if share.expires_at else None,
                "max_access_count": share.max_access_count,
                "current_access_count": share.current_access_count,
                "is_revoked": share.is_revoked,
                "password_protected": bool(share.password_hash),
                "created_at": str(share.created_at),
                "status": _share_status(share),
                "owner_email": owner_email or "Guest",
            }
        )
    return {"items": items, "total": total, "page": page, "pages": ceil(total / limit) if limit else 1}


@router.delete("/shares/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_any_share(
    link_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    await db.execute(update(ShareLink).where(ShareLink.id == link_id).values(is_revoked=True))
    await log_event(db, "admin_revoke_share", current_user.id, "share_link", link_id, request)


@router.get("/shares/{link_id}/access-logs")
async def admin_share_access_logs(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    rows = (
        await db.execute(
            select(ShareAccessLog)
            .where(ShareAccessLog.share_id == link_id)
            .order_by(ShareAccessLog.accessed_at.desc())
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "accessed_at": str(row.accessed_at),
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
            }
            for row in rows
        ]
    }


@router.get("/audit-logs")
async def admin_audit_logs(
    page: int = 1,
    limit: int = 20,
    user: str = "",
    action: str = "",
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    query = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id)
    count_query = select(func.count()).select_from(AuditLog).outerjoin(User, User.id == AuditLog.user_id)

    if user:
        user_term = f"%{user}%"
        query = query.where(or_(AuditLog.user_id.ilike(user_term), User.email.ilike(user_term)))
        count_query = count_query.where(or_(AuditLog.user_id.ilike(user_term), User.email.ilike(user_term)))
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if from_date:
        dt = datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        query = query.where(AuditLog.created_at >= dt)
        count_query = count_query.where(AuditLog.created_at >= dt)
    if to_date:
        dt = datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        query = query.where(AuditLog.created_at <= dt)
        count_query = count_query.where(AuditLog.created_at <= dt)

    total = (await db.execute(count_query)).scalar() or 0
    rows = (
        await db.execute(query.order_by(AuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit))
    ).all()
    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_email": email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "details": log.details,
                "severity": log.severity,
                "created_at": str(log.created_at),
            }
            for log, email in rows
        ],
        "total": total,
        "page": page,
        "pages": ceil(total / limit) if limit else 1,
    }


@router.get("/audit-logs/export")
async def export_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    rows = (
        await db.execute(
            select(AuditLog, User.email)
            .outerjoin(User, User.id == AuditLog.user_id)
            .order_by(AuditLog.created_at.desc())
        )
    ).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "user_id", "user_email", "action", "resource_type", "resource_id", "ip_address", "severity", "created_at"])
    for log, email in rows:
        writer.writerow([log.id, log.user_id, email, log.action, log.resource_type, log.resource_id, log.ip_address, log.severity, log.created_at])
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit-logs.csv"})


@router.get("/compliance-report")
async def compliance_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    total_encryptions = (await db.execute(select(func.count()).select_from(EncryptedPayload))).scalar() or 0
    unencrypted_ops = (
        await db.execute(select(func.count()).select_from(EncryptedPayload).where(EncryptedPayload.encryption_algo == "NONE"))
    ).scalar() or 0
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    mfa_enabled = (
        await db.execute(select(func.count()).select_from(User).where(User.mfa_enabled == True))  # noqa: E712
    ).scalar() or 0
    locked_accounts = (
        await db.execute(
            select(func.count()).select_from(User).where(User.locked_until.is_not(None), User.locked_until > datetime.now(timezone.utc))
        )
    ).scalar() or 0
    policy_override_events = (
        await db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.action == "encrypt_policy_override"))
    ).scalar() or 0
    by_level_rows = (
        await db.execute(
            select(ClassificationRecord.predicted_level, func.count())
            .join(EncryptedPayload, EncryptedPayload.classification_id == ClassificationRecord.id)
            .group_by(ClassificationRecord.predicted_level)
        )
    ).all()

    return {
        "total_encryptions": total_encryptions,
        "encryptions_by_level": {level: count for level, count in by_level_rows},
        "unencrypted_ops": unencrypted_ops,
        "mfa_adoption_pct": round((mfa_enabled / total_users) * 100, 1) if total_users else 0,
        "locked_accounts": locked_accounts,
        "policy_violations": policy_override_events,
        "security_score": max(0, 100 - (policy_override_events * 5) - (locked_accounts * 2) - (unencrypted_ops * 2)),
    }

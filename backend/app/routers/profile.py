from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.audit import AuditLog
from app.models.classification import ClassificationRecord
from app.models.encryption import EncryptedPayload, ShareLink
from app.models.user import User
from app.security.password import verify_password, hash_password
from app.services.audit_service import log_event
from app.services.auth_service import ensure_password_strength, revoke_all_refresh_tokens

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _user_dict(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "role": u.role, "is_active": u.is_active, "mfa_enabled": u.mfa_enabled,
        "failed_login_attempts": u.failed_login_attempts,
        "created_at": str(u.created_at), "updated_at": str(u.updated_at),
    }


@router.get("")
async def get_profile(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)


@router.put("")
async def update_profile(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = {"full_name"}
    upd = {k: v for k, v in data.items() if k in allowed and v}
    if upd:
        await db.execute(update(User).where(User.id == current_user.id).values(**upd))
    return {"message": "Profile updated"}


@router.put("/password")
async def change_password(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.get("current_password", ""), current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    ensure_password_strength(data["new_password"])
    new_pw_hash = hash_password(data["new_password"])
    await db.execute(update(User).where(User.id == current_user.id).values(password_hash=new_pw_hash))
    return {"message": "Password changed"}


@router.get("/activity")
async def activity(
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limit = 20
    total = (await db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.user_id == current_user.id)
    )).scalar() or 0
    res = await db.execute(
        select(AuditLog).where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc()).offset((page-1)*limit).limit(limit)
    )
    logs = res.scalars().all()
    return {
        "items": [
            {"id": l.id, "action": l.action, "details": str(l.details or ""),
             "created_at": str(l.created_at)} for l in logs
        ],
        "total": total, "page": page, "pages": ceil(total / limit) if limit else 1,
    }


@router.get("/sessions")
async def sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Sessions are backed by refresh_tokens table
    from app.models.user import RefreshToken
    res = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked == False,  # noqa: E712
        ).order_by(RefreshToken.created_at.desc())
    )
    tokens = res.scalars().all()
    return [
        {"id": t.id, "device": "Browser", "browser": "Unknown",
         "ip_address": "—", "last_active": str(t.created_at),
         "is_current": False}
        for t in tokens
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.user import RefreshToken
    from sqlalchemy import update as sql_update
    await db.execute(
        sql_update(RefreshToken).where(
            RefreshToken.id == session_id,
            RefreshToken.user_id == current_user.id,
        ).values(revoked=True)
    )


@router.get("/stats")
async def stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_cls = (await db.execute(
        select(func.count()).select_from(ClassificationRecord).where(
            ClassificationRecord.user_id == current_user.id
        )
    )).scalar() or 0
    total_enc = (await db.execute(
        select(func.count()).select_from(EncryptedPayload).where(
            EncryptedPayload.user_id == current_user.id
        )
    )).scalar() or 0
    total_shares = (await db.execute(
        select(func.count()).select_from(ShareLink).where(ShareLink.user_id == current_user.id)
    )).scalar() or 0
    active_shares = (await db.execute(
        select(func.count()).select_from(ShareLink).where(
            ShareLink.user_id == current_user.id,
            ShareLink.is_revoked == False,  # noqa: E712
        )
    )).scalar() or 0
    return {"total_classifications": total_cls, "total_encryptions": total_enc,
            "total_shares": total_shares, "active_shares": active_shares}


@router.get("/export")
async def export_profile_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    classifications = (
        await db.execute(select(ClassificationRecord).where(ClassificationRecord.user_id == current_user.id))
    ).scalars().all()
    encryptions = (
        await db.execute(select(EncryptedPayload).where(EncryptedPayload.user_id == current_user.id))
    ).scalars().all()
    shares = (
        await db.execute(select(ShareLink).where(ShareLink.user_id == current_user.id))
    ).scalars().all()
    audit_logs = (
        await db.execute(select(AuditLog).where(AuditLog.user_id == current_user.id))
    ).scalars().all()
    return JSONResponse(
        {
            "profile": _user_dict(current_user),
            "classifications": [
                {
                    "id": row.id,
                    "input_text_preview": row.input_text_preview,
                    "input_type": row.input_type,
                    "file_name": row.file_name,
                    "predicted_level": row.predicted_level,
                    "confidence_score": row.confidence_score,
                    "created_at": str(row.created_at),
                }
                for row in classifications
            ],
            "encryptions": [
                {
                    "id": row.id,
                    "classification_id": row.classification_id,
                    "encryption_algo": row.encryption_algo,
                    "original_size": row.original_size,
                    "encrypted_size": row.encrypted_size,
                    "created_at": str(row.created_at),
                }
                for row in encryptions
            ],
            "shares": [
                {
                    "id": row.id,
                    "payload_id": row.payload_id,
                    "token_prefix": row.token_prefix,
                    "expires_at": str(row.expires_at) if row.expires_at else None,
                    "max_access_count": row.max_access_count,
                    "current_access_count": row.current_access_count,
                    "is_revoked": row.is_revoked,
                    "created_at": str(row.created_at),
                }
                for row in shares
            ],
            "audit_logs": [
                {
                    "id": row.id,
                    "action": row.action,
                    "details": row.details,
                    "severity": row.severity,
                    "created_at": str(row.created_at),
                }
                for row in audit_logs
            ],
        },
        headers={"Content-Disposition": "attachment; filename=weaver-profile-export.json"},
    )


@router.delete("/account", status_code=204)
async def delete_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(update(User).where(User.id == current_user.id).values(is_active=False))
    await revoke_all_refresh_tokens(db, current_user.id)
    await log_event(db, "profile_soft_delete", current_user.id, "user", current_user.id, request)

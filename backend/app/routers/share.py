import secrets
import uuid
from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.encryption import EncryptedPayload, ShareLink
from app.models.classification import ClassificationRecord
from app.models.share_access import ShareAccessLog
from app.models.user import User
from app.schemas.encryption import ShareCreateRequest, ShareCreateResponse, ShareLinkResponse
from app.security.jwt_handler import hash_token
from app.security.password import hash_password
from app.security.rate_limiter import limiter
from app.services import crypto_service
from app.services.audit_service import log_event

router = APIRouter(prefix="/api/share", tags=["share"])


def _parse_expiry(expires_in: str | None) -> datetime | None:
    if not expires_in or expires_in.lower() in ("never", ""):
        return None
    mapping = {"h": 1/24, "d": 1, "w": 7, "m": 30}
    unit = expires_in[-1].lower()
    try:
        amount = int(expires_in[:-1])
        days = amount * mapping.get(unit, 1)
        return datetime.now(timezone.utc) + timedelta(days=days)
    except Exception:
        return None


def _share_status(s: ShareLink) -> str:
    if s.is_revoked:
        return "revoked"
    if s.expires_at and s.expires_at < datetime.now(timezone.utc):
        return "expired"
    if s.max_access_count and s.current_access_count >= s.max_access_count:
        return "expired"
    return "active"


def _encrypt_share_token(raw_token: str) -> bytes:
    return crypto_service.wrap_dek_with_server_kek(raw_token.encode("utf-8"))


def _recover_share_url(token_encrypted: bytes | None) -> str | None:
    if not token_encrypted:
        return None
    try:
        raw_token = crypto_service.unwrap_dek_with_server_kek(token_encrypted).decode("utf-8")
    except Exception:
        return None
    return f"/decrypt/{raw_token}"


def _to_schema(
    s: ShareLink,
    preview: str = "",
    file_name: str | None = None,
    content_type: str | None = None,
) -> ShareLinkResponse:
    return ShareLinkResponse(
        id=s.id, payload_id=s.payload_id,
        token_prefix=s.token_prefix or "",
        share_url=_recover_share_url(s.token_encrypted),
        content_preview=preview,
        file_name=file_name,
        content_type=content_type,
        expires_at=str(s.expires_at) if s.expires_at else None,
        max_access_count=s.max_access_count,
        current_access_count=s.current_access_count,
        is_revoked=s.is_revoked,
        password_protected=bool(s.password_hash),
        created_at=str(s.created_at),
        status=_share_status(s),
    )


@router.post("", response_model=ShareCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_share(
    request: Request,
    data: ShareCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify user owns the payload
    res = await db.execute(
        select(EncryptedPayload).where(
            EncryptedPayload.id == data.payload_id,
            EncryptedPayload.user_id == current_user.id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Payload not found")

    raw_token = secrets.token_urlsafe(48)  # 64-char URL-safe token
    token_hash_val = hash_token(raw_token)
    token_prefix = raw_token[:8]
    expires_at = _parse_expiry(data.expires_in)
    password_hash_val = hash_password(data.password) if data.password else None

    share = ShareLink(
        id=str(uuid.uuid4()),
        payload_id=data.payload_id,
        user_id=current_user.id,
        token_hash=token_hash_val,
        token_encrypted=_encrypt_share_token(raw_token),
        token_prefix=token_prefix,
        password_hash=password_hash_val,
        expires_at=expires_at,
        max_access_count=data.max_access,
    )
    db.add(share)
    await db.flush()
    await log_event(db, "share_create", current_user.id, "share_link", share.id, request)

    share_url = f"/decrypt/{raw_token}"
    return ShareCreateResponse(
        share_id=share.id,
        token=raw_token,
        share_url=share_url,
        token_prefix=token_prefix,
        expires_at=str(expires_at) if expires_at else None,
        max_access_count=data.max_access,
    )


@router.get("/mine")
async def list_my_shares(
    page: int = 1,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limit = 20
    offset = (page - 1) * limit
    count_res = await db.execute(
        select(func.count()).select_from(ShareLink).where(ShareLink.user_id == current_user.id)
    )
    total = count_res.scalar() or 0
    res = await db.execute(
        select(ShareLink).where(ShareLink.user_id == current_user.id)
        .order_by(ShareLink.created_at.desc()).offset(offset).limit(limit)
    )
    shares = res.scalars().all()

    payload_ids = [s.payload_id for s in shares]
    preview_by_payload_id: dict[str, tuple[str, str | None, str | None]] = {}
    if payload_ids:
        payloads = (await db.execute(
            select(EncryptedPayload.id, ClassificationRecord.input_text_preview, EncryptedPayload.file_name, EncryptedPayload.content_type)
            .join(
                ClassificationRecord,
                ClassificationRecord.id == EncryptedPayload.classification_id,
                isouter=True,
            )
            .where(EncryptedPayload.id.in_(payload_ids))
        )).all()
        preview_by_payload_id = {
            payload_id: (preview or "", file_name, content_type)
            for payload_id, preview, file_name, content_type in payloads
        }

    return {"items": [
        _to_schema(
            s,
            preview_by_payload_id.get(s.payload_id, ("", None, None))[0],
            preview_by_payload_id.get(s.payload_id, ("", None, None))[1],
            preview_by_payload_id.get(s.payload_id, ("", None, None))[2],
        )
        for s in shares
    ], "total": total,
            "page": page, "pages": ceil(total / limit) if limit else 1}


@router.get("/{payload_id}/links")
async def list_payload_shares(
    payload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(ShareLink).where(
            ShareLink.payload_id == payload_id,
            ShareLink.user_id == current_user.id,
        )
    )
    share_rows = res.scalars().all()
    payload_res = await db.execute(
        select(ClassificationRecord.input_text_preview, EncryptedPayload.file_name, EncryptedPayload.content_type)
        .join(EncryptedPayload, EncryptedPayload.classification_id == ClassificationRecord.id)
        .where(EncryptedPayload.id == payload_id)
    )
    payload_meta = payload_res.one_or_none()
    preview = payload_meta[0] if payload_meta else ""
    file_name = payload_meta[1] if payload_meta else None
    content_type = payload_meta[2] if payload_meta else None
    return [_to_schema(s, preview, file_name, content_type) for s in share_rows]


@router.get("/{link_id}/stats")
async def share_stats(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(ShareLink).where(ShareLink.id == link_id, ShareLink.user_id == current_user.id)
    )
    share = res.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")
    payload_res = await db.execute(
        select(ClassificationRecord.input_text_preview, EncryptedPayload.file_name, EncryptedPayload.content_type)
        .join(EncryptedPayload, EncryptedPayload.classification_id == ClassificationRecord.id)
        .where(EncryptedPayload.id == share.payload_id)
    )
    payload_meta = payload_res.one_or_none()
    preview = payload_meta[0] if payload_meta else ""
    file_name = payload_meta[1] if payload_meta else None
    content_type = payload_meta[2] if payload_meta else None
    return _to_schema(share, preview, file_name, content_type)


@router.get("/{link_id}/access-logs")
async def share_access_logs(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    share = (
        await db.execute(
            select(ShareLink).where(ShareLink.id == link_id, ShareLink.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")

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


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(ShareLink).where(ShareLink.id == link_id, ShareLink.user_id == current_user.id)
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Share link not found")
    await db.execute(update(ShareLink).where(ShareLink.id == link_id).values(is_revoked=True))
    await log_event(db, "share_revoke", current_user.id, "share_link", link_id)

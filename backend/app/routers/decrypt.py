import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.encryption import EncryptedPayload, ShareLink
from app.models.share_access import ShareAccessLog
from app.models.user import User
from app.schemas.encryption import DecryptRequest, DecryptResponse
from app.security.jwt_handler import hash_token
from app.security.password import verify_password
from app.security.rate_limiter import limiter
from app.services import crypto_service
from app.services.audit_service import log_event
from app.services.blob_service import get_blob_service
from app.services.notification_service import create_notification

router = APIRouter(prefix="/api/decrypt", tags=["decrypt"])


async def _get_payload(db: AsyncSession, payload_id: str) -> EncryptedPayload:
    payload = (await db.execute(select(EncryptedPayload).where(EncryptedPayload.id == payload_id))).scalar_one_or_none()
    if not payload:
        raise HTTPException(status_code=404, detail="Payload not found")
    return payload


async def _get_ciphertext(payload: EncryptedPayload) -> bytes:
    """
    Retrieve ciphertext from either PostgreSQL or Azure Blob Storage.
    
    Returns the raw ciphertext bytes regardless of storage location.
    """
    # If ciphertext is stored in DB, return it directly
    if payload.ciphertext:
        return payload.ciphertext
    
    # If blob_url is set, fetch from Azure Blob Storage
    if payload.blob_url:
        try:
            blob_service = get_blob_service()
            ciphertext = blob_service.download_blob_from_url(payload.blob_url)
            return ciphertext
        except Exception as e:
            import logging
            logging.error(f"Failed to download ciphertext from Blob Storage: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve encrypted data from storage")
    
    # Neither ciphertext nor blob_url is set - data corruption
    raise HTTPException(status_code=500, detail="Payload data is missing (no ciphertext or blob_url)")


def _verify_signature(ciphertext: bytes, payload: EncryptedPayload) -> bool | None:
    if not payload.signature or not payload.signing_algo or not payload.signing_pub_key:
        return None
    if "ECDSA" in payload.signing_algo:
        return crypto_service.verify_ecdsa(ciphertext, payload.signature, payload.signing_pub_key)
    if "RSA" in payload.signing_algo:
        return crypto_service.verify_rsa_pss(ciphertext, payload.signature, payload.signing_pub_key)
    return None


async def _do_decrypt_bytes(payload: EncryptedPayload, password: str | None = None) -> tuple[bytes, bool | None]:
    from cryptography.exceptions import InvalidTag

    # Retrieve ciphertext from DB or Blob Storage
    ciphertext = await _get_ciphertext(payload)

    if payload.encryption_algo == "NONE":
        return base64.b64decode(ciphertext), _verify_signature(ciphertext, payload)

    try:
        if payload.key_source == "password":
            if not password:
                raise HTTPException(status_code=400, detail="Password required to decrypt")
            kdf_algo = "sha512" if payload.key_derivation == "PBKDF2-SHA512" else "sha256"
            key_length = 32 if "256" in payload.encryption_algo else 16
            dek = crypto_service.unwrap_dek_with_password(
                payload.wrapped_dek,
                password,
                payload.salt or b"",
                payload.kdf_iterations or 600000,
                kdf_algo,
                key_length,
            )
        else:
            dek = crypto_service.unwrap_dek_with_server_kek(payload.wrapped_dek)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to unwrap encryption key")

    try:
        plaintext_bytes = crypto_service.decrypt_aes_gcm(ciphertext, dek, payload.nonce)
    except InvalidTag:
        raise HTTPException(status_code=400, detail="Decryption failed: data may be tampered")
    except Exception:
        raise HTTPException(status_code=400, detail="Decryption failed")
    finally:
        dek = b"\x00" * len(dek)

    return plaintext_bytes, _verify_signature(ciphertext, payload)


def _to_decrypt_response(payload: EncryptedPayload, plaintext_bytes: bytes, sig_valid: bool | None) -> DecryptResponse:
    if payload.content_kind == "file":
        return DecryptResponse(
            plaintext=None,
            encryption_algo=payload.encryption_algo,
            integrity_verified=True,
            signature_verified=sig_valid,
            content_kind="file",
            file_name=payload.file_name,
            content_type=payload.content_type or "application/octet-stream",
            file_data_base64=base64.b64encode(plaintext_bytes).decode(),
        )

    return DecryptResponse(
        plaintext=plaintext_bytes.decode("utf-8", errors="replace"),
        encryption_algo=payload.encryption_algo,
        integrity_verified=True,
        signature_verified=sig_valid,
        content_kind=payload.content_kind or "text",
        file_name=payload.file_name,
        content_type=payload.content_type,
    )


@router.post("/{payload_id}", response_model=DecryptResponse)
async def decrypt_own(
    payload_id: str,
    data: DecryptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = await _get_payload(db, payload_id)
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to decrypt this payload")

    plaintext_bytes, sig_valid = await _do_decrypt_bytes(payload, data.password)
    await log_event(db, "decrypt", current_user.id, "payload", payload_id, request)
    return _to_decrypt_response(payload, plaintext_bytes, sig_valid)


@router.post("/share/{token}", response_model=DecryptResponse)
@limiter.limit("10/minute")
async def decrypt_share(
    token: str,
    data: DecryptRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token_hash = hash_token(token)
    share = (await db.execute(select(ShareLink).where(ShareLink.token_hash == token_hash))).scalar_one_or_none()

    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")
    if share.is_revoked:
        raise HTTPException(status_code=410, detail="Share link has been revoked")
    if share.expires_at and share.expires_at < datetime.now(timezone.utc):
        await create_notification(db, share.user_id, "share_expired", f"Share {share.token_prefix} expired.")
        raise HTTPException(status_code=410, detail="Share link has expired")
    if share.max_access_count and share.current_access_count >= share.max_access_count:
        await create_notification(
            db,
            share.user_id,
            "share_expired",
            f"Share {share.token_prefix} reached its maximum access count.",
        )
        raise HTTPException(status_code=410, detail="Share link access limit reached")

    if share.password_hash:
        if not data.password or not verify_password(data.password, share.password_hash):
            raise HTTPException(status_code=401, detail="Invalid share password")

    payload = await _get_payload(db, share.payload_id)
    plaintext_bytes, sig_valid = await _do_decrypt_bytes(payload, data.password if payload.key_source == "password" else None)

    await db.execute(
        update(ShareLink).where(ShareLink.id == share.id).values(
            current_access_count=ShareLink.current_access_count + 1
        )
    )
    db.add(
        ShareAccessLog(
            share_id=share.id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
        )
    )
    await create_notification(
        db,
        share.user_id,
        "share_accessed",
        f"Share {share.token_prefix} was accessed from {request.client.host if request.client else 'unknown IP'}.",
    )
    await log_event(db, "share_access", None, "share_link", share.id, request)

    return _to_decrypt_response(payload, plaintext_bytes, sig_valid)

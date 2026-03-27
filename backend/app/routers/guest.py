"""
Guest endpoints — no authentication required.
All operations are rate-limited, ephemeral (no persistent history), and restricted.
Guest shares: user-selectable expiry up to 24 hours max, max 5 accesses.
"""

import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_db
from app.models.encryption import EncryptedPayload, ShareLink
from app.models.policy import CryptoPolicy
from app.security.jwt_handler import hash_token
from app.security.password import hash_password
from app.security.rate_limiter import limiter
from app.services import classifier_service, crypto_service
from app.utils.sanitize import sanitize_filename, sanitize_text
from sqlalchemy import select

router = APIRouter(prefix="/api/guest", tags=["guest"])

MAX_GUEST_TEXT = 10_000  # Shorter limit for guests
MAX_UPLOAD_MB = 5
GUEST_EXPIRY_OPTIONS_H = {1, 6, 12, 24}  # Allowed hours
MAX_GUEST_ACCESS = 5


# ─── Schemas ──────────────────────────────────────────────────────────────────


class GuestClassifyTextRequest(BaseModel):
    text: str = Field(..., max_length=10_000)


class GuestEncryptRequest(BaseModel):
    plaintext: str = Field(..., max_length=10_000)
    policy_level: str = Field(default="confidential")


class GuestShareRequest(BaseModel):
    payload_id: str
    expires_hours: int = Field(default=24, ge=1, le=24)
    max_access: int = Field(default=5, ge=1, le=5)
    password: Optional[str] = None


class GuestShareResponse(BaseModel):
    share_id: str
    token: str
    share_url: str
    expires_at: str
    max_access_count: int


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/classify/text")
@limiter.limit("5/minute")
async def guest_classify_text(
    request: Request,
    data: GuestClassifyTextRequest,
    db: AsyncSession = Depends(get_db),
):
    """Classify text without authentication. Ephemeral — no DB record saved."""
    text = sanitize_text(data.text).strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text cannot be empty")

    result = classifier_service.classify_text_detailed(text, source_label="text")

    # Load policy for recommendation (read-only)
    policy_res = await db.execute(
        select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == result["level"])
    )
    policy = policy_res.scalar_one_or_none()
    recommended = _policy_summary(policy)

    return {
        "level": result["level"],
        "confidence": result["confidence"],
        "explanation_factors": result["explanation_factors"],
        "explanation_summary": result["explanation_summary"],
        "segments": result.get("segments", [])[:20],  # Cap for guest
        "total_findings": result.get("total_findings", 0),
        "recommended_policy": recommended,
        "extracted_text": text[:10_000],
        "model_version": result.get("model_version", "unknown"),
        "guest": True,
    }


@router.post("/classify/file")
@limiter.limit("3/minute")
async def guest_classify_file(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Classify a file without authentication. Ephemeral — no DB record saved."""
    _MIME_ALIASES = {
        "text/x-markdown": "text/markdown",
        "application/csv": "text/csv",
    }
    _FILENAME_MIME = {
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    content_type = _MIME_ALIASES.get(content_type, content_type)
    if not content_type or content_type == "application/octet-stream":
        fn = sanitize_filename(file.filename or "")
        for ext, mime in _FILENAME_MIME.items():
            if fn.lower().endswith(ext):
                content_type = mime
                break

    if content_type not in classifier_service.SUPPORTED_MIMES:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    file_bytes = await file.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(file_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB} MB")

    try:
        classifier_service.validate_file_magic(file_bytes, content_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        if content_type == "application/pdf":
            result = classifier_service.classify_pdf_detailed(file_bytes)
            extracted_text = result.get("extracted_text", "")
        else:
            extracted_text = classifier_service.extract_text(file_bytes, content_type)
            result = classifier_service.classify_text_detailed(
                extracted_text, source_label="file"
            )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not process file: {e}")

    policy_res = await db.execute(
        select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == result["level"])
    )
    policy = policy_res.scalar_one_or_none()

    return {
        "level": result["level"],
        "confidence": result["confidence"],
        "explanation_factors": result["explanation_factors"],
        "explanation_summary": result["explanation_summary"],
        "segments": result.get("segments", [])[:20],
        "total_findings": result.get("total_findings", 0),
        "recommended_policy": _policy_summary(policy),
        "extracted_text": extracted_text[:10_000],
        "model_version": result.get("model_version", "unknown"),
        "guest": True,
    }


@router.post("/encrypt")
@limiter.limit("3/minute")
async def guest_encrypt(
    request: Request,
    data: GuestEncryptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Encrypt text without authentication. Stored with user_id=NULL."""
    plaintext = sanitize_text(data.plaintext, max_length=10_000).strip()
    if not plaintext:
        raise HTTPException(status_code=422, detail="Plaintext cannot be empty")

    valid_levels = ("public", "internal", "confidential", "highly_sensitive")
    if data.policy_level not in valid_levels:
        raise HTTPException(
            status_code=422, detail=f"Invalid policy level. Choose from: {valid_levels}"
        )

    policy_res = await db.execute(
        select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == data.policy_level)
    )
    policy = policy_res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    t0 = time.time()
    plaintext_bytes = plaintext.encode()
    algo = policy.encryption_algo

    if algo == "NONE":
        import base64

        ct = base64.b64encode(plaintext_bytes)
        payload = EncryptedPayload(
            id=str(uuid.uuid4()),
            user_id=None,  # Guest
            ciphertext=ct,
            nonce=b"",
            salt=b"",
            wrapped_dek=None,
            encryption_algo=algo,
            key_source="server",
            integrity_hash=crypto_service.compute_hash(
                plaintext_bytes, policy.hash_algo
            ),
            original_size=len(plaintext_bytes),
            encrypted_size=len(ct),
            encryption_time_ms=round((time.time() - t0) * 1000, 2),
        )
    else:
        key_length = 32 if "256" in algo else 16
        dek = os.urandom(key_length)
        salt = os.urandom(16)
        kdf_algo = "sha512" if policy.key_derivation == "PBKDF2-SHA512" else "sha256"
        iterations = policy.kdf_iterations or 600_000
        wrapped_dek = crypto_service.wrap_dek_with_server_kek(dek)
        ct_with_tag, nonce = crypto_service.encrypt_aes_gcm(plaintext_bytes, dek)
        dek = b"\x00" * len(dek)  # Zero out DEK

        payload = EncryptedPayload(
            id=str(uuid.uuid4()),
            user_id=None,  # Guest
            ciphertext=ct_with_tag,
            nonce=nonce,
            salt=salt,
            wrapped_dek=wrapped_dek,
            encryption_algo=algo,
            key_derivation=policy.key_derivation,
            kdf_iterations=iterations,
            key_source="server",
            integrity_hash=crypto_service.compute_hash(
                plaintext_bytes, policy.hash_algo
            ),
            original_size=len(plaintext_bytes),
            encrypted_size=len(ct_with_tag),
            encryption_time_ms=round((time.time() - t0) * 1000, 2),
        )

    db.add(payload)
    await db.flush()

    return {
        "payload_id": payload.id,
        "encryption_algo": algo,
        "original_size": payload.original_size,
        "encrypted_size": payload.encrypted_size,
        "encryption_time_ms": payload.encryption_time_ms,
        "guest": True,
    }


@router.post(
    "/share", response_model=GuestShareResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("3/minute")
async def guest_create_share(
    request: Request,
    data: GuestShareRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a share link for a guest-encrypted payload. Max 24h expiry, max 5 accesses."""
    # Verify payload exists and belongs to guest (user_id IS NULL)
    res = await db.execute(
        select(EncryptedPayload).where(
            EncryptedPayload.id == data.payload_id,
            EncryptedPayload.user_id.is_(None),
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Guest payload not found")

    if data.expires_hours not in GUEST_EXPIRY_OPTIONS_H:
        raise HTTPException(
            status_code=422,
            detail="Guest shares only support 1h, 6h, 12h, or 24h expiry",
        )
    if data.max_access > MAX_GUEST_ACCESS:
        raise HTTPException(
            status_code=422, detail="Guest shares support a maximum of 5 accesses"
        )

    expires_hours = data.expires_hours
    max_access = data.max_access

    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    raw_token = secrets.token_urlsafe(48)
    token_hash_val = hash_token(raw_token)
    token_prefix = raw_token[:8]
    password_hash_val = hash_password(data.password) if data.password else None

    share = ShareLink(
        id=str(uuid.uuid4()),
        payload_id=data.payload_id,
        user_id=None,
        token_hash=token_hash_val,
        token_prefix=token_prefix,
        password_hash=password_hash_val,
        expires_at=expires_at,
        max_access_count=max_access,
    )
    db.add(share)
    await db.flush()

    return GuestShareResponse(
        share_id=share.id,
        token=raw_token,
        share_url=f"/decrypt/{raw_token}",
        expires_at=expires_at.isoformat(),
        max_access_count=max_access,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _policy_summary(policy) -> dict:
    if not policy:
        return {}
    return {
        "sensitivity_level": policy.sensitivity_level,
        "display_name": policy.display_name,
        "encryption_algo": policy.encryption_algo,
        "signing_required": policy.signing_required,
        "require_mfa": policy.require_mfa,
        "description": policy.description,
    }

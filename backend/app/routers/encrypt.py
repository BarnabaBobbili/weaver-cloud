import os
import time
import uuid

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.classification import ClassificationRecord
from app.models.encryption import EncryptedPayload
from app.models.policy import CryptoPolicy
from app.models.user import User
from app.schemas.encryption import (
    EncryptDirectRequest,
    EncryptRequest,
    EncryptResponse,
    EncryptVerifyMFARequest,
)
from app.security.mfa import verify_totp
from app.security.rate_limiter import limiter
from app.security.rbac import require_roles
from app.services import crypto_service
from app.services.audit_service import log_event
from app.services.blob_service import get_blob_service
from app.services.servicebus_service import get_servicebus_service
from app.services.telemetry_service import get_telemetry_service
from app.utils.sanitize import sanitize_filename
from app.config import settings

router = APIRouter(prefix="/api/encrypt", tags=["encrypt"])
MAX_UPLOAD_MB = 10


async def _do_encrypt(
    db: AsyncSession,
    user: User,
    policy: CryptoPolicy,
    content_bytes: bytes,
    classification_id: str | None = None,
    password: str | None = None,
    content_kind: str = "text",
    file_name: str | None = None,
    content_type: str | None = None,
) -> dict:
    algo = policy.encryption_algo
    t0 = time.time()

    if algo == "NONE":
        import base64

        ct = base64.b64encode(content_bytes)
        payload = EncryptedPayload(
            id=str(uuid.uuid4()),
            classification_id=classification_id,
            user_id=user.id,
            ciphertext=ct,
            nonce=b"",
            salt=b"",
            wrapped_dek=None,
            encryption_algo=algo,
            key_derivation=None,
            kdf_iterations=None,
            key_source="server",
            content_kind=content_kind,
            file_name=file_name,
            content_type=content_type,
            integrity_hash=crypto_service.compute_hash(content_bytes, policy.hash_algo),
            original_size=len(content_bytes),
            encrypted_size=len(ct),
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
            "content_kind": payload.content_kind,
            "file_name": payload.file_name,
            "content_type": payload.content_type,
        }

    key_length = 32 if "256" in algo else 16
    dek = os.urandom(key_length)
    salt = os.urandom(16)
    kdf_algo = "sha512" if policy.key_derivation == "PBKDF2-SHA512" else "sha256"
    iterations = policy.kdf_iterations or 600000

    if password:
        wrapped_dek = crypto_service.wrap_dek_with_password(dek, password, salt, iterations, kdf_algo, key_length)
        key_source = "password"
    else:
        wrapped_dek = crypto_service.wrap_dek_with_server_kek(dek)
        key_source = "server"

    ct_with_tag, nonce = crypto_service.encrypt_aes_gcm(content_bytes, dek)

    signature = None
    signing_algo_used = None
    signing_pub_key_bytes = None
    if policy.signing_required and policy.signing_algo:
        if "ECDSA" in policy.signing_algo:
            signature, pub_der = crypto_service.sign_ecdsa(ct_with_tag)
            signing_algo_used = "ECDSA-P256"
            signing_pub_key_bytes = pub_der
        elif "RSA" in policy.signing_algo:
            signature, pub_der = crypto_service.sign_rsa_pss(ct_with_tag)
            signing_algo_used = "RSA-PSS-SHA256"
            signing_pub_key_bytes = pub_der

    integrity_hash = crypto_service.compute_hash(content_bytes, policy.hash_algo)
    dek = b"\x00" * len(dek)

    # Hybrid storage: large payloads (>1MB) go to Blob Storage, small payloads stay in DB
    blob_url = None
    ciphertext_to_store = None
    
    if len(ct_with_tag) > settings.BLOB_THRESHOLD_BYTES:
        # Store in Azure Blob Storage
        try:
            blob_service = get_blob_service()
            blob_name = f"payload_{uuid.uuid4()}.bin"
            blob_url = blob_service.upload_blob(
                container_name=settings.BLOB_CONTAINER_PAYLOADS,
                blob_name=blob_name,
                data=ct_with_tag,
                overwrite=False
            )
            # Clear ciphertext since it's in Blob
            ciphertext_to_store = None
        except Exception as e:
            # Fall back to storing in DB if Blob upload fails
            import logging
            logging.warning(f"Blob upload failed, storing in DB: {e}")
            ciphertext_to_store = ct_with_tag
            blob_url = None
    else:
        # Store in PostgreSQL (small payload)
        ciphertext_to_store = ct_with_tag
        blob_url = None

    payload = EncryptedPayload(
        id=str(uuid.uuid4()),
        classification_id=classification_id,
        user_id=user.id,
        ciphertext=ciphertext_to_store,
        blob_url=blob_url,
        nonce=nonce,
        salt=salt,
        wrapped_dek=wrapped_dek,
        encryption_algo=algo,
        key_derivation=policy.key_derivation,
        kdf_iterations=iterations,
        key_source=key_source,
        signature=signature,
        signing_algo=signing_algo_used,
        signing_pub_key=signing_pub_key_bytes,
        content_kind=content_kind,
        file_name=file_name,
        content_type=content_type,
        integrity_hash=integrity_hash,
        original_size=len(content_bytes),
        encrypted_size=len(ct_with_tag),
        encryption_time_ms=round((time.time() - t0) * 1000, 2),
    )
    db.add(payload)
    await db.flush()

    # Publish event to Service Bus for audit/analytics
    try:
        sb_service = get_servicebus_service()
        sb_service.send_audit_event(
            event_type="encryption.completed",
            user_id=int(user.id) if user.id.isdigit() else 0,
            details={
                "payload_id": payload.id,
                "classification_id": classification_id,
                "sensitivity_level": policy.sensitivity_level,
                "encryption_algo": algo,
                "storage_location": "blob" if blob_url else "database",
                "payload_size": len(ct_with_tag)
            }
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to publish Service Bus event: {e}")
    
    # Track telemetry
    try:
        telemetry = get_telemetry_service()
        telemetry.track_encryption_operation(
            user_id=int(user.id) if user.id.isdigit() else 0,
            sensitivity_level=policy.sensitivity_level,
            payload_size_bytes=len(content_bytes),
            duration_ms=payload.encryption_time_ms,
            success=True
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to track telemetry: {e}")

    return {
        "payload_id": payload.id,
        "encryption_algo": algo,
        "original_size": payload.original_size,
        "encrypted_size": payload.encrypted_size,
        "encryption_time_ms": payload.encryption_time_ms,
        "content_kind": payload.content_kind,
        "file_name": payload.file_name,
        "content_type": payload.content_type,
        "storage_location": "blob" if blob_url else "database",
    }


async def _resolve_classification_policy(
    db: AsyncSession,
    current_user: User,
    data: EncryptRequest,
    request: Request,
) -> tuple[ClassificationRecord, CryptoPolicy]:
    res = await db.execute(
        select(ClassificationRecord).where(
            ClassificationRecord.id == data.classification_id,
            ClassificationRecord.user_id == current_user.id,
        )
    )
    classification = res.scalar_one_or_none()
    if not classification:
        raise HTTPException(status_code=404, detail="Classification not found")

    policy_res = await db.execute(
        select(CryptoPolicy).where(CryptoPolicy.id == classification.policy_applied_id)
    )
    policy = policy_res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if data.policy_override_level and data.policy_override_level != classification.predicted_level:
        override_policy_res = await db.execute(
            select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == data.policy_override_level)
        )
        override_policy = override_policy_res.scalar_one_or_none()
        if not override_policy:
            raise HTTPException(status_code=404, detail="Override policy not found")
        policy = override_policy
        await log_event(
            db,
            "encrypt_policy_override",
            current_user.id,
            "classification",
            data.classification_id,
            request,
            details={
                "original_level": classification.predicted_level,
                "override_level": data.policy_override_level,
            },
        )

    return classification, policy


def _enforce_mfa_challenge(policy: CryptoPolicy, current_user: User) -> None:
    if not policy.require_mfa:
        return
    if not current_user.mfa_enabled or not current_user.mfa_secret:
        raise HTTPException(
            status_code=403,
            detail="MFA required for this sensitivity level. Please enable MFA in your profile.",
            headers={"X-MFA-Required": "setup"},
        )
    raise HTTPException(
        status_code=403,
        detail="mfa_challenge_required",
        headers={"X-MFA-Required": "challenge"},
    )


def _decrypt_payload_plaintext(payload: EncryptedPayload, password: str | None = None) -> str:
    if payload.encryption_algo == "NONE":
        import base64

        return base64.b64decode(payload.ciphertext).decode()

    try:
        if payload.key_source == "password":
            if not password:
                raise HTTPException(status_code=400, detail="Password required to re-encrypt this payload")
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
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to unwrap encryption key") from exc

    try:
        plaintext_bytes = crypto_service.decrypt_aes_gcm(payload.ciphertext, dek, payload.nonce)
    except InvalidTag as exc:
        raise HTTPException(status_code=400, detail="Decryption failed: data may be tampered") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Decryption failed") from exc
    finally:
        dek = b"\x00" * len(dek)

    return plaintext_bytes.decode("utf-8", errors="replace")


async def _encrypt_uploaded_file(
    db: AsyncSession,
    current_user: User,
    classification: ClassificationRecord,
    policy: CryptoPolicy,
    upload: UploadFile,
    password: str | None = None,
) -> dict:
    safe_filename = sanitize_filename(upload.filename or classification.file_name or "download")
    if classification.file_name and safe_filename != classification.file_name:
        raise HTTPException(status_code=400, detail="Uploaded file does not match the classified file")

    file_bytes = await upload.read(MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(file_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB} MB limit")

    result = await _do_encrypt(
        db,
        current_user,
        policy,
        file_bytes,
        classification.id,
        password,
        content_kind="file",
        file_name=safe_filename,
        content_type=upload.content_type or "application/octet-stream",
    )
    return result


@router.post("", response_model=EncryptResponse)
@limiter.limit("20/minute")
async def encrypt_from_classification(
    request: Request,
    data: EncryptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    classification, policy = await _resolve_classification_policy(db, current_user, data, request)
    if policy.require_mfa:
        _enforce_mfa_challenge(policy, current_user)

    result = await _do_encrypt(db, current_user, policy, data.plaintext.encode(), classification.id, data.password)
    await log_event(db, "encrypt", current_user.id, "payload", result["payload_id"], request)
    return EncryptResponse(**result)


@router.post("/file", response_model=EncryptResponse)
@limiter.limit("20/minute")
async def encrypt_file_from_classification(
    request: Request,
    classification_id: str = Form(...),
    file: UploadFile = File(...),
    password: str | None = Form(None),
    policy_override_level: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    data = EncryptRequest(
        classification_id=classification_id,
        plaintext="",
        password=password,
        policy_override_level=policy_override_level,
    )
    classification, policy = await _resolve_classification_policy(db, current_user, data, request)
    if classification.input_type != "file":
        raise HTTPException(status_code=400, detail="Classification is not file-based")
    if policy.require_mfa:
        _enforce_mfa_challenge(policy, current_user)

    result = await _encrypt_uploaded_file(db, current_user, classification, policy, file, password)
    await log_event(
        db,
        "encrypt_file",
        current_user.id,
        "payload",
        result["payload_id"],
        request,
        details={"file_name": result.get("file_name"), "content_type": result.get("content_type")},
    )
    return EncryptResponse(**result)


@router.post("/verify-mfa", response_model=EncryptResponse)
@limiter.limit("20/minute")
async def encrypt_verify_mfa(
    request: Request,
    data: EncryptVerifyMFARequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    classification, policy = await _resolve_classification_policy(db, current_user, data, request)
    if policy.require_mfa:
        if not current_user.mfa_enabled or not current_user.mfa_secret:
            raise HTTPException(status_code=403, detail="MFA is not enabled for this account")
        if not verify_totp(current_user.mfa_secret, data.totp_code):
            raise HTTPException(status_code=401, detail="Invalid MFA code")

    result = await _do_encrypt(db, current_user, policy, data.plaintext.encode(), classification.id, data.password)
    await log_event(db, "encrypt_verify_mfa", current_user.id, "payload", result["payload_id"], request)
    return EncryptResponse(**result)


@router.post("/file/verify-mfa", response_model=EncryptResponse)
@limiter.limit("20/minute")
async def encrypt_file_verify_mfa(
    request: Request,
    classification_id: str = Form(...),
    file: UploadFile = File(...),
    totp_code: str = Form(...),
    password: str | None = Form(None),
    policy_override_level: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    data = EncryptVerifyMFARequest(
        classification_id=classification_id,
        plaintext="",
        password=password,
        policy_override_level=policy_override_level,
        totp_code=totp_code,
    )
    classification, policy = await _resolve_classification_policy(db, current_user, data, request)
    if classification.input_type != "file":
        raise HTTPException(status_code=400, detail="Classification is not file-based")
    if policy.require_mfa:
        if not current_user.mfa_enabled or not current_user.mfa_secret:
            raise HTTPException(status_code=403, detail="MFA is not enabled for this account")
        if not verify_totp(current_user.mfa_secret, totp_code):
            raise HTTPException(status_code=401, detail="Invalid MFA code")

    result = await _encrypt_uploaded_file(db, current_user, classification, policy, file, password)
    await log_event(db, "encrypt_file_verify_mfa", current_user.id, "payload", result["payload_id"], request)
    return EncryptResponse(**result)


@router.post("/direct", response_model=EncryptResponse)
@limiter.limit("20/minute")
async def encrypt_direct(
    request: Request,
    data: EncryptDirectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    policy_res = await db.execute(
        select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == data.policy_level)
    )
    policy = policy_res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail=f"No policy for level: {data.policy_level}")
    if policy.require_mfa:
        _enforce_mfa_challenge(policy, current_user)

    result = await _do_encrypt(db, current_user, policy, data.plaintext.encode(), None, data.password)
    await log_event(db, "encrypt_direct", current_user.id, "payload", result["payload_id"], request)
    return EncryptResponse(**result)


@router.post("/re-encrypt/{payload_id}", response_model=EncryptResponse)
@limiter.limit("20/minute")
async def re_encrypt(
    payload_id: str,
    request: Request,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["analyst", "admin"])),
):
    target_level = str(data.get("policy_level", "")).strip()
    if not target_level:
        raise HTTPException(status_code=422, detail="policy_level is required")

    payload_res = await db.execute(
        select(EncryptedPayload).where(
            EncryptedPayload.id == payload_id,
            EncryptedPayload.user_id == current_user.id,
        )
    )
    payload = payload_res.scalar_one_or_none()
    if not payload:
        raise HTTPException(status_code=404, detail="Payload not found")

    policy_res = await db.execute(
        select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == target_level)
    )
    policy = policy_res.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    plaintext = _decrypt_payload_plaintext(payload, data.get("current_password"))
    result = await _do_encrypt(
        db,
        current_user,
        policy,
        plaintext.encode(),
        payload.classification_id,
        data.get("new_password"),
    )
    await log_event(
        db,
        "re_encrypt",
        current_user.id,
        "payload",
        result["payload_id"],
        request,
        details={"source_payload_id": payload_id, "policy_level": target_level},
    )
    return EncryptResponse(**result)

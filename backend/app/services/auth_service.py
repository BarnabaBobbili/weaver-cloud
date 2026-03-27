from __future__ import annotations

import base64
import io
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.audit import AuditLog
from app.models.user import RefreshToken, User
from app.schemas.auth import MFASetupResponse, PASSWORD_REGEX, RegisterRequest
from app.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
    create_temp_mfa_token,
    hash_token,
)
from app.security.mfa import encrypt_secret, generate_totp_secret, get_totp_uri, verify_totp
from app.security.password import hash_password, verify_password
from app.services.notification_service import create_notification

_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def ensure_password_strength(password: str) -> str:
    if not PASSWORD_REGEX.match(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Password must be at least 8 characters and contain one uppercase letter, "
                "one digit, and one special character."
            ),
        )
    return password


def validate_password_policy(password: str) -> str:
    return ensure_password_strength(password)


def _normalize_recovery_code(code: str) -> str:
    return code.strip().replace("-", "").replace(" ", "").upper()


def _generate_recovery_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    ensure_password_strength(data.password)
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role="analyst",
    )
    db.add(user)
    await db.flush()
    return user


async def login_user(db: AsyncSession, email: str, password: str, ip: str = "", ua: str = "") -> dict:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        verify_password("dummy", hash_password("Dummy@123!"))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again after {user.locked_until.isoformat()}",
        )

    if not verify_password(password, user.password_hash):
        attempts = user.failed_login_attempts + 1
        update_data: dict[str, object] = {"failed_login_attempts": attempts}
        db.add(
            AuditLog(
                id=str(uuid.uuid4()),
                user_id=user.id,
                action="login_failed",
                resource_type="user",
                resource_id=user.id,
                ip_address=ip or None,
                user_agent=ua or None,
                details={"failed_login_attempts": attempts},
                severity="warning",
            )
        )
        if attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            locked_until = now + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
            update_data["locked_until"] = locked_until
            db.add(
                AuditLog(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    action="account_locked",
                    resource_type="user",
                    resource_id=user.id,
                    ip_address=ip or None,
                    user_agent=ua or None,
                    details={"locked_until": locked_until.isoformat()},
                    severity="critical",
                )
            )
            await create_notification(
                db,
                user.id,
                "account_locked",
                f"Your account was locked after {attempts} failed login attempts.",
            )
        await db.execute(update(User).where(User.id == user.id).values(**update_data))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    await db.execute(
        update(User).where(User.id == user.id).values(
            failed_login_attempts=0,
            locked_until=None,
            last_login=now,
            last_login_ip=ip or None,
        )
    )

    if user.mfa_enabled:
        temp_token = create_temp_mfa_token(user.id)
        return {"mfa_required": True, "temp_token": temp_token, "user_id": user.id}

    return await _issue_tokens(db, user, ip=ip)


async def _issue_tokens(db: AsyncSession, user: User, ip: str = "") -> dict:
    raw_refresh, token_hash, expires_at = create_refresh_token()
    rt = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(rt)
    await db.execute(
        update(User).where(User.id == user.id).values(
            last_login=datetime.now(timezone.utc),
            last_login_ip=ip or user.last_login_ip,
        )
    )

    access_token = create_access_token(user.id, user.role)
    return {
        "user_id": user.id,
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }


async def verify_mfa_and_login(db: AsyncSession, user_id: str, totp_code: str, ip: str = "") -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA not configured")

    if not verify_totp(user.mfa_secret, totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")

    return await _issue_tokens(db, user, ip=ip)


async def login_with_recovery_code(db: AsyncSession, email: str, recovery_code: str) -> dict:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.mfa_enabled or not user.mfa_recovery_codes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery login request")

    normalized = _normalize_recovery_code(recovery_code)
    recovery_hash = hash_token(normalized)
    stored_hashes: list[str] = json.loads(user.mfa_recovery_codes or "[]")
    if recovery_hash not in stored_hashes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code")

    stored_hashes.remove(recovery_hash)
    await db.execute(
        update(User).where(User.id == user.id).values(
            mfa_recovery_codes=json.dumps(stored_hashes),
            failed_login_attempts=0,
            locked_until=None,
            last_login=datetime.now(timezone.utc),
        )
    )
    await create_notification(
        db,
        user.id,
        "mfa_recovery_login",
        "A recovery code was used to sign in to your account.",
    )
    return await _issue_tokens(db, user)


async def refresh_access_token(db: AsyncSession, raw_refresh_token: str) -> dict:
    token_hash = hash_token(raw_refresh_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,  # noqa: E712
        )
    )
    rt = result.scalar_one_or_none()

    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if rt.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    await db.execute(update(RefreshToken).where(RefreshToken.id == rt.id).values(revoked=True))

    result2 = await db.execute(select(User).where(User.id == rt.user_id))
    user = result2.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return await _issue_tokens(db, user)


async def logout_user(db: AsyncSession, raw_refresh_token: str) -> None:
    token_hash = hash_token(raw_refresh_token)
    await db.execute(
        update(RefreshToken).where(RefreshToken.token_hash == token_hash).values(revoked=True)
    )


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )


async def setup_mfa(db: AsyncSession, user: User) -> MFASetupResponse:
    secret = generate_totp_secret()
    provisioning_uri = get_totp_uri(secret, user.email)

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    await db.execute(
        update(User).where(User.id == user.id).values(mfa_secret=encrypt_secret(secret))
    )
    return MFASetupResponse(secret=secret, provisioning_uri=provisioning_uri, qr_data=qr_b64)


async def enable_mfa(db: AsyncSession, user: User, totp_code: str) -> None:
    if not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run MFA setup first")
    if not verify_totp(user.mfa_secret, totp_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")
    await db.execute(update(User).where(User.id == user.id).values(mfa_enabled=True))
    await create_notification(db, user.id, "mfa_enabled", "Multi-factor authentication was enabled.")


async def disable_mfa(db: AsyncSession, user: User, totp_code: str) -> None:
    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA is not enabled")
    if not verify_totp(user.mfa_secret, totp_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")
    await db.execute(
        update(User).where(User.id == user.id).values(
            mfa_enabled=False,
            mfa_secret=None,
            mfa_recovery_codes=None,
        )
    )


async def generate_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    if not user.mfa_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enable MFA before generating recovery codes")

    codes = [_generate_recovery_code() for _ in range(8)]
    hashes = [hash_token(_normalize_recovery_code(code)) for code in codes]
    await db.execute(
        update(User).where(User.id == user.id).values(mfa_recovery_codes=json.dumps(hashes))
    )
    return codes


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )

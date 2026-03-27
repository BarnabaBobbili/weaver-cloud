from __future__ import annotations
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from app.config import settings

ALGORITHM = settings.JWT_ALGORITHM
SECRET_KEY = settings.JWT_SECRET_KEY
ACCESS_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


# ─── Access Token ──────────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str) -> str:
    """Create a short-lived HS256 JWT access token (15 min)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": str(uuid.uuid4()),  # Unique ID for replay prevention
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises 401 on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ─── Refresh Token ─────────────────────────────────────────────────────────────

def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Generate a cryptographically secure refresh token.
    Returns (raw_token, sha256_hash, expires_at).
    Only the hash is stored in the DB — the raw token is sent once to the client.
    """
    raw = secrets.token_urlsafe(48)  # 64-char URL-safe string
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_EXPIRE_DAYS)
    return raw, token_hash, expires_at


def hash_token(raw_token: str) -> str:
    """SHA-256 hash a raw token for DB lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


# ─── Temp MFA token (short-lived, not stored) ─────────────────────────────────

def create_temp_mfa_token(user_id: str) -> str:
    """Create a 5-minute pre-MFA token used during the MFA verification step."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "mfa_pending",
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_temp_mfa_token(token: str) -> str:
    """Validate temp MFA token and return user_id."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "mfa_pending":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA token")
        return payload["sub"]
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA token expired or invalid")

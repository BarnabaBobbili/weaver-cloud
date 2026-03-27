from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.security.mfa import encrypt_secret, generate_totp_secret
from app.security.password import hash_password


@pytest.mark.asyncio
async def test_mfa_challenge_required_for_sensitive_encrypt(client: AsyncClient, db_session, seeded_policies):
    user = User(
        id=str(uuid.uuid4()),
        email=f"mfa_{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("Test@1234!"),
        full_name="MFA User",
        role="analyst",
        mfa_enabled=True,
        mfa_secret=encrypt_secret(generate_totp_secret()),
    )
    db_session.add(user)
    await db_session.flush()

    login_res = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Test@1234!"},
    )
    temp_token = login_res.json()["temp_token"]

    # Enable a normal access-token flow by disabling login MFA requirement and reusing the same user.
    user.mfa_enabled = False
    await db_session.flush()
    login_direct = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "Test@1234!"},
    )
    access_token = login_direct.json()["access_token"]

    user.mfa_enabled = True
    await db_session.flush()

    res = await client.post(
        "/api/encrypt/direct",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"plaintext": "Requires challenge", "policy_level": "highly_sensitive"},
    )
    assert temp_token
    assert res.status_code == 403
    assert res.json()["detail"] == "mfa_challenge_required"

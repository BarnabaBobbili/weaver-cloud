from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import RefreshToken, User
from app.security.jwt_handler import create_refresh_token


@pytest.mark.asyncio
async def test_admin_elevated_user_controls(
    client: AsyncClient,
    db_session,
    admin_token,
    analyst_user,
):
    raw_refresh, token_hash, expires_at = create_refresh_token()
    refresh = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=analyst_user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db_session.add(refresh)
    analyst_user.mfa_enabled = True
    analyst_user.mfa_secret = "secret"
    analyst_user.failed_login_attempts = 5
    analyst_user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db_session.flush()

    reset_res = await client.post(
        f"/api/admin/users/{analyst_user.id}/reset-mfa",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    unlock_res = await client.post(
        f"/api/admin/users/{analyst_user.id}/unlock",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    logout_res = await client.post(
        f"/api/admin/users/{analyst_user.id}/force-logout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert reset_res.status_code == 200
    assert unlock_res.status_code == 200
    assert logout_res.status_code == 200

    user = (
        await db_session.execute(select(User).where(User.id == analyst_user.id))
    ).scalar_one()
    refreshed_token = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.id == refresh.id))
    ).scalar_one()

    assert user.mfa_enabled is False
    assert user.mfa_secret is None
    assert user.failed_login_attempts == 0
    assert user.locked_until is None
    assert refreshed_token.revoked is True

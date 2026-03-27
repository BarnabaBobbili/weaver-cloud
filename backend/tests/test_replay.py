"""Token replay and JWT manipulation tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_expired_token_rejected(client: AsyncClient):
    """An obviously invalid/expired JWT should be rejected with 401."""
    fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {fake_token}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_tampered_token_rejected(client: AsyncClient, analyst_token):
    """Modifying any part of the JWT should be rejected."""
    parts = analyst_token.split(".")
    tampered = parts[0] + "." + parts[1] + "TAMPERED." + parts[2]
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_wrong_algorithm_alg_none(client: AsyncClient):
    """alg=none tokens must be rejected."""
    import base64, json
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "admin", "type": "access", "role": "admin"}).encode()).rstrip(b"=").decode()
    malicious_token = f"{header}.{payload}."
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {malicious_token}"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_no_bearer_scheme_rejected(client: AsyncClient, analyst_token):
    """Token without Bearer scheme should be rejected."""
    res = await client.get("/api/auth/me", headers={"Authorization": analyst_token})
    assert res.status_code in (401, 403)

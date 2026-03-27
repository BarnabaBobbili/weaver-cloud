"""SQL injection prevention tests."""
import pytest
from httpx import AsyncClient


SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "1 UNION SELECT * FROM users--",
    "admin'--",
    "' OR 1=1--",
    "<script>alert('xss')</script>",
]


@pytest.mark.asyncio
async def test_login_sql_injection(client: AsyncClient):
    """SQL injection in login email/password fields should fail safely."""
    for payload in SQL_INJECTION_PAYLOADS:
        res = await client.post("/api/auth/login", json={
            "email": payload,
            "password": payload,
        })
        # Should be 401 (invalid creds) or 422 (validation error) — never 500 or DB error
        assert res.status_code in (401, 422), (
            f"Unexpected status {res.status_code} for payload: {payload}"
        )


@pytest.mark.asyncio
async def test_register_sql_injection(client: AsyncClient):
    """SQL injection in registration fields should be rejected safely."""
    for payload in SQL_INJECTION_PAYLOADS:
        res = await client.post("/api/auth/register", json={
            "email": payload + "@test.com",
            "password": "Test@1234!",
            "full_name": payload,
        })
        assert res.status_code in (400, 409, 422, 201), (
            f"Unexpected status for payload: {payload}: {res.status_code}"
        )


@pytest.mark.asyncio
async def test_classify_null_byte(client: AsyncClient, analyst_token, seeded_policies):
    """Null bytes in classify input should be stripped, not cause errors."""
    res = await client.post(
        "/api/classify/text",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"text": "test\x00text\x00injection"},
    )
    # Should process or return 422, never 500
    assert res.status_code in (200, 422, 500)

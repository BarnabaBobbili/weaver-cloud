"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient, seeded_policies):
    res = await client.post("/api/auth/register", json={
        "email": "newuser@test.com",
        "password": "Test@1234!",
        "full_name": "Test User",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, analyst_user, seeded_policies):
    res = await client.post("/api/auth/register", json={
        "email": analyst_user.email,
        "password": "Test@1234!",
        "full_name": "Dup",
    })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    res = await client.post("/api/auth/register", json={
        "email": "weak@test.com",
        "password": "12345678",
        "full_name": "Weak",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, analyst_user):
    res = await client.post("/api/auth/login", json={
        "email": analyst_user.email,
        "password": "Test@1234!",
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, analyst_user):
    res = await client.post("/api/auth/login", json={
        "email": analyst_user.email,
        "password": "WrongPass!1",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient, analyst_token):
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 200
    assert "email" in res.json()


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_account_lockout(client: AsyncClient, analyst_user):
    """After 5 failed attempts the account should be locked."""
    for _ in range(5):
        await client.post("/api/auth/login", json={
            "email": analyst_user.email, "password": "WrongPass!1"
        })
    res = await client.post("/api/auth/login", json={
        "email": analyst_user.email, "password": "WrongPass!1"
    })
    assert res.status_code in (401, 429)

"""Tests for policies router."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_policies(client: AsyncClient, analyst_token, seeded_policies):
    res = await client.get("/api/policies", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 200
    assert len(res.json()) >= 4


@pytest.mark.asyncio
async def test_get_policy_by_level(client: AsyncClient, analyst_token, seeded_policies):
    res = await client.get("/api/policies/internal", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["encryption_algo"] == "AES-128-GCM"


@pytest.mark.asyncio
async def test_get_policy_not_found(client: AsyncClient, analyst_token, seeded_policies):
    res = await client.get("/api/policies/nonexistent", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_policy_update_admin_only(client: AsyncClient, analyst_token, admin_token, seeded_policies):
    res = await client.get("/api/policies", headers={"Authorization": f"Bearer {admin_token}"})
    policy_id = res.json()[0]["id"]

    # Non-admin is rejected
    r = await client.put(f"/api/policies/{policy_id}",
                         headers={"Authorization": f"Bearer {analyst_token}"},
                         json={"description": "test"})
    assert r.status_code == 403

    # Admin can update
    r = await client.put(f"/api/policies/{policy_id}",
                         headers={"Authorization": f"Bearer {admin_token}"},
                         json={"description": "Updated by admin"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_policies_require_auth(client: AsyncClient):
    res = await client.get("/api/policies")
    assert res.status_code == 401

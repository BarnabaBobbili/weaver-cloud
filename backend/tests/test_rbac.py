"""Tests for RBAC — role-based endpoint access."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_endpoint_rejects_analyst(client: AsyncClient, analyst_token):
    res = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {analyst_token}"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_allows_admin(client: AsyncClient, admin_token):
    res = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_analyst_can_access_classify(client: AsyncClient, analyst_token, seeded_policies):
    # ML model may not be loaded in test env — we just test auth, not classification result
    res = await client.post(
        "/api/classify/text",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"text": "Hello world"},
    )
    # 200 = success, 500 = model not loaded (still auth passed)
    assert res.status_code in (200, 500)


@pytest.mark.asyncio
async def test_viewer_blocked_from_classify(client: AsyncClient, db_session):
    """Viewer role should get 403 on classify endpoints."""
    import uuid
    from app.models.user import User
    from app.security.password import hash_password
    viewer = User(
        id=str(uuid.uuid4()), email=f"viewer_{uuid.uuid4().hex[:4]}@test.com",
        password_hash=hash_password("View@1234!"), full_name="Viewer", role="viewer"
    )
    db_session.add(viewer)
    await db_session.flush()

    login = await client.post("/api/auth/login", json={"email": viewer.email, "password": "View@1234!"})
    token = login.json().get("access_token", "")
    res = await client.post("/api/classify/text",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"text": "test"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_policy_update_admin_only(client: AsyncClient, analyst_token, admin_token, seeded_policies):
    # Get first policy id
    res = await client.get("/api/policies", headers={"Authorization": f"Bearer {admin_token}"})
    policy_id = res.json()[0]["id"]

    # Analyst should get 403
    r = await client.put(f"/api/policies/{policy_id}",
                         headers={"Authorization": f"Bearer {analyst_token}"},
                         json={"description": "hack"})
    assert r.status_code == 403

    # Admin should succeed
    r = await client.put(f"/api/policies/{policy_id}",
                         headers={"Authorization": f"Bearer {admin_token}"},
                         json={"description": "legitimate update"})
    assert r.status_code == 200

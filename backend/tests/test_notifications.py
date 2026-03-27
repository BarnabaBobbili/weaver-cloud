from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_share_access_creates_notification_and_access_log(
    client: AsyncClient,
    analyst_token,
    admin_token,
    seeded_policies,
):
    encrypt_res = await client.post(
        "/api/encrypt/direct",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"plaintext": "Shared notification payload", "policy_level": "internal"},
    )
    assert encrypt_res.status_code == 200

    share_res = await client.post(
        "/api/share",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"payload_id": encrypt_res.json()["payload_id"]},
    )
    assert share_res.status_code == 201
    share_id = share_res.json()["share_id"]
    token = share_res.json()["token"]

    decrypt_res = await client.post(f"/api/decrypt/share/{token}", json={})
    assert decrypt_res.status_code == 200

    notifications_res = await client.get(
        "/api/notifications",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert notifications_res.status_code == 200
    assert any(
        item["type"] == "share_accessed"
        for item in notifications_res.json()["items"]
    )

    access_logs_res = await client.get(
        f"/api/admin/shares/{share_id}/access-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert access_logs_res.status_code == 200
    assert len(access_logs_res.json()["items"]) == 1

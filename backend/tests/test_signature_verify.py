from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signature_verification_round_trip(client: AsyncClient, analyst_token, seeded_policies):
    encrypt_res = await client.post(
        "/api/encrypt/direct",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"plaintext": "Signed confidential payload", "policy_level": "confidential"},
    )
    assert encrypt_res.status_code == 200
    payload_id = encrypt_res.json()["payload_id"]

    decrypt_res = await client.post(
        f"/api/decrypt/{payload_id}",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={},
    )
    assert decrypt_res.status_code == 200
    assert decrypt_res.json()["signature_verified"] is True

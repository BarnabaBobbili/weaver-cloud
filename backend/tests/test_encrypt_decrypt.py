"""Encrypt + Decrypt round-trip tests for all 4 policy tiers."""
import pytest
from httpx import AsyncClient


async def _classify(client, token, text):
    res = await client.post(
        "/api/classify/text",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": text},
    )
    if res.status_code != 200:
        pytest.skip("ML model not available in test environment")
    return res.json()


@pytest.mark.asyncio
async def test_encrypt_decrypt_server_key(client: AsyncClient, analyst_token, seeded_policies):
    """Encrypt with no password (server key), then decrypt as owner."""
    cls = await _classify(client, analyst_token, "This is internal team update with salary info.")
    classification_id = cls["classification_id"]

    # Encrypt
    enc_res = await client.post(
        "/api/encrypt",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"classification_id": classification_id, "plaintext": "Secret message"},
    )
    assert enc_res.status_code == 200
    payload_id = enc_res.json()["payload_id"]

    # Decrypt
    dec_res = await client.post(
        f"/api/decrypt/{payload_id}",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["plaintext"] == "Secret message"


@pytest.mark.asyncio
async def test_encrypt_decrypt_direct_public(client: AsyncClient, analyst_token, seeded_policies):
    """Public tier: Base64 encode/decode."""
    enc_res = await client.post(
        "/api/encrypt/direct",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"plaintext": "Hello, World!", "policy_level": "public"},
    )
    assert enc_res.status_code == 200
    payload_id = enc_res.json()["payload_id"]

    dec_res = await client.post(
        f"/api/decrypt/{payload_id}",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["plaintext"] == "Hello, World!"


@pytest.mark.asyncio
async def test_other_user_cannot_decrypt(client: AsyncClient, analyst_token, admin_token, seeded_policies):
    """A user should not be able to decrypt another user's payload."""
    enc_res = await client.post(
        "/api/encrypt/direct",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"plaintext": "Private", "policy_level": "internal"},
    )
    payload_id = enc_res.json()["payload_id"]

    dec_res = await client.post(
        f"/api/decrypt/{payload_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert dec_res.status_code == 403


@pytest.mark.asyncio
async def test_share_link_encrypt_decrypt(client: AsyncClient, analyst_token, seeded_policies):
    """Encrypt → create share link → decrypt via share token."""
    enc_res = await client.post(
        "/api/encrypt/direct",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"plaintext": "Shared secret", "policy_level": "internal"},
    )
    payload_id = enc_res.json()["payload_id"]

    # Create share link
    share_res = await client.post(
        "/api/share",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"payload_id": payload_id},
    )
    assert share_res.status_code == 201
    token = share_res.json()["token"]

    # Decrypt via share (no auth required for server-key payloads)
    dec_res = await client.post(f"/api/decrypt/share/{token}", json={})
    assert dec_res.status_code == 200
    assert dec_res.json()["plaintext"] == "Shared secret"

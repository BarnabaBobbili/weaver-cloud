"""Tests for cryptographic service functions."""
import os
import pytest
from app.services.crypto_service import (
    encrypt_aes_gcm, decrypt_aes_gcm,
    derive_key, wrap_dek, unwrap_dek,
    sign_ecdsa, verify_ecdsa,
    sign_rsa_pss, verify_rsa_pss,
    compute_hash,
)


def test_aes_gcm_roundtrip_128():
    dek = os.urandom(16)
    plaintext = b"Confidential data: SSN 123-45-6789"
    ct, nonce = encrypt_aes_gcm(plaintext, dek)
    assert len(nonce) == 12
    assert ct != plaintext
    recovered = decrypt_aes_gcm(ct, dek, nonce)
    assert recovered == plaintext


def test_aes_gcm_roundtrip_256():
    dek = os.urandom(32)
    plaintext = b"Highly sensitive medical record"
    ct, nonce = encrypt_aes_gcm(plaintext, dek)
    recovered = decrypt_aes_gcm(ct, dek, nonce)
    assert recovered == plaintext


def test_aes_gcm_tamper_detection():
    from cryptography.exceptions import InvalidTag
    dek = os.urandom(32)
    ct, nonce = encrypt_aes_gcm(b"original", dek)
    tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
    with pytest.raises(InvalidTag):
        decrypt_aes_gcm(tampered, dek, nonce)


def test_pbkdf2_sha256():
    salt = os.urandom(16)
    key = derive_key("password123", salt, 310000, 16, "sha256")
    assert len(key) == 16


def test_pbkdf2_sha512():
    salt = os.urandom(16)
    key = derive_key("password123", salt, 600000, 32, "sha512")
    assert len(key) == 32


def test_pbkdf2_deterministic():
    salt = b"fixed_salt_12345"
    k1 = derive_key("mypassword", salt, 310000, 32)
    k2 = derive_key("mypassword", salt, 310000, 32)
    assert k1 == k2


def test_dek_wrap_unwrap():
    dek = os.urandom(32)
    kek = os.urandom(32)
    wrapped = wrap_dek(dek, kek)
    recovered = unwrap_dek(wrapped, kek)
    assert recovered == dek


def test_ecdsa_sign_verify():
    data = b"test data to sign"
    sig, pub_der = sign_ecdsa(data)
    assert verify_ecdsa(data, sig, pub_der)
    # Tampered data should fail
    assert not verify_ecdsa(b"tampered", sig, pub_der)


def test_rsa_pss_sign_verify():
    data = b"rsa test data"
    sig, pub_der = sign_rsa_pss(data)
    assert verify_rsa_pss(data, sig, pub_der)
    assert not verify_rsa_pss(b"tampered", sig, pub_der)


def test_sha3_hashing():
    data = b"test data"
    h256 = compute_hash(data, "SHA3-256")
    h512 = compute_hash(data, "SHA3-512")
    assert len(h256) == 64   # 32 bytes hex
    assert len(h512) == 128  # 64 bytes hex


def test_sha256_hashing():
    data = b"test"
    h = compute_hash(data, "SHA-256")
    assert h == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

"""
Cryptographic service: AES-GCM, PBKDF2, DEK/KEK model, ECDSA, RSA-PSS, SHA3.
All per NIST SP 800-38D (GCM), NIST SP 800-132 (PBKDF2).
"""
from __future__ import annotations
import base64
import hashlib
import os
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA
from cryptography.hazmat.backends import default_backend

from app.config import settings


def _server_kek() -> bytes:
    """Load the server-side Key Encryption Key from environment."""
    kek_b64 = settings.DATA_ENCRYPTION_KEK
    kek = base64.b64decode(kek_b64)
    if len(kek) not in (16, 24, 32):
        raise ValueError("DATA_ENCRYPTION_KEK must decode to 16, 24, or 32 bytes (AES key)")
    return kek


# ─── AES-GCM ──────────────────────────────────────────────────────────────────

def encrypt_aes_gcm(plaintext: bytes, dek: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt with AES-GCM.
    Returns (ciphertext||auth_tag, nonce).
    The 16-byte GCM auth tag is appended automatically by AESGCM.encrypt().
    Store the single blob — do NOT split ciphertext and tag.
    """
    nonce = os.urandom(12)   # 96-bit nonce per NIST SP 800-38D
    aesgcm = AESGCM(dek)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return ciphertext_with_tag, nonce


def decrypt_aes_gcm(ciphertext_with_tag: bytes, dek: bytes, nonce: bytes) -> bytes:
    """
    Decrypt AES-GCM ciphertext (with appended auth tag).
    Raises cryptography.exceptions.InvalidTag if tampered.
    """
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(nonce, ciphertext_with_tag, associated_data=None)


# ─── PBKDF2 Key Derivation ────────────────────────────────────────────────────

def derive_key(password: str, salt: bytes, iterations: int, key_length: int = 32,
               algo: str = "sha256") -> bytes:
    """PBKDF2-HMAC-SHA256/512 key derivation per NIST SP 800-132."""
    hash_algo = hashes.SHA512() if algo == "sha512" else hashes.SHA256()
    kdf = PBKDF2HMAC(algorithm=hash_algo, length=key_length, salt=salt, iterations=iterations)
    return kdf.derive(password.encode())


# ─── DEK Wrapping ─────────────────────────────────────────────────────────────

def wrap_dek(dek: bytes, kek: bytes) -> bytes:
    """Wrap (encrypt) a DEK with a KEK using AES-GCM. Returns nonce||ciphertext_with_tag."""
    ct, nonce = encrypt_aes_gcm(dek, kek)
    return nonce + ct   # Prepend nonce so unwrap can extract it


def unwrap_dek(wrapped: bytes, kek: bytes) -> bytes:
    """Unwrap a DEK — extracts nonce (12 bytes) then decrypts."""
    nonce = wrapped[:12]
    ct = wrapped[12:]
    return decrypt_aes_gcm(ct, kek, nonce)


def wrap_dek_with_server_kek(dek: bytes) -> bytes:
    return wrap_dek(dek, _server_kek())


def unwrap_dek_with_server_kek(wrapped: bytes) -> bytes:
    return unwrap_dek(wrapped, _server_kek())


def wrap_dek_with_password(dek: bytes, password: str, salt: bytes,
                            iterations: int, algo: str = "sha256", key_length: int = 32) -> bytes:
    kek = derive_key(password, salt, iterations, key_length, algo)
    return wrap_dek(dek, kek)


def unwrap_dek_with_password(wrapped: bytes, password: str, salt: bytes,
                               iterations: int, algo: str = "sha256", key_length: int = 32) -> bytes:
    kek = derive_key(password, salt, iterations, key_length, algo)
    return unwrap_dek(wrapped, kek)


# ─── Digital Signatures ───────────────────────────────────────────────────────

def sign_ecdsa(data: bytes) -> tuple[bytes, bytes]:
    """Sign data with ECDSA-P256. Returns (signature, DER-encoded public key)."""
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    signature = private_key.sign(data, ECDSA(hashes.SHA256()))
    pub_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return signature, pub_der


def verify_ecdsa(data: bytes, signature: bytes, pub_der: bytes) -> bool:
    try:
        pub_key = serialization.load_der_public_key(pub_der, backend=default_backend())
        pub_key.verify(signature, data, ECDSA(hashes.SHA256()))  # type: ignore
        return True
    except Exception:
        return False


def sign_rsa_pss(data: bytes) -> tuple[bytes, bytes]:
    """Sign data with RSA-PSS-2048. Returns (signature, DER-encoded public key)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    signature = private_key.sign(
        data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    pub_der = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return signature, pub_der


def verify_rsa_pss(data: bytes, signature: bytes, pub_der: bytes) -> bool:
    try:
        pub_key = serialization.load_der_public_key(pub_der, backend=default_backend())
        pub_key.verify(  # type: ignore
            signature, data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


# ─── Hashing ──────────────────────────────────────────────────────────────────

def compute_hash(data: bytes, algo: str = "SHA-256") -> str:
    mapping = {
        "SHA-256": "sha256",
        "SHA3-256": "sha3_256",
        "SHA3-512": "sha3_512",
    }
    h = hashlib.new(mapping.get(algo, "sha256"))
    h.update(data)
    return h.hexdigest()


# ─── ChaCha20-Poly1305 (optional AEAD) ────────────────────────────────────────

def encrypt_chacha20(plaintext: bytes, key: bytes) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    nonce = os.urandom(12)
    chacha = ChaCha20Poly1305(key)
    ct = chacha.encrypt(nonce, plaintext, None)
    return ct, nonce

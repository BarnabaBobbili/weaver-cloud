from __future__ import annotations
import base64
import pyotp
from cryptography.fernet import Fernet
from app.config import settings

# Fernet key for encrypting TOTP secrets at rest
_fernet = Fernet(settings.MFA_ENCRYPTION_KEY.encode() if len(settings.MFA_ENCRYPTION_KEY) != 44
                 else settings.MFA_ENCRYPTION_KEY.encode())


def _get_fernet() -> Fernet:
    key = settings.MFA_ENCRYPTION_KEY.encode()
    return Fernet(key)


def generate_totp_secret() -> str:
    """Generate a new base32 TOTP secret."""
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    """Encrypt a TOTP secret with Fernet before storing in DB."""
    f = _get_fernet()
    return f.encrypt(secret.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted TOTP secret from DB."""
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


def get_totp_uri(secret: str, email: str) -> str:
    """Generate an otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="Weaver")


def verify_totp(encrypted_secret: str, code: str) -> bool:
    """Verify a TOTP code against the stored (encrypted) secret. Allows 1 window (±30s)."""
    try:
        secret = decrypt_secret(encrypted_secret)
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    except Exception:
        return False

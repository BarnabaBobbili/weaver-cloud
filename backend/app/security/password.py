from importlib.util import find_spec

from passlib.context import CryptContext
from passlib.exc import MissingBackendError

_ARGON2_AVAILABLE = find_spec("argon2") is not None

# Prefer Argon2id when its backend is installed, but keep PBKDF2 available so
# local/dev environments do not hard-fail auth when argon2-cffi is missing.
pwd_context = CryptContext(
    schemes=["argon2", "pbkdf2_sha256"] if _ARGON2_AVAILABLE else ["pbkdf2_sha256", "argon2"],
    deprecated="auto",
    argon2__time_cost=3,
    argon2__memory_cost=65536,  # 64 MB
    argon2__parallelism=4,
    pbkdf2_sha256__rounds=310000,
)


def hash_password(password: str) -> str:
    """Hash a password, preferring Argon2id when the backend is available."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password hash without turning missing optional backends into 500s."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except MissingBackendError:
        return False

"""
gen_keys.py — Generate cryptographic keys and patch them into .env
Run once from the backend directory: python scripts/gen_keys.py
"""
import secrets
import base64
import re
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError:
    raise SystemExit("cryptography package not installed. Run: pip install cryptography")

# ── Generate keys ────────────────────────────────────────────────────────────
jwt_secret       = secrets.token_hex(32)            # 64-char hex  (256-bit)
mfa_fernet_key   = Fernet.generate_key().decode()   # 44-char URL-safe base64
data_kek         = base64.b64encode(secrets.token_bytes(32)).decode()  # 44-char base64

print("Generated keys:")
print(f"  JWT_SECRET_KEY       = {jwt_secret}")
print(f"  MFA_ENCRYPTION_KEY   = {mfa_fernet_key}")
print(f"  DATA_ENCRYPTION_KEK  = {data_kek}")

# ── Patch .env ───────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
text = env_path.read_text(encoding="utf-8")

replacements = {
    r"JWT_SECRET_KEY=.*":        f"JWT_SECRET_KEY={jwt_secret}",
    r"MFA_ENCRYPTION_KEY=.*":    f"MFA_ENCRYPTION_KEY={mfa_fernet_key}",
    r"DATA_ENCRYPTION_KEK=.*":   f"DATA_ENCRYPTION_KEK={data_kek}",
}

for pattern, replacement in replacements.items():
    text = re.sub(pattern, replacement, text)

env_path.write_text(text, encoding="utf-8")
print(f"\n✅  .env updated at {env_path}")
print("⚠   Keep these keys safe — regenerating them will invalidate all existing tokens and encrypted data.")

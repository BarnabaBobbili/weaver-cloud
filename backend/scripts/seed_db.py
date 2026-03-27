"""
Seed script: inserts default admin user and 4 crypto policies.
Run: python scripts/seed_db.py
"""
from __future__ import annotations
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select, text
from app.database import AsyncSessionLocal, engine, Base
# Import every model module so Base.metadata knows about all tables before create_all().
from app.models import AuditLog, ClassificationRecord, CryptoPolicy, EncryptedPayload, RefreshToken, ShareLink, User
from app.security.password import hash_password

DEFAULT_ADMIN_EMAIL = "admin@weaver.local"
DEFAULT_ADMIN_PASSWORD = "Admin@1234"  # Change after first login!

DEFAULT_POLICIES = [
    {
        "sensitivity_level": "public",
        "display_name": "Public",
        "encryption_algo": "NONE",
        "key_derivation": None,
        "kdf_iterations": None,
        "signing_required": False,
        "signing_algo": None,
        "hash_algo": "SHA-256",
        "require_mfa": False,
        "description": "No encryption — content is public. Base64 encoded for transport.",
    },
    {
        "sensitivity_level": "internal",
        "display_name": "Internal",
        "encryption_algo": "AES-128-GCM",
        "key_derivation": "PBKDF2-SHA256",
        "kdf_iterations": 310000,
        "signing_required": False,
        "signing_algo": None,
        "hash_algo": "SHA-256",
        "require_mfa": False,
        "description": "AES-128-GCM with PBKDF2-SHA256 (310K iterations). For internal business docs.",
    },
    {
        "sensitivity_level": "confidential",
        "display_name": "Confidential",
        "encryption_algo": "AES-256-GCM",
        "key_derivation": "PBKDF2-SHA256",
        "kdf_iterations": 600000,
        "signing_required": True,
        "signing_algo": "ECDSA-P256",
        "hash_algo": "SHA3-256",
        "require_mfa": False,
        "description": "AES-256-GCM + ECDSA-P256 signing + PBKDF2-SHA256 (600K). OWASP 2023 compliant.",
    },
    {
        "sensitivity_level": "highly_sensitive",
        "display_name": "Highly Sensitive",
        "encryption_algo": "AES-256-GCM",
        "key_derivation": "PBKDF2-SHA512",
        "kdf_iterations": 600000,
        "signing_required": True,
        "signing_algo": "RSA-PSS-SHA256",
        "hash_algo": "SHA3-512",
        "require_mfa": True,
        "description": "AES-256-GCM + RSA-PSS-SHA256 + PBKDF2-SHA512 (600K). MFA required. PII/medical.",
    },
]

SCHEMA_PATCHES = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_recovery_codes TEXT",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_ip VARCHAR(64) NULL",
    "ALTER TABLE encrypted_payloads ADD COLUMN IF NOT EXISTS signing_pub_key BYTEA NULL",
    "ALTER TABLE encrypted_payloads ADD COLUMN IF NOT EXISTS content_kind VARCHAR(20) NOT NULL DEFAULT 'text'",
    "ALTER TABLE encrypted_payloads ADD COLUMN IF NOT EXISTS file_name VARCHAR(255) NULL",
    "ALTER TABLE encrypted_payloads ADD COLUMN IF NOT EXISTS content_type VARCHAR(255) NULL",
    "ALTER TABLE share_links ADD COLUMN IF NOT EXISTS token_encrypted BYTEA NULL",
    "UPDATE encrypted_payloads SET content_kind = 'text' WHERE content_kind IS NULL",
    "CREATE TABLE IF NOT EXISTS notifications (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL, type VARCHAR(50) NOT NULL, message TEXT NOT NULL, is_read BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())",
    "CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_notifications_type ON notifications (type)",
    "CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)",
]


async def seed():
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in SCHEMA_PATCHES:
            await conn.execute(text(statement))

    async with AsyncSessionLocal() as db:
        # Seed policies
        for p_data in DEFAULT_POLICIES:
            res = await db.execute(
                select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == p_data["sensitivity_level"])
            )
            if not res.scalar_one_or_none():
                import uuid
                policy = CryptoPolicy(id=str(uuid.uuid4()), **p_data)
                db.add(policy)
                print(f"  [+] Policy: {p_data['sensitivity_level']}")
            else:
                print(f"  [=] Policy already exists: {p_data['sensitivity_level']}")

        # Seed admin user
        res = await db.execute(select(User).where(User.email == DEFAULT_ADMIN_EMAIL))
        if not res.scalar_one_or_none():
            import uuid
            admin = User(
                id=str(uuid.uuid4()),
                email=DEFAULT_ADMIN_EMAIL,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                full_name="Weaver Admin",
                role="admin",
            )
            db.add(admin)
            print(f"  [+] Admin user: {DEFAULT_ADMIN_EMAIL} / {DEFAULT_ADMIN_PASSWORD}")
            print("      ⚠  Change this password after first login!")
        else:
            print(f"  [=] Admin already exists: {DEFAULT_ADMIN_EMAIL}")

        await db.commit()

    print("\nSeed complete!")


if __name__ == "__main__":
    asyncio.run(seed())

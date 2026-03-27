from __future__ import annotations

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        (
            "postgresql://user:pass@localhost:5432/app",
            "postgresql+asyncpg://user:pass@localhost:5432/app",
        ),
        (
            "postgres://user:pass@localhost:5432/app",
            "postgresql+asyncpg://user:pass@localhost:5432/app",
        ),
        (
            "postgresql+asyncpg://user:pass@localhost:5432/app",
            "postgresql+asyncpg://user:pass@localhost:5432/app",
        ),
    ],
)
def test_settings_normalizes_postgres_urls_to_asyncpg(raw_url: str, expected_url: str):
    settings = Settings(
        DATABASE_URL=raw_url,
        DATABASE_URL_DIRECT=raw_url,
        JWT_SECRET_KEY="test-secret",
        MFA_ENCRYPTION_KEY="test-mfa-key",
        DATA_ENCRYPTION_KEK="test-kek",
    )

    assert settings.DATABASE_URL == expected_url
    assert settings.DATABASE_URL_DIRECT == expected_url

from __future__ import annotations

import pytest

from app.config import Settings, _normalize_postgres_url


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
    assert _normalize_postgres_url(raw_url) == expected_url


def test_cors_origins_list_trims_and_ignores_empty_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://example.com, ,http://localhost:5173 ")
    settings = Settings()

    assert settings.cors_origins_list == ["https://example.com", "http://localhost:5173"]


def test_cors_origin_regex_defaults_to_azure_static_apps(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CORS_ORIGIN_REGEX", raising=False)
    settings = Settings()

    assert settings.cors_origin_regex == r"^https://[a-z0-9-]+(\.[a-z0-9-]+)?\.azurestaticapps\.net$"


def test_cors_origin_regex_can_be_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ORIGIN_REGEX", "   ")
    settings = Settings()

    assert settings.cors_origin_regex is None

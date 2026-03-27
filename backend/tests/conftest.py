"""
Shared pytest fixtures for all tests.
Uses a separate test database (Supabase connection from env, 
or can override DATABASE_URL for testing).
"""
from __future__ import annotations
import asyncio
import os
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

os.environ.setdefault("WEAVER_DISABLE_RATE_LIMITS", "1")

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.policy import CryptoPolicy
from app.security.password import hash_password

# ─── Use a test DB URL — override DATABASE_URL with a test schema or SQLite ──
# For Supabase tests, set TEST_DATABASE_URL in environment, or reuse the dev DB
# with isolated test data (cleaned up after each test).
from app.config import settings

TEST_DB_URL = (
    os.getenv("TEST_DATABASE_URL")
    or "sqlite+aiosqlite:///./test_suite.db"
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    connect_args = {}
    if TEST_DB_URL.startswith("postgresql"):
        connect_args["prepared_statement_cache_size"] = 0
    engine = create_async_engine(TEST_DB_URL, echo=False, connect_args=connect_args)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """HTTP test client with dependency override for DB."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_policies(db_session: AsyncSession):
    """Seed 4 crypto policies for tests."""
    policies = [
        {"id": str(uuid.uuid4()), "sensitivity_level": "public", "display_name": "Public",
         "encryption_algo": "NONE", "hash_algo": "SHA-256", "signing_required": False, "require_mfa": False},
        {"id": str(uuid.uuid4()), "sensitivity_level": "internal", "display_name": "Internal",
         "encryption_algo": "AES-128-GCM", "key_derivation": "PBKDF2-SHA256", "kdf_iterations": 310000,
         "hash_algo": "SHA-256", "signing_required": False, "require_mfa": False},
        {"id": str(uuid.uuid4()), "sensitivity_level": "confidential", "display_name": "Confidential",
         "encryption_algo": "AES-256-GCM", "key_derivation": "PBKDF2-SHA256", "kdf_iterations": 600000,
         "hash_algo": "SHA3-256", "signing_required": True, "signing_algo": "ECDSA-P256", "require_mfa": False},
        {"id": str(uuid.uuid4()), "sensitivity_level": "highly_sensitive", "display_name": "Highly Sensitive",
         "encryption_algo": "AES-256-GCM", "key_derivation": "PBKDF2-SHA512", "kdf_iterations": 600000,
         "hash_algo": "SHA3-512", "signing_required": True, "signing_algo": "RSA-PSS-SHA256", "require_mfa": True},
    ]
    for p in policies:
        from sqlalchemy import select
        res = await db_session.execute(
            select(CryptoPolicy).where(CryptoPolicy.sensitivity_level == p["sensitivity_level"])
        )
        if not res.scalar_one_or_none():
            db_session.add(CryptoPolicy(**p))
    await db_session.flush()
    return policies


async def _create_user(db_session, email, password, role="analyst"):
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _get_token(client, email, password):
    res = await client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json().get("access_token", "")


@pytest_asyncio.fixture
async def analyst_user(db_session):
    return await _create_user(db_session, f"analyst_{uuid.uuid4().hex[:6]}@test.com", "Test@1234!", "analyst")


@pytest_asyncio.fixture
async def admin_user(db_session):
    return await _create_user(db_session, f"admin_{uuid.uuid4().hex[:6]}@test.com", "Test@1234!", "admin")


@pytest_asyncio.fixture
async def analyst_token(client, analyst_user):
    return await _get_token(client, analyst_user.email, "Test@1234!")


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    return await _get_token(client, admin_user.email, "Test@1234!")

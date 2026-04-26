import asyncio
import pytest
import pytest_asyncio
import asyncpg
from httpx import ASGITransport, AsyncClient
import fakeredis.aioredis as fakeredis
from app.core import redis as redis_module
from unittest.mock import patch

import app.core.db as db_module
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.main import app


# ── Fix event loop scope ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Database pool ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_db_pool():
    pool = await asyncpg.create_pool(
        host=settings.postgres_test_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_test_db,
        min_size=5,
        max_size=10,
    )
    yield pool
    await pool.close()


# ── Schema creation ────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_schema(test_db_pool):
    async with test_db_pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name       VARCHAR(255) NOT NULL,
                slug       VARCHAR(100) NOT NULL UNIQUE,
                is_active  BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id        UUID NOT NULL REFERENCES tenants(id),
                email            VARCHAR(255) NOT NULL UNIQUE,
                hashed_password  VARCHAR(255) NOT NULL,
                is_active        BOOLEAN NOT NULL DEFAULT TRUE,
                created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id           UUID NOT NULL DEFAULT gen_random_uuid(),
                occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                tenant_id    UUID NOT NULL REFERENCES tenants(id),
                event_type   VARCHAR(100) NOT NULL,
                session_id   VARCHAR(255),
                user_agent   TEXT,
                ip_address   VARCHAR(45),
                url          TEXT,
                referrer     TEXT,
                properties   JSONB,
                PRIMARY KEY (id, occurred_at)
            );
        """)
        await conn.execute("""
            SELECT create_hypertable(
                'events', 'occurred_at',
                chunk_time_interval => INTERVAL '7 days',
                if_not_exists => TRUE
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS pageviews (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id    UUID NOT NULL REFERENCES tenants(id),
                url          TEXT NOT NULL,
                title        VARCHAR(512),
                duration_ms  INTEGER,
                session_id   VARCHAR(255),
                occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS funnels (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id    UUID NOT NULL REFERENCES tenants(id),
                name         VARCHAR(255) NOT NULL,
                description  TEXT,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS funnel_steps (
                id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                funnel_id        UUID NOT NULL REFERENCES funnels(id) ON DELETE CASCADE,
                tenant_id        UUID NOT NULL,
                name             VARCHAR(255) NOT NULL,
                url_pattern      VARCHAR(512) NOT NULL,
                position         INTEGER NOT NULL,
                conversion_rate  FLOAT
            );
        """)

    yield
    # ✅ NO DROP TABLE here — tables stay, your real data is safe


# ── DB pool patch ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def patch_db_pool(test_db_pool, create_test_schema):
    db_module._primary_pool = test_db_pool
    db_module._replica_pool = test_db_pool
    yield


# ── Redis patch ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", autouse=True)
async def patch_redis():
    fake = fakeredis.FakeRedis()
    with patch.object(redis_module, "get_redis_client", return_value=fake):
        yield fake
    await fake.aclose()


# ── Table cleanup ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def clean_tables(test_db_pool):
    # Clean BEFORE the test so each test starts fresh
    async with test_db_pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE TABLE
                funnel_steps, funnels, pageviews,
                events, users, tenants
            RESTART IDENTITY CASCADE;
        """)
    yield


# ── Test data factories ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_tenant(test_db_pool, clean_tables) -> dict:
    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO tenants (name, slug)
            VALUES ('Test Corp', 'test-corp')
            RETURNING id, name, slug, is_active, created_at
        """)
    return dict(row)


@pytest_asyncio.fixture
async def test_user(test_db_pool, test_tenant) -> dict:
    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO users (tenant_id, email, hashed_password)
            VALUES ($1, $2, $3)
            RETURNING id, tenant_id, email, is_active, created_at
        """,
            test_tenant["id"],
            "test@example.com",
            hash_password("testpassword123"),
        )
    return dict(row)


@pytest_asyncio.fixture
def auth_token(test_user, test_tenant) -> str:
    return create_access_token(
        subject=str(test_user["id"]),
        tenant_id=str(test_tenant["id"]),
    )


@pytest_asyncio.fixture
def auth_headers(auth_token) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}


# ── HTTP client ────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
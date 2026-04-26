
from datetime import datetime, timezone

import pytest
import fakeredis.aioredis as fakeredis

from app.services.cache import (
    _make_cache_key,
    get_cached,
    invalidate_tenant_cache,
    make_event_breakdown_key,
    make_pageviews_key,
    make_top_pages_key,
    set_cached,
)


@pytest.fixture
async def redis():
    """
    fakeredis behaves identically to real Redis but runs in-memory.
    Each test gets a fresh empty instance.
    """
    async with fakeredis.FakeRedis() as r:
        yield r


# ── Cache key generation ──────────────────────────────────────────────────────

def test_make_cache_key_is_deterministic():
    """
    Same inputs must always produce the same key.
    If not, cache lookups would never find previously cached data.
    """
    key1 = _make_cache_key("tenant-1", "pageviews", start="2024-01-01", end="2024-01-07")
    key2 = _make_cache_key("tenant-1", "pageviews", start="2024-01-01", end="2024-01-07")
    assert key1 == key2


def test_make_cache_key_different_tenants_differ():
    """
    Two different tenants must never share a cache key.
    This is the core of tenant data isolation.
    """
    key1 = _make_cache_key("tenant-1", "pageviews", start="2024-01-01")
    key2 = _make_cache_key("tenant-2", "pageviews", start="2024-01-01")
    assert key1 != key2


def test_make_cache_key_different_params_differ():
    key1 = _make_cache_key("tenant-1", "pageviews", start="2024-01-01")
    key2 = _make_cache_key("tenant-1", "pageviews", start="2024-01-08")
    assert key1 != key2


def test_make_cache_key_contains_tenant_id():
    """The key must be namespaced with the tenant_id for easy invalidation."""
    tenant_id = "tenant-abc-123"
    key = _make_cache_key(tenant_id, "pageviews")
    assert tenant_id in key


def test_pageviews_key_format():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 7, tzinfo=timezone.utc)
    key = make_pageviews_key("tenant-1", start, end)
    assert key.startswith("cache:tenant-1:pageviews:")


def test_top_pages_key_includes_limit():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 7, tzinfo=timezone.utc)
    key1 = make_top_pages_key("tenant-1", start, end, limit=10)
    key2 = make_top_pages_key("tenant-1", start, end, limit=20)
    # Different limit must produce a different key
    assert key1 != key2


# ── get_cached / set_cached ───────────────────────────────────────────────────

async def test_get_cached_returns_none_on_miss(redis):
    """Cache miss — key doesn't exist — must return None."""
    result = await get_cached(redis, "nonexistent:key")
    assert result is None


async def test_set_and_get_cached_roundtrip(redis):
    """Write data to cache then read it back — must be identical."""
    data = [{"bucket": "2024-01-01T00:00:00", "count": 42}]
    await set_cached(redis, "test:key", data, ttl_seconds=60)
    result = await get_cached(redis, "test:key")
    assert result == data


async def test_cached_data_types_preserved(redis):
    """
    JSON serialisation must preserve Python types correctly.
    Integers stay integers, strings stay strings, lists stay lists.
    """
    data = {"count": 100, "url": "/home", "nested": [1, 2, 3]}
    await set_cached(redis, "test:types", data)
    result = await get_cached(redis, "test:types")
    assert result["count"] == 100
    assert result["url"] == "/home"
    assert result["nested"] == [1, 2, 3]


async def test_set_cached_with_ttl(redis):
    """Verify the key has a TTL set in Redis."""
    await set_cached(redis, "test:ttl", {"data": "value"}, ttl_seconds=300)
    ttl = await redis.ttl("test:ttl")
    # TTL should be close to 300 (might be 299 due to execution time)
    assert 290 <= ttl <= 300


# ── invalidate_tenant_cache ───────────────────────────────────────────────────

async def test_invalidate_tenant_cache_removes_all_tenant_keys(redis):
    """
    Invalidation must delete ALL keys for a tenant and only that tenant.
    """
    tenant_id = "tenant-abc"
    other_tenant_id = "tenant-xyz"

    # Write keys for our tenant
    await redis.set(f"cache:{tenant_id}:pageviews:hash1", "data1")
    await redis.set(f"cache:{tenant_id}:top_pages:hash2", "data2")
    await redis.set(f"cache:{tenant_id}:events:hash3", "data3")

    # Write a key for a different tenant — must NOT be deleted
    await redis.set(f"cache:{other_tenant_id}:pageviews:hash4", "other_data")

    await invalidate_tenant_cache(redis, tenant_id)

    # All our tenant's keys should be gone
    assert await redis.get(f"cache:{tenant_id}:pageviews:hash1") is None
    assert await redis.get(f"cache:{tenant_id}:top_pages:hash2") is None
    assert await redis.get(f"cache:{tenant_id}:events:hash3") is None

    # Other tenant's key must still exist
    assert await redis.get(f"cache:{other_tenant_id}:pageviews:hash4") == b"other_data"


async def test_invalidate_empty_cache_does_not_crash(redis):
    """Invalidating when no keys exist must not raise an exception."""
    await invalidate_tenant_cache(redis, "nonexistent-tenant")
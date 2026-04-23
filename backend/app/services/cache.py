import hashlib
import json
from datetime import datetime
from typing import Any

from redis.asyncio import Redis


def _make_cache_key(tenant_id: str, query_name: str, **params) -> str:
    """
    Builds a deterministic cache key from the query name and parameters.
    Example: cache:acme-tenant-uuid:pageviews:start=...:end=...
    """
    param_str = ":".join(f"{k}={v}" for k, v in sorted(params.items()))
    raw = f"{tenant_id}:{query_name}:{param_str}"
    # Hash it so long URLs don't exceed Redis key length limits
    hashed = hashlib.md5(raw.encode()).hexdigest()
    return f"cache:{tenant_id}:{query_name}:{hashed}"


async def get_cached(redis: Redis, key: str) -> Any | None:
    """Returns parsed JSON from cache, or None if missing/expired."""
    value = await redis.get(key)
    if value is None:
        return None
    return json.loads(value)


async def set_cached(
    redis: Redis,
    key: str,
    data: Any,
    ttl_seconds: int = 300,  # 5 minutes default
) -> None:
    """Serialises data to JSON and stores it with a TTL."""
    await redis.set(key, json.dumps(data, default=str), ex=ttl_seconds)


async def invalidate_tenant_cache(redis: Redis, tenant_id: str) -> None:
    """
    Deletes all cache keys for a tenant when new events arrive.
    Uses Redis SCAN to avoid blocking the server with KEYS command.
    """
    pattern = f"cache:{tenant_id}:*"
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break


def make_pageviews_key(tenant_id: str, start: datetime, end: datetime) -> str:
    return _make_cache_key(tenant_id, "pageviews", start=start.isoformat(), end=end.isoformat())


def make_top_pages_key(tenant_id: str, start: datetime, end: datetime, limit: int) -> str:
    return _make_cache_key(tenant_id, "top_pages", start=start.isoformat(), end=end.isoformat(), limit=limit)


def make_event_breakdown_key(tenant_id: str, start: datetime, end: datetime) -> str:
    return _make_cache_key(tenant_id, "event_breakdown", start=start.isoformat(), end=end.isoformat())
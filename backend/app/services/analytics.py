from datetime import datetime

from redis.asyncio import Redis

import app.core.db as db
from app.services.cache import (
    get_cached,
    make_event_breakdown_key,
    make_pageviews_key,
    make_top_pages_key,
    set_cached,
)

CACHE_TTL = 300


async def get_pageview_counts(
    tenant_id: str, site_id: str, start: datetime, end: datetime, redis: Redis,
) -> list[dict]:
    key = make_pageviews_key(f"{tenant_id}:{site_id}", start, end)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached

    rows = await db.fetch(
        """
        SELECT time_bucket('1 hour', occurred_at) AS bucket, COUNT(*) AS count
        FROM pageviews
        WHERE site_id = $1
          AND occurred_at >= $2
          AND occurred_at
            < $3
        GROUP BY bucket
        ORDER BY bucket ASC
        """,
        site_id, start, end,
    )
    data = [{"bucket": row["bucket"].isoformat(), "count": row["count"]} for row in rows]
    await set_cached(redis, key, data, ttl_seconds=CACHE_TTL)
    return data



async def get_top_pages(
    tenant_id: str, site_id: str, start: datetime, end: datetime, limit: int, redis: Redis,
) -> list[dict]:
    key = make_top_pages_key(f"{tenant_id}:{site_id}", start, end, limit)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached

    rows = await db.fetch(
        """
        SELECT url, COUNT(*) AS count FROM pageviews
        WHERE site_id = $1 AND occurred_at >= $2 AND occurred_at < $3
        GROUP BY url ORDER BY count DESC LIMIT $4
        """,
        site_id, start, end, limit,
    )
    data = [{"url": row["url"], "count": row["count"]} for row in rows]
    await set_cached(redis, key, data, ttl_seconds=CACHE_TTL)
    return data


async def get_event_breakdown(
    tenant_id: str, site_id: str, start: datetime, end: datetime, redis: Redis,
) -> list[dict]:
    key = make_event_breakdown_key(f"{tenant_id}:{site_id}", start, end)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached

    rows = await db.fetch(
        """
        SELECT event_type, COUNT(*) AS count FROM events
        WHERE site_id = $1 AND occurred_at >= $2 AND occurred_at < $3
        GROUP BY event_type ORDER BY count DESC
        """,
        site_id, start, end,
    )
    data = [{"event_type": row["event_type"], "count": row["count"]} for row in rows]
    await set_cached(redis, key, data, ttl_seconds=CACHE_TTL)
    return data
import uuid
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Pageview
from app.services.cache import (
    get_cached,
    make_event_breakdown_key,
    make_pageviews_key,
    make_top_pages_key,
    set_cached,
)

CACHE_TTL = 300  # 5 minutes


async def get_pageview_counts(
    tenant_id: str,
    start: datetime,
    end: datetime,
    db: AsyncSession,
    redis: Redis,
) -> list[dict]:
    # 1. Check cache first
    key = make_pageviews_key(tenant_id, start, end)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached

    # 2. Cache miss — query Postgres
    query = text("""
        SELECT
            time_bucket('1 hour', occurred_at) AS bucket,
            COUNT(*) AS count
        FROM pageviews
        WHERE
            tenant_id = :tenant_id
            AND occurred_at >= :start
            AND occurred_at < :end
        GROUP BY bucket
        ORDER BY bucket ASC
    """)
    result = await db.execute(
        query,
        {"tenant_id": str(tenant_id), "start": start, "end": end},
    )
    data = [{"bucket": row.bucket.isoformat(), "count": row.count} for row in result.fetchall()]

    # 3. Write to cache
    await set_cached(redis, key, data, ttl_seconds=CACHE_TTL)
    return data


async def get_top_pages(
    tenant_id: str,
    start: datetime,
    end: datetime,
    limit: int,
    db: AsyncSession,
    redis: Redis,
) -> list[dict]:
    key = make_top_pages_key(tenant_id, start, end, limit)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached

    result = await db.execute(
        select(Pageview.url, func.count().label("count"))
        .where(
            Pageview.tenant_id == uuid.UUID(tenant_id),
            Pageview.occurred_at >= start,
            Pageview.occurred_at < end,
        )
        .group_by(Pageview.url)
        .order_by(func.count().desc())
        .limit(limit)
    )
    data = [{"url": row.url, "count": row.count} for row in result.fetchall()]

    await set_cached(redis, key, data, ttl_seconds=CACHE_TTL)
    return data


async def get_event_breakdown(
    tenant_id: str,
    start: datetime,
    end: datetime,
    db: AsyncSession,
    redis: Redis,
) -> list[dict]:
    key = make_event_breakdown_key(tenant_id, start, end)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached

    result = await db.execute(
        select(Event.event_type, func.count().label("count"))
        .where(
            Event.tenant_id == uuid.UUID(tenant_id),
            Event.occurred_at >= start,
            Event.occurred_at < end,
        )
        .group_by(Event.event_type)
        .order_by(func.count().desc())
    )
    data = [{"event_type": row.event_type, "count": row.count} for row in result.fetchall()]

    await set_cached(redis, key, data, ttl_seconds=CACHE_TTL)
    return data
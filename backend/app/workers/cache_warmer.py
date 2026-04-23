from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics import get_event_breakdown, get_pageview_counts, get_top_pages
from app.services.cache import invalidate_tenant_cache


async def warm_tenant_cache(
    tenant_id: str,
    redis: Redis,
    db: AsyncSession,
) -> None:
    """
    Called as a BackgroundTask after event ingestion.
    1. Invalidates all stale cache entries for this tenant.
    2. Pre-warms the last 7 days dashboard queries immediately.
    """
    # Step 1 — invalidate stale data
    await invalidate_tenant_cache(redis, tenant_id)

    # Step 2 — pre-warm the most common queries
    # These are the queries the dashboard hits on first load
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    try:
        await get_pageview_counts(tenant_id, start, end, db, redis)
        await get_top_pages(tenant_id, start, end, limit=10, db=db, redis=redis)
        await get_event_breakdown(tenant_id, start, end, db, redis)
    except Exception as e:
        # Background tasks must never crash the main request
        # Log the error but swallow it
        print(f"Cache warming failed for tenant {tenant_id}: {e}")
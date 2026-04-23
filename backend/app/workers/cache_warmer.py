from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis

from app.services.analytics import get_event_breakdown, get_pageview_counts, get_top_pages
from app.services.cache import invalidate_tenant_cache


async def warm_tenant_cache(tenant_id: str, redis: Redis) -> None:
    await invalidate_tenant_cache(redis, tenant_id)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    try:
        await get_pageview_counts(tenant_id, start, end, redis)
        await get_top_pages(tenant_id, start, end, limit=10, redis=redis)
        await get_event_breakdown(tenant_id, start, end, redis)
    except Exception as e:
        print(f"Cache warming failed for tenant {tenant_id}: {e}")
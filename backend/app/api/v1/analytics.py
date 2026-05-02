from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from redis.asyncio import Redis

from app.api.deps import get_current_tenant, get_redis
from app.services.analytics import get_event_breakdown, get_pageview_counts, get_top_pages

router = APIRouter(prefix="/analytics", tags=["analytics"])


def default_start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=7)


def default_end() -> datetime:
    return datetime.now(timezone.utc)

def require_site(site_id: str | None = Query(default=None)) -> str:
    if not site_id:
        raise HTTPException(status_code=400, detail="site_id query parameter is required")
    return site_id

@router.get("/pageviews")
async def pageviews(
    site_id: str = Depends(require_site),
    start: datetime = Query(default_factory=default_start),
    end: datetime = Query(default_factory=default_end),
    redis: Redis = Depends(get_redis),
    tenant_id: str = Depends(get_current_tenant),
):
    data = await get_pageview_counts(tenant_id, site_id, start, end, redis)
    return {"site_id": site_id, "data": data}


@router.get("/top-pages")
async def top_pages(
    site_id: str = Depends(require_site),
    start: datetime = Query(default_factory=default_start),
    end: datetime = Query(default_factory=default_end),
    limit: int = Query(default=10, ge=1, le=100),
    redis: Redis = Depends(get_redis),
    tenant_id: str = Depends(get_current_tenant),
):
    data = await get_top_pages(tenant_id, site_id, start, end, limit, redis)
    return {"site_id": site_id, "data": data}


@router.get("/events")
async def event_breakdown(
    site_id: str = Depends(require_site),
    start: datetime = Query(default_factory=default_start),
    end: datetime = Query(default_factory=default_end),
    redis: Redis = Depends(get_redis),
    tenant_id: str = Depends(get_current_tenant),
):
    data = await get_event_breakdown(tenant_id, site_id, start, end, redis)
    return {"site_id": site_id, "data": data}
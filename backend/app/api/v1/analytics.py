from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db, get_redis
from app.services.analytics import get_event_breakdown, get_pageview_counts, get_top_pages

router = APIRouter(prefix="/analytics", tags=["analytics"])


def default_start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=7)


def default_end() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/pageviews")
async def pageviews(
    start: datetime = Query(default_factory=default_start),
    end: datetime = Query(default_factory=default_end),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    tenant_id: str = Depends(get_current_tenant),
):
    data = await get_pageview_counts(tenant_id, start, end, db, redis)
    return {"tenant_id": tenant_id, "data": data}


@router.get("/top-pages")
async def top_pages(
    start: datetime = Query(default_factory=default_start),
    end: datetime = Query(default_factory=default_end),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    tenant_id: str = Depends(get_current_tenant),
):
    data = await get_top_pages(tenant_id, start, end, limit, db, redis)
    return {"tenant_id": tenant_id, "data": data}


@router.get("/events")
async def event_breakdown(
    start: datetime = Query(default_factory=default_start),
    end: datetime = Query(default_factory=default_end),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    tenant_id: str = Depends(get_current_tenant),
):
    data = await get_event_breakdown(tenant_id, start, end, db, redis)
    return {"tenant_id": tenant_id, "data": data}
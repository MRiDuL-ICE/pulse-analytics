from fastapi import APIRouter, BackgroundTasks, Depends, Request
from redis.asyncio import Redis

from app.api.deps import get_current_tenant, get_redis
from app.schemas.event import EventPayload
from app.services.events import ingest_event
from app.workers.cache_warmer import warm_tenant_cache

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", status_code=202)
async def track_event(
    payload: EventPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    redis: Redis = Depends(get_redis),
    tenant_id: str = Depends(get_current_tenant),
):
    event = await ingest_event(
        tenant_id=tenant_id,
        event_type=payload.event_type,
        properties=payload.properties,
        session_id=payload.session_id,
        url=payload.url,
        referrer=payload.referrer,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    background_tasks.add_task(
        warm_tenant_cache,
        tenant_id=tenant_id,
        redis=redis,
    )

    return {"accepted": True, "event_id": str(event["id"])}
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant, get_db
from app.services.events import ingest_event

from app.schemas.event import EventPayload

router = APIRouter(prefix="/events", tags=["events"])


class EventIn:
    pass



@router.post("", status_code=202)
async def track_event(
    payload: EventPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
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
        db=db,
    )
    return {"accepted": True, "event_id": str(event.id)}
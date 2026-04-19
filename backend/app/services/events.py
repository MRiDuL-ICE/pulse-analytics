import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Pageview


async def ingest_event(
    tenant_id: str,
    event_type: str,
    properties: dict,
    session_id: str | None,
    url: str | None,
    referrer: str | None,
    user_agent: str | None,
    ip_address: str | None,
    db: AsyncSession,
) -> Event:
    event = Event(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(tenant_id),
        event_type=event_type,
        session_id=session_id,
        url=url,
        referrer=referrer,
        user_agent=user_agent,
        ip_address=ip_address,
        properties=properties,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)

    # If it's a pageview, also write to the dedicated pageviews table
    if event_type == "pageview":
        pageview = Pageview(
            tenant_id=uuid.UUID(tenant_id),
            url=url or "",
            title=properties.get("title"),
            duration_ms=properties.get("duration_ms"),
            session_id=session_id,
            occurred_at=event.occurred_at,
        )
        db.add(pageview)

    await db.flush()
    return event
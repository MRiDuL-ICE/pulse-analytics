import uuid
from datetime import datetime, timezone

import app.core.db as db


async def ingest_event(
    tenant_id: str,
    event_type: str,
    properties: dict,
    session_id: str | None,
    url: str | None,
    referrer: str | None,
    user_agent: str | None,
    ip_address: str | None,
) -> dict:
    import json
    occurred_at = datetime.now(timezone.utc)
    event_id = uuid.uuid4()

    event = await db.fetchrow(
        """
        INSERT INTO events (
            id, tenant_id, event_type, session_id,
            user_agent, ip_address, url, referrer,
            properties, occurred_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id, tenant_id, event_type, url, occurred_at
        """,
        event_id,
        uuid.UUID(tenant_id),
        event_type,
        session_id,
        user_agent,
        ip_address,
        url,
        referrer,
        json.dumps(properties),
        occurred_at,
    )

    if event_type == "pageview":
        await db.execute(
            """
            INSERT INTO pageviews (
                tenant_id, url, title, duration_ms, session_id, occurred_at
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(tenant_id),
            url or "",
            properties.get("title"),
            properties.get("duration_ms"),
            session_id,
            occurred_at,
        )

    return dict(event)
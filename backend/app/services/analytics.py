import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Pageview


async def get_pageview_counts(
    tenant_id: str,
    start: datetime,
    end: datetime,
    db: AsyncSession,
) -> list[dict]:
    """
    Returns hourly pageview counts for a tenant within a time range.
    Uses TimescaleDB's time_bucket() for efficient rollups.
    """
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
        {
            "tenant_id": str(tenant_id),
            "start": start,
            "end": end,
        },
    )
    rows = result.fetchall()
    return [{"bucket": row.bucket.isoformat(), "count": row.count} for row in rows]


async def get_top_pages(
    tenant_id: str,
    start: datetime,
    end: datetime,
    limit: int,
    db: AsyncSession,
) -> list[dict]:
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
    return [{"url": row.url, "count": row.count} for row in result.fetchall()]


async def get_event_breakdown(
    tenant_id: str,
    start: datetime,
    end: datetime,
    db: AsyncSession,
) -> list[dict]:
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
    return [{"event_type": row.event_type, "count": row.count} for row in result.fetchall()]
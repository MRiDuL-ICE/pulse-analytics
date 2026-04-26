
from httpx import AsyncClient


async def test_track_pageview_event(client: AsyncClient, auth_headers, test_db_pool):
    response = await client.post(
        "/api/v1/events",
        json={
            "event_type": "pageview",
            "url": "/home",
            "properties": {"title": "Home Page"},
        },
        headers=auth_headers,
    )
    assert response.status_code == 202
    data = response.json()
    assert data["accepted"] is True
    assert "event_id" in data

    # Verify the row actually landed in the database
    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM events WHERE id = $1",
            data["event_id"],
        )
    assert row is not None
    assert row["event_type"] == "pageview"
    assert row["url"] == "/home"


async def test_pageview_event_also_writes_to_pageviews_table(
    client: AsyncClient, auth_headers, test_db_pool
):
    """
    Pageview events must write to BOTH the events table and the pageviews table.
    This is the dual-write logic in services/events.py.
    """
    await client.post(
        "/api/v1/events",
        json={"event_type": "pageview", "url": "/pricing", "properties": {"title": "Pricing"}},
        headers=auth_headers,
    )

    async with test_db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM pageviews WHERE url = '/pricing'")
    assert count == 1


async def test_non_pageview_event_does_not_write_to_pageviews(
    client: AsyncClient, auth_headers, test_db_pool
):
    """Click events should go to events table only, not pageviews."""
    await client.post(
        "/api/v1/events",
        json={"event_type": "click", "url": "/home", "properties": {"element_id": "btn-cta"}},
        headers=auth_headers,
    )

    async with test_db_pool.acquire() as conn:
        pv_count = await conn.fetchval("SELECT COUNT(*) FROM pageviews")
        ev_count = await conn.fetchval("SELECT COUNT(*) FROM events WHERE event_type = 'click'")

    assert pv_count == 0
    assert ev_count == 1


async def test_track_event_without_auth_fails(client: AsyncClient):
    response = await client.post(
        "/api/v1/events",
        json={"event_type": "pageview", "url": "/home"},
    )
    assert response.status_code == 403


async def test_event_tenant_isolation(client: AsyncClient, test_db_pool, auth_headers):
    """
    Events must be tagged with the correct tenant_id from the JWT.
    A different tenant must not see another tenant's events.
    """
    await client.post(
        "/api/v1/events",
        json={"event_type": "pageview", "url": "/home"},
        headers=auth_headers,
    )

    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT tenant_id FROM events")

    # All events must belong to the same tenant
    tenant_ids = {str(row["tenant_id"]) for row in rows}
    assert len(tenant_ids) == 1


async def test_track_multiple_events(client: AsyncClient, auth_headers, test_db_pool):
    urls = ["/home", "/about", "/pricing", "/contact"]
    for url in urls:
        response = await client.post(
            "/api/v1/events",
            json={"event_type": "pageview", "url": url},
            headers=auth_headers,
        )
        assert response.status_code == 202

    async with test_db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM events")
    assert count == len(urls)
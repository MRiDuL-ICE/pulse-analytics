import pytest
from httpx import AsyncClient


@pytest.fixture
async def seeded_events(client: AsyncClient, clean_tables, auth_headers):
    """
    Seeds 5 pageview events before analytics tests run.
    Tests that need data declare this fixture and get the events pre-inserted.
    """
    urls = ["/home", "/home", "/pricing", "/about", "/contact"]
    for url in urls:
        await client.post(
            "/api/v1/events",
            json={"event_type": "pageview", "url": url, "properties": {"title": url}},
            headers=auth_headers,
        )


async def test_pageviews_endpoint_returns_data(
    client: AsyncClient, clean_tables, auth_headers, seeded_events
):
    response = await client.get("/api/v1/analytics/pageviews", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "tenant_id" in data
    # We seeded 5 events — at least 1 bucket must exist
    assert len(data["data"]) >= 1


async def test_pageviews_bucket_structure(client: AsyncClient, clean_tables, auth_headers, seeded_events):
    """Each bucket in the response must have 'bucket' and 'count' fields."""
    response = await client.get("/api/v1/analytics/pageviews", headers=auth_headers)
    buckets = response.json()["data"]
    for bucket in buckets:
        assert "bucket" in bucket
        assert "count" in bucket
        assert isinstance(bucket["count"], int)
        assert bucket["count"] > 0


async def test_top_pages_returns_ranked_results(
    client: AsyncClient, clean_tables, auth_headers, seeded_events
):
    """
    /home was visited twice, all others once.
    Top pages must return /home first.
    """
    response = await client.get("/api/v1/analytics/top-pages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) > 0
    # /home appears twice so it must be first
    assert data[0]["url"] == "/home"
    assert data[0]["count"] == 2


async def test_top_pages_limit_parameter(client: AsyncClient, clean_tables, auth_headers, seeded_events):
    """The limit parameter must restrict the number of results returned."""
    response = await client.get(
        "/api/v1/analytics/top-pages?limit=2",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) <= 2


async def test_top_pages_limit_validation(client: AsyncClient, clean_tables, auth_headers):
    """limit=0 must be rejected — minimum is 1."""
    response = await client.get(
        "/api/v1/analytics/top-pages?limit=0",
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_event_breakdown_groups_by_type(client: AsyncClient, clean_tables, auth_headers):
    """Send different event types and verify each appears in the breakdown."""
    for event_type in ["pageview", "pageview", "click", "conversion"]:
        await client.post(
            "/api/v1/events",
            json={"event_type": event_type, "url": "/test"},
            headers=auth_headers,
        )

    response = await client.get("/api/v1/analytics/events", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    types = {item["event_type"]: item["count"] for item in data}
    assert types["pageview"] == 2
    assert types["click"] == 1
    assert types["conversion"] == 1


async def test_analytics_requires_auth(client: AsyncClient, clean_tables):
    for endpoint in ["/api/v1/analytics/pageviews", "/api/v1/analytics/top-pages", "/api/v1/analytics/events"]:
        response = await client.get(endpoint)
        assert response.status_code == 403


async def test_analytics_empty_returns_empty_list(client: AsyncClient, clean_tables, auth_headers):
    """With no events in the DB, analytics must return empty lists not errors."""
    response = await client.get("/api/v1/analytics/pageviews", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []
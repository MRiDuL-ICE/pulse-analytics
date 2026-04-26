import pytest
from httpx import AsyncClient


async def test_create_api_key(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/api-keys",
        json={"name": "My Website"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Website"
    assert data["key"].startswith("pk_live_")
    assert "warning" in data
    assert "key_hash" not in data   # raw hash must never be exposed
    assert data["is_active"] is True


async def test_created_key_starts_with_prefix(client: AsyncClient, auth_headers):
    response = await client.post(
        "/api/v1/api-keys",
        json={"name": "Test Key"},
        headers=auth_headers,
    )
    data = response.json()
    assert data["key_prefix"] == data["key"][:15]


async def test_list_api_keys(client: AsyncClient, auth_headers):
    await client.post("/api/v1/api-keys", json={"name": "Key 1"}, headers=auth_headers)
    await client.post("/api/v1/api-keys", json={"name": "Key 2"}, headers=auth_headers)

    response = await client.get("/api/v1/api-keys", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Raw key must never appear in list
    for key in data:
        assert "key" not in key


async def test_list_keys_does_not_expose_raw_key(client: AsyncClient, auth_headers):
    await client.post("/api/v1/api-keys", json={"name": "Secret Key"}, headers=auth_headers)
    response = await client.get("/api/v1/api-keys", headers=auth_headers)
    for key in response.json():
        assert "key" not in key
        assert "key_hash" not in key


async def test_revoke_api_key(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/v1/api-keys",
        json={"name": "To Revoke"},
        headers=auth_headers,
    )
    key_id = create.json()["id"]

    response = await client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify it's inactive
    keys = await client.get("/api/v1/api-keys", headers=auth_headers)
    revoked = next(k for k in keys.json() if k["id"] == key_id)
    assert revoked["is_active"] is False


async def test_track_event_with_api_key(client: AsyncClient, auth_headers):
    """
    Full flow: create API key → use it to send an event (no JWT needed).
    This is exactly how the JS snippet works.
    """
    create = await client.post(
        "/api/v1/api-keys",
        json={"name": "JS Snippet Key"},
        headers=auth_headers,
    )
    raw_key = create.json()["key"]

    # Send event using API key instead of JWT
    response = await client.post(
        "/api/v1/events",
        json={"event_type": "pageview", "url": "/home"},
        headers={"X-API-Key": raw_key},   # no Authorization header
    )
    assert response.status_code == 202
    assert response.json()["accepted"] is True


async def test_track_event_with_revoked_key_fails(client: AsyncClient, auth_headers):
    create = await client.post(
        "/api/v1/api-keys",
        json={"name": "Will Be Revoked"},
        headers=auth_headers,
    )
    data = create.json()
    raw_key = data["key"]
    key_id = data["id"]

    await client.delete(f"/api/v1/api-keys/{key_id}", headers=auth_headers)

    response = await client.post(
        "/api/v1/events",
        json={"event_type": "pageview", "url": "/home"},
        headers={"X-API-Key": raw_key},
    )
    assert response.status_code == 401


async def test_track_event_with_invalid_key_fails(client: AsyncClient):
    response = await client.post(
        "/api/v1/events",
        json={"event_type": "pageview", "url": "/home"},
        headers={"X-API-Key": "pk_live_totallyfakekey12345"},
    )
    assert response.status_code == 401


async def test_revoke_another_tenants_key_fails(
    client: AsyncClient, auth_headers, test_db_pool
):
    """A tenant must not be able to revoke another tenant's API key."""
    # Create a second tenant and key
    async with test_db_pool.acquire() as conn:
        other_tenant = await conn.fetchrow(
            "INSERT INTO tenants (name, slug) VALUES ('Other', 'other') RETURNING id"
        )
        other_key = await conn.fetchrow(
            """
            INSERT INTO api_keys (tenant_id, name, key_prefix, key_hash)
            VALUES ($1, 'Other Key', 'pk_live_other', 'fakehash')
            RETURNING id
            """,
            other_tenant["id"],
        )

    response = await client.delete(
        f"/api/v1/api-keys/{other_key['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_create_api_key_requires_auth(client: AsyncClient, clean_tables):
    response = await client.post(
        "/api/v1/api-keys",
        json={"name": "No Auth"},
    )
    assert response.status_code == 403
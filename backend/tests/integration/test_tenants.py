
from httpx import AsyncClient


async def test_get_my_tenant(client: AsyncClient, auth_headers, test_tenant):
    response = await client.get("/api/v1/tenants/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "test-corp"
    assert data["name"] == "Test Corp"
    assert data["is_active"] is True


async def test_get_my_tenant_without_auth(client: AsyncClient):
    response = await client.get("/api/v1/tenants/me")
    assert response.status_code == 403


async def test_update_tenant_name(client: AsyncClient, auth_headers):
    response = await client.patch(
        "/api/v1/tenants/me",
        json={"name": "Updated Corp Name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Corp Name"


async def test_update_tenant_slug(client: AsyncClient, auth_headers):
    response = await client.patch(
        "/api/v1/tenants/me",
        json={"slug": "updated-slug"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["slug"] == "updated-slug"


async def test_update_tenant_duplicate_slug_fails(
    client: AsyncClient, auth_headers, test_db_pool
):
    # Use a separate connection explicitly to avoid pool conflicts
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tenants (name, slug) VALUES ('Other Corp', 'taken-slug')"
        )

    response = await client.patch(
        "/api/v1/tenants/me",
        json={"slug": "taken-slug"},
        headers=auth_headers,
    )
    assert response.status_code == 409


async def test_update_tenant_empty_body_fails(client: AsyncClient, auth_headers):
    """Sending an empty update must return 400 — nothing to update."""
    response = await client.patch(
        "/api/v1/tenants/me",
        json={},
        headers=auth_headers,
    )
    assert response.status_code == 400


async def test_deactivate_tenant(client: AsyncClient, auth_headers, test_db_pool, test_tenant):
    response = await client.delete("/api/v1/tenants/me", headers=auth_headers)
    assert response.status_code == 204

    # Verify is_active is now False in the database
    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT is_active FROM tenants WHERE id = $1",
            test_tenant["id"],
        )
    assert row["is_active"] is False
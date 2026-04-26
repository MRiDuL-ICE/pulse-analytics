
from httpx import AsyncClient


# ── Register ──────────────────────────────────────────────────────────────────

async def test_register_new_user(client: AsyncClient, clean_tables):
    """Happy path — register a brand new user with a new tenant."""
    response = await client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "securepassword123",
        "tenant_name": "New Corp",
        "tenant_slug": "new-corp",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "tenant_id" in data
    # hashed_password must NEVER appear in the response
    assert "hashed_password" not in data
    assert "password" not in data


async def test_register_duplicate_email_fails(client: AsyncClient, clean_tables):
    """Registering twice with the same email must return 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "password": "password123",
        "tenant_name": "Corp A",
        "tenant_slug": "corp-a",
    }
    await client.post("/api/v1/auth/register", json=payload)

    # Second registration with same email
    response = await client.post("/api/v1/auth/register", json={
        **payload,
        "tenant_slug": "corp-b",  # different slug to isolate the email conflict
    })
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


async def test_register_invalid_email_fails(client: AsyncClient, clean_tables):
    """Pydantic must reject malformed email addresses before they hit the DB."""
    response = await client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "password": "password123",
        "tenant_name": "Corp",
        "tenant_slug": "corp",
    })
    assert response.status_code == 422


async def test_register_missing_fields_fails(client: AsyncClient, clean_tables):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        # missing password, tenant_name, tenant_slug
    })
    assert response.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

async def test_login_success(client: AsyncClient, clean_tables, test_user):
    """
    test_user fixture creates the user in DB.
    We log in with its credentials and verify we get tokens back.
    """
    response = await client.post(
        "/api/v1/auth/login",
        data={"email": "test@example.com", "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    # Tokens must be non-empty strings
    assert len(data["access_token"]) > 0
    assert len(data["refresh_token"]) > 0


async def test_login_wrong_password(client: AsyncClient, clean_tables, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        data={"email": "test@example.com", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


async def test_login_nonexistent_user(client: AsyncClient, clean_tables):
    response = await client.post(
        "/api/v1/auth/login",
        data={"email": "ghost@example.com", "password": "password123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


async def test_login_wrong_password_same_error_as_wrong_user(client: AsyncClient, clean_tables, test_user):
    """
    Security: wrong password and wrong username must return the same error message.
    This prevents user enumeration attacks — attackers can't tell if an account exists.
    """
    wrong_user_resp = await client.post(
        "/api/v1/auth/login",
        data={"email": "ghost@example.com", "password": "any"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    wrong_pass_resp = await client.post(
        "/api/v1/auth/login",
        data={"email": "test@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert wrong_user_resp.json()["detail"] == wrong_pass_resp.json()["detail"]


# ── Refresh ───────────────────────────────────────────────────────────────────

async def test_refresh_token_returns_new_tokens(client: AsyncClient, clean_tables, test_user):
    login = await client.post(
        "/api/v1/auth/login",
        data={"email": "test@example.com", "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # New refresh token must be different from the used one (rotation)
    assert data["refresh_token"] != refresh_token


async def test_refresh_token_cannot_be_reused(client: AsyncClient, clean_tables, test_user):
    """
    After a refresh token is used once it's blacklisted.
    Using it a second time must fail.
    """
    login = await client.post(
        "/api/v1/auth/login",
        data={"email": "test@example.com", "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    refresh_token = login.json()["refresh_token"]

    # First use — should succeed
    await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    # Second use — must be rejected
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()


async def test_refresh_with_access_token_fails(client: AsyncClient, clean_tables, auth_token):
    """Passing an access token where a refresh token is expected must fail."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_token},
    )
    assert response.status_code == 401


# ── Protected routes ──────────────────────────────────────────────────────────

async def test_protected_route_without_token_fails(client: AsyncClient, clean_tables):
    response = await client.get("/api/v1/tenants/me")
    assert response.status_code == 403


async def test_protected_route_with_invalid_token_fails(client: AsyncClient, clean_tables):
    response = await client.get(
        "/api/v1/tenants/me",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert response.status_code == 403


async def test_protected_route_with_valid_token_succeeds(client: AsyncClient, clean_tables, auth_headers):
    response = await client.get("/api/v1/tenants/me", headers=auth_headers)
    assert response.status_code == 200


# ── Logout ────────────────────────────────────────────────────────────────────

async def test_logout_blacklists_refresh_token(client: AsyncClient, clean_tables, test_user, auth_headers):
    login = await client.post(
        "/api/v1/auth/login",
        data={"email": "test@example.com", "password": "testpassword123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    refresh_token = login.json()["refresh_token"]

    # Logout
    response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers=auth_headers,
    )
    assert response.status_code == 204

    # Now try to use the refresh token — must fail
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401
import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis

import app.core.db as db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import TokenOut
from app.schemas.user import UserCreate


async def register_user(data: UserCreate) -> dict:
    # Check email not already taken
    existing = await db.fetchrow(
        "SELECT id FROM users WHERE email = $1",
        data.email,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create tenant
    tenant = await db.fetchrow(
        """
        INSERT INTO tenants (name, slug)
        VALUES ($1, $2)
        RETURNING id, name, slug, is_active, created_at
        """,
        data.tenant_name,
        data.tenant_slug,
    )

    # Create user
    user = await db.fetchrow(
        """
        INSERT INTO users (tenant_id, email, hashed_password)
        VALUES ($1, $2, $3)
        RETURNING id, tenant_id, email, is_active, created_at
        """,
        tenant["id"],
        data.email,
        hash_password(data.password),
    )

    return dict(user)


async def login_user(email: str, password: str) -> TokenOut:
    user = await db.fetchrow(
        "SELECT id, tenant_id, hashed_password, is_active FROM users WHERE email = $1",
        email,
    )

    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(
        subject=str(user["id"]),
        tenant_id=str(user["tenant_id"]),
    )
    refresh_token = create_refresh_token(
        subject=str(user["id"]),
        tenant_id=str(user["tenant_id"]),
    )

    return TokenOut(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(refresh_token: str, redis: Redis) -> TokenOut:
    is_blacklisted = await redis.get(f"blacklist:{refresh_token}")
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    await redis.set(
        f"blacklist:{refresh_token}",
        "1",
        ex=60 * 60 * 24 * 7,
    )

    return TokenOut(
        access_token=create_access_token(
            subject=payload["sub"],
            tenant_id=payload["tenant_id"],
        ),
        refresh_token=create_refresh_token(
            subject=payload["sub"],
            tenant_id=payload["tenant_id"],
        ),
    )


async def logout_user(refresh_token: str, redis: Redis) -> None:
    try:
        decode_token(refresh_token)
    except ValueError:
        return
    await redis.set(
        f"blacklist:{refresh_token}",
        "1",
        ex=60 * 60 * 24 * 7,
    )
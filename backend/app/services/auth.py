import uuid

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import Tenant, User
from app.schemas import TokenOut, UserCreate


async def register_user(data: UserCreate, db: AsyncSession) -> User:
    # Check email not already taken
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create tenant first
    tenant = Tenant(
        name=data.tenant_name,
        slug=data.tenant_slug,
    )
    db.add(tenant)
    await db.flush()  # writes tenant to DB and gets its ID without committing

    # Create user
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.flush()

    return user


async def login_user(email: str, password: str, db: AsyncSession) -> TokenOut:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        tenant_id=str(user.tenant_id),
    )

    return TokenOut(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(refresh_token: str, redis: Redis) -> TokenOut:
    # Check if token is blacklisted
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

    # Blacklist the used refresh token immediately (rotation)
    await redis.set(
        f"blacklist:{refresh_token}",
        "1",
        ex=60 * 60 * 24 * 7,  # expire after 7 days (same as token TTL)
    )

    # Issue fresh pair
    new_access = create_access_token(
        subject=payload["sub"],
        tenant_id=payload["tenant_id"],
    )
    new_refresh = create_refresh_token(
        subject=payload["sub"],
        tenant_id=payload["tenant_id"],
    )

    return TokenOut(access_token=new_access, refresh_token=new_refresh)


async def logout_user(refresh_token: str, redis: Redis) -> None:
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        return  # already invalid, nothing to blacklist

    await redis.set(
        f"blacklist:{refresh_token}",
        "1",
        ex=60 * 60 * 24 * 7,
    )
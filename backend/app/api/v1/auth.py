from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_redis
from app.schemas.auth import RefreshRequest, TokenOut
from app.schemas.user import UserCreate, UserOut, LoginRequest
from app.services.auth import login_user, logout_user, refresh_tokens, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    user = await register_user(data, db)
    return user


@router.post("/login", response_model=TokenOut)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    # Accept JSON body with email/password
    return await login_user(data.email, data.password, db)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    data: RefreshRequest,
    redis: Redis = Depends(get_redis),
):
    return await refresh_tokens(data.refresh_token, redis)


@router.post("/logout", status_code=204)
async def logout(
    data: RefreshRequest,
    redis: Redis = Depends(get_redis),
    _: dict = Depends(get_current_user),  # enforces valid access token
):
    await logout_user(data.refresh_token, redis)
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from redis.asyncio import Redis

from app.api.deps import get_current_user, get_redis
from app.schemas.auth import RefreshRequest, TokenOut
from app.schemas.user import UserCreate, UserOut, LoginRequest
from app.services.auth import login_user, logout_user, refresh_tokens, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: UserCreate):
    user = await register_user(data)
    return user


@router.post("/login", response_model=TokenOut)
async def login(form_data: LoginRequest):
    return await login_user(form_data.email, form_data.password)


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
    _: dict = Depends(get_current_user),
):
    await logout_user(data.refresh_token, redis)
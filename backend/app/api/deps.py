from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from app.core.redis import get_redis_client
from app.core.security import decode_token

http_bearer = HTTPBearer()


async def get_redis() -> Redis:
    return get_redis_client()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authenticated",
        )
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return payload


async def get_current_tenant(
    current_user: dict = Depends(get_current_user),
) -> str:
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant associated with this token",
        )
    return tenant_id



async def get_tenant_from_api_key_or_jwt(
    x_api_key: str | None = Header(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
) -> tuple[str, str | None]:
    """
    Dual authentication dependency for the events endpoint.

    Accepts either:
    - X-API-Key: pk_live_xxxx  (write-only key from JS snippet)
    - Authorization: Bearer <jwt>  (JWT from dashboard or server-side code)

    API key takes priority if both are provided.
    """
    # Try API key first
    if x_api_key:
        from app.services.api_keys import verify_api_key
        result = await verify_api_key(x_api_key)
        if result:
            return result
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Fall back to JWT
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenant associated with this token",
            )
        return tenant_id, None

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide X-API-Key or Authorization header.",
    )
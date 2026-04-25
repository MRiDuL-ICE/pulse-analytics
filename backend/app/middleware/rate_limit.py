import time

from fastapi import Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis import get_redis_client

RATE_LIMIT = 100
WINDOW_SECONDS = 60
EXCLUDED_PATHS = {"/docs", "/openapi.json", "/redoc", "/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)

        redis: Redis = get_redis_client()
        identifier = self._get_identifier(request)
        is_limited, retry_after = await self._check_rate_limit(redis, identifier)

        if is_limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Try again later.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    def _get_identifier(self, request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token_prefix = auth[7:20]
            return f"rl:token:{token_prefix}"
        ip = request.client.host if request.client else "unknown"
        return f"rl:ip:{ip}"

    async def _check_rate_limit(
        self, redis: Redis, identifier: str
    ) -> tuple[bool, int]:
        now = time.time()
        window_start = now - WINDOW_SECONDS
        key = f"rate_limit:{identifier}"

        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, WINDOW_SECONDS)
        results = await pipe.execute()

        request_count = results[2]

        if request_count > RATE_LIMIT:
            oldest = await redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(WINDOW_SECONDS - (now - oldest[0][1]))
            else:
                retry_after = WINDOW_SECONDS
            return True, max(retry_after, 1)

        return False, 0
import time

from fastapi import Request, Response
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis import get_redis_client

# Limits per window
RATE_LIMIT = 100       # max requests
WINDOW_SECONDS = 60    # per 60 seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        redis: Redis = get_redis_client()

        # Identify the requester — use tenant_id from JWT if available,
        # fall back to IP address for unauthenticated routes
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
        """
        Try to extract tenant_id from the Authorization header for per-tenant
        limiting. Fall back to IP for unauthenticated requests.
        """
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            # Use the raw token as the key — avoids decoding JWT in middleware
            # which would add latency to every single request
            token_prefix = auth[7:20]  # first 13 chars — enough to be unique
            return f"rl:token:{token_prefix}"

        ip = request.client.host if request.client else "unknown"
        return f"rl:ip:{ip}"

    async def _check_rate_limit(
        self, redis: Redis, identifier: str
    ) -> tuple[bool, int]:
        """
        Sliding window algorithm using a Redis sorted set.
        Each request is stored as a member with its timestamp as the score.
        Old entries outside the window are pruned on every request.
        """
        now = time.time()
        window_start = now - WINDOW_SECONDS
        key = f"rate_limit:{identifier}"

        # Pipeline batches all Redis commands into one round trip
        pipe = redis.pipeline()
        # Remove entries older than the window
        pipe.zremrangebyscore(key, 0, window_start)
        # Add current request with timestamp as score
        pipe.zadd(key, {str(now): now})
        # Count requests in current window
        pipe.zcard(key)
        # Set key expiry so it auto-cleans from Redis
        pipe.expire(key, WINDOW_SECONDS)
        results = await pipe.execute()

        request_count = results[2]  # zcard result

        if request_count > RATE_LIMIT:
            # Calculate how long until the oldest request falls out of the window
            oldest = await redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(WINDOW_SECONDS - (now - oldest[0][1]))
            else:
                retry_after = WINDOW_SECONDS
            return True, max(retry_after, 1)

        return False, 0
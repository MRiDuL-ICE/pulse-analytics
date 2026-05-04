from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

# Module-level pool — created once, shared across all requests
_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            ssl_cert_reqs=None,  # ← don't verify Upstash cert
            socket_connect_timeout=10,
            decode_responses=True,   # return str instead of bytes
        )
    return _pool


def get_redis_client() -> Redis:
    return Redis(connection_pool=get_redis_pool())


async def close_redis_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
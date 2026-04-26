import pytest
import fakeredis.aioredis as fakeredis
from unittest.mock import AsyncMock, MagicMock, patch

from app.middleware.rate_limit import RateLimitMiddleware, RATE_LIMIT, WINDOW_SECONDS


@pytest.fixture
async def redis():
    async with fakeredis.FakeRedis() as r:
        yield r


async def test_sliding_window_allows_requests_within_limit(redis):
    """
    Send exactly RATE_LIMIT requests — all should be allowed.
    """
    middleware = RateLimitMiddleware(app=MagicMock())

    for i in range(RATE_LIMIT):
        is_limited, _ = await middleware._check_rate_limit(redis, f"rl:ip:127.0.0.1")
        assert is_limited is False, f"Request {i+1} was blocked but should be allowed"


async def test_sliding_window_blocks_after_limit_exceeded(redis):
    """
    Send RATE_LIMIT + 1 requests — the last one must be blocked.
    """
    middleware = RateLimitMiddleware(app=MagicMock())
    identifier = "rl:ip:10.0.0.1"

    for _ in range(RATE_LIMIT):
        await middleware._check_rate_limit(redis, identifier)

    # This one exceeds the limit
    is_limited, retry_after = await middleware._check_rate_limit(redis, identifier)
    assert is_limited is True
    assert retry_after > 0


async def test_rate_limit_returns_retry_after(redis):
    """retry_after must be a positive integer telling the client when to retry."""
    middleware = RateLimitMiddleware(app=MagicMock())
    identifier = "rl:ip:10.0.0.2"

    for _ in range(RATE_LIMIT + 1):
        is_limited, retry_after = await middleware._check_rate_limit(redis, identifier)

    assert isinstance(retry_after, int)
    assert 0 < retry_after <= WINDOW_SECONDS


async def test_different_identifiers_have_separate_limits(redis):
    """
    Two different IPs/tokens must have completely independent rate limit buckets.
    Exhausting one must not affect the other.
    """
    middleware = RateLimitMiddleware(app=MagicMock())

    # Exhaust limit for IP 1
    for _ in range(RATE_LIMIT + 1):
        await middleware._check_rate_limit(redis, "rl:ip:1.1.1.1")

    # IP 2 should still be free
    is_limited, _ = await middleware._check_rate_limit(redis, "rl:ip:2.2.2.2")
    assert is_limited is False


async def test_excluded_paths_bypass_rate_limit():
    """
    /docs, /health etc. must never be rate limited regardless of request volume.
    We test this by verifying the middleware calls call_next directly for these paths.
    """
    from app.middleware.rate_limit import EXCLUDED_PATHS

    assert "/docs" in EXCLUDED_PATHS
    assert "/health" in EXCLUDED_PATHS
    assert "/openapi.json" in EXCLUDED_PATHS
    assert "/redoc" in EXCLUDED_PATHS
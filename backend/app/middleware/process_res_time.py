import time
import logging
from fastapi import Request

logger = logging.getLogger("api.performance")


def format_duration(seconds: float) -> str:
    ns = seconds * 1_000_000_000
    us = seconds * 1_000_000
    ms = seconds * 1_000

    if ns < 1_000:
        return f"{ns:.0f} ns"
    elif us < 1_000:
        return f"{us:.2f} µs"
    elif ms < 1_000:
        return f"{ms:.2f} ms"
    else:
        return f"{seconds:.4f} s"


async def process_res_time_middleware(request: Request, call_next):
    start = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start
    formatted = format_duration(duration)

    # attach to response headers (Swagger / client visible)
    response.headers["X-Process-Time"] = formatted

    # optional debug metadata
    response.headers["X-Process-Seconds"] = f"{duration:.6f}"

    # 🚨 slow API logging threshold (200ms default)
    if duration > 0.2:
        logger.warning(
            f"SLOW REQUEST: {request.method} {request.url.path} took {formatted}"
        )
    else:
        logger.info(
            f"{request.method} {request.url.path} took {formatted}"
        )

    return response
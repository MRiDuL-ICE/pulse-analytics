from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.core.db import create_pool, close_pool
from app.core.redis import close_redis_pool, get_redis_pool
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.process_res_time import process_res_time_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up...")
    await create_pool()       # asyncpg pool
    get_redis_pool()          # redis pool
    print("All pools ready.")

    yield

    print("Shutting down...")
    await close_pool()
    await close_redis_pool()
    print("All pools closed.")



app = FastAPI(
    title="Pulse Analytics",
    version="0.1.0",
    lifespan=lifespan,
)


app.middleware("http")(process_res_time_middleware)
app.add_middleware(RateLimitMiddleware)



app.include_router(auth_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}


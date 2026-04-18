from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.deps import get_db, get_redis

from app.core.database import engine
from app.core.redis import close_redis_pool, get_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────
    print("Starting up — initialising connection pools...")
    get_redis_pool()          # warms up the Redis pool
    # DB engine pool is created lazily on first use by SQLAlchemy
    print("Connection pools ready.")

    yield  # app runs here

    # ── Shutdown ─────────────────────────────────────────
    print("Shutting down — closing connection pools...")
    await close_redis_pool()
    await engine.dispose()    # closes all Postgres connections cleanly
    print("Pools closed. Goodbye.")


app = FastAPI(
    title="Pulse Analytics",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"db": "ok", "result": result.scalar()}


@app.get("/health/redis")
async def health_redis(redis: Redis = Depends(get_redis)):
    await redis.set("ping", "pong", ex=10)
    value = await redis.get("ping")
    return {"redis": "ok", "value": value}
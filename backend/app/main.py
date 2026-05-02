import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.tenants import router as tenants_router
from app.core.db import close_pool, create_pool
from app.core.redis import close_redis_pool, get_redis_pool
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.process_res_time import process_res_time_middleware
from app.api.v1.api_keys import router as api_keys_router
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.sites import router as sites_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_id = os.environ.get("WORKER_ID", "unknown")
    print(f"Worker {worker_id} starting up...")
    await create_pool()
    get_redis_pool()
    print(f"Worker {worker_id} — all pools ready.")

    yield

    print(f"Worker {worker_id} shutting down...")
    await close_pool()
    await close_redis_pool()
    print(f"Worker {worker_id} — all pools closed.")


app = FastAPI(
    title="Pulse Analytics",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost",   # Next.js default
    "http://127.0.0.1",
    "http://localhost:3000",   # Next.js default
    "http://127.0.0.1:3000",
    "http://localhost:4000",   # Next.js default
    "http://127.0.0.1:4000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],   # or specify ["GET", "POST"]
    allow_headers=["*"],
)

app.middleware("http")(process_res_time_middleware)
app.add_middleware(RateLimitMiddleware)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(sites_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(tenants_router, prefix="/api/v1")
app.include_router(api_keys_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
import asyncpg

from app.core.config import settings

# Primary pool — all writes go here
_primary_pool: asyncpg.Pool | None = None

# Replica pool — read-only analytics queries go here
_replica_pool: asyncpg.Pool | None = None


async def create_pool() -> None:
    global _primary_pool, _replica_pool

    _primary_pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        min_size=5,
        max_size=20,
        command_timeout=30,
    )

    # Try to connect to replica — fall back to primary if unavailable
    replica_host = getattr(settings, "postgres_replica_host", None)
    if replica_host:
        try:
            _replica_pool = await asyncpg.create_pool(
                host=replica_host,
                port=getattr(settings, "postgres_replica_port", 5432),
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_db,
                min_size=3,
                max_size=15,
                command_timeout=5,  # short timeout so startup isn't delayed
            )
            print("Replica pool connected.")
        except Exception as e:
            print(f"Replica unavailable ({e}) — falling back to primary for reads.")
            _replica_pool = _primary_pool
    else:
        _replica_pool = _primary_pool

async def close_pool() -> None:
    global _primary_pool, _replica_pool
    if _primary_pool:
        await _primary_pool.close()
        _primary_pool = None
    if _replica_pool and _replica_pool is not _primary_pool:
        await _replica_pool.close()
        _replica_pool = None


def get_primary_pool() -> asyncpg.Pool:
    if _primary_pool is None:
        raise RuntimeError("Primary pool not initialised.")
    return _primary_pool


def get_replica_pool() -> asyncpg.Pool:
    if _replica_pool is None:
        raise RuntimeError("Replica pool not initialised.")
    return _replica_pool


# ── Primary (write) helpers ───────────────────────────────────────────────────

async def execute(query: str, *args) -> str:
    async with get_primary_pool().acquire() as conn:
        return await conn.execute(query, *args)


async def executemany(query: str, args: list) -> None:
    async with get_primary_pool().acquire() as conn:
        await conn.executemany(query, args)


async def fetchrow(query: str, *args) -> asyncpg.Record | None:
    async with get_primary_pool().acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    async with get_primary_pool().acquire() as conn:
        return await conn.fetchval(query, *args)


# ── Replica (read) helpers ────────────────────────────────────────────────────

async def fetch(query: str, *args) -> list[asyncpg.Record]:
    """All SELECT queries use the replica pool."""
    async with get_replica_pool().acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow_replica(query: str, *args) -> asyncpg.Record | None:
    """Single row SELECT from replica."""
    async with get_replica_pool().acquire() as conn:
        return await conn.fetchrow(query, *args)
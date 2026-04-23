import asyncpg

from app.core.config import settings


_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=settings.postgres_db,
        min_size=5,       # connection kept open always
        max_size=20,      # max connection under load
        command_timeout=30,
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized, Call create_pool first")
    return _pool

async def fetch(query: str, *args) -> list[asyncpg.Record]:
    """Run a SELECT, return all rows."""
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args) -> asyncpg.Record | None:
    """Run a SELECT, return one row or None."""
    async with get_pool().acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    """Run a SELECT, return a single value."""
    async with get_pool().acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args) -> str:
    """Run an INSERT / UPDATE / DELETE."""
    async with get_pool().acquire() as conn:
        return await conn.execute(query, *args)


async def executemany(query: str, args: list) -> None:
    """Run an INSERT / UPDATE for multiple rows."""
    async with get_pool().acquire() as conn:
        await conn.executemany(query, args)
"""
Run with: docker compose exec api python migrations/run_migrations.py
Applies any .sql files in /app/migrations/ that haven't been run yet.
"""
import asyncio
import os
import ssl

from pathlib import Path

import asyncpg


async def run():
    # SSL for Aiven
    ssl_ctx = ssl.create_default_context(cafile="/app/certs/ca.pem")
    ssl_ctx.check_hostname = True
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED

    conn = await asyncpg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        database=os.environ["POSTGRES_DB"],
        ssl=ssl_ctx,
    )

    # Ensure the migrations tracking table exists
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id          SERIAL PRIMARY KEY,
            filename    VARCHAR(255) NOT NULL UNIQUE,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Get already-applied migrations
    applied = {
        row["filename"]
        for row in await conn.fetch("SELECT filename FROM migrations")
    }

    # Find all .sql files sorted by name
    migrations_dir = Path(__file__).parent
    sql_files = sorted(migrations_dir.glob("*.sql"))

    for sql_file in sql_files:
        if sql_file.name in applied:
            print(f"  skipping {sql_file.name} — already applied")
            continue

        print(f"  applying {sql_file.name} ...")
        sql = sql_file.read_text()

        async with conn.transaction():
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO migrations (filename) VALUES ($1) ON CONFLICT DO NOTHING",
                sql_file.name,
            )
        print(f"  done ✓")

    await conn.close()
    print("All migrations applied.")


if __name__ == "__main__":
    asyncio.run(run())
from pathlib import Path

import asyncpg


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=database_url)


async def bootstrap_schema(pool: asyncpg.Pool, schema_path: str | Path = "sql/schema.sql") -> None:
    sql = Path(schema_path).read_text(encoding="utf-8")
    async with pool.acquire() as connection:
        await connection.execute(sql)

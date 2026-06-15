from pathlib import Path

import asyncpg


async def create_pool(database_url: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=database_url)


async def bootstrap_schema(pool: asyncpg.Pool, schema_path: str | Path = "sql/schema.sql") -> None:
    sql = Path(schema_path).read_text(encoding="utf-8")
    async with pool.acquire() as connection:
        await connection.execute(sql)
        await connection.execute(
            """
            ALTER TABLE daily_reports
                ALTER COLUMN submitted_latitude DROP NOT NULL,
                ALTER COLUMN submitted_longitude DROP NOT NULL,
                ALTER COLUMN distance_from_store_meter DROP NOT NULL;

            ALTER TABLE daily_reports
                DROP CONSTRAINT IF EXISTS daily_reports_location_status_check;

            ALTER TABLE daily_reports
                ADD CONSTRAINT daily_reports_location_status_check
                CHECK (location_status IN ('in_radius', 'out_of_radius', 'manual_store_selection'));
            """
        )

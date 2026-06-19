import asyncpg


class RegionsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_provinces(self, active_status: str) -> list[str]:
        rows = await self._pool.fetch(
            """
            SELECT DISTINCT province
            FROM regions
            WHERE status = $1
            ORDER BY province
            """,
            active_status,
        )
        return [row["province"] for row in rows]

    async def list_cities(self, province: str, active_status: str) -> list[str]:
        rows = await self._pool.fetch(
            """
            SELECT city
            FROM regions
            WHERE province = $1
              AND status = $2
            ORDER BY city
            """,
            province,
            active_status,
        )
        return [row["city"] for row in rows]

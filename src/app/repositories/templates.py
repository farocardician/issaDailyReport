import asyncpg


class TemplatesRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_all(self) -> dict[str, str]:
        rows = await self._pool.fetch("SELECT key, message FROM ui_translate ORDER BY key")
        return {row["key"]: row["message"] for row in rows}

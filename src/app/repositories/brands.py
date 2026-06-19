import asyncpg

from app.domain.brands import Brand


class BrandsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, active_status: str) -> list[Brand]:
        rows = await self._pool.fetch(
            """
            SELECT brand_id, label, short_code, sort_order, status
            FROM brands
            WHERE status = $1
            ORDER BY sort_order, label
            """,
            active_status,
        )
        return [_to_brand(row) for row in rows]


def _to_brand(row: asyncpg.Record) -> Brand:
    return Brand(
        brand_id=row["brand_id"],
        label=row["label"],
        short_code=row["short_code"],
        sort_order=row["sort_order"],
        status=row["status"],
    )

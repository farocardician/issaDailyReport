import asyncpg

from app.domain.outlet import Outlet


class OutletRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, active_status: str) -> list[Outlet]:
        rows = await self._pool.fetch(
            """
            SELECT outlet_id, label, short_code, sort_order, status
            FROM outlet
            WHERE status = $1
            ORDER BY sort_order, label
            """,
            active_status,
        )
        return [_to_outlet(row) for row in rows]


def _to_outlet(row: asyncpg.Record) -> Outlet:
    return Outlet(
        outlet_id=row["outlet_id"],
        label=row["label"],
        short_code=row["short_code"],
        sort_order=row["sort_order"],
        status=row["status"],
    )

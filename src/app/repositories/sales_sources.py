import asyncpg

from app.domain.sales_sources import GmvSource


class SalesSourcesRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, active_status: str) -> list[GmvSource]:
        rows = await self._pool.fetch(
            """
            SELECT gmv_source_id, label, source_type, requires_traffic, sort_order, status
            FROM gmv_sources
            WHERE status = $1
            ORDER BY sort_order, label
            """,
            active_status,
        )
        return [_to_gmv_source(row) for row in rows]


def _to_gmv_source(row: asyncpg.Record) -> GmvSource:
    return GmvSource(
        gmv_source_id=row["gmv_source_id"],
        label=row["label"],
        source_type=row["source_type"],
        requires_traffic=row["requires_traffic"],
        sort_order=row["sort_order"],
        status=row["status"],
    )

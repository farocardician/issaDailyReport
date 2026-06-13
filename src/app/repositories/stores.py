import asyncpg

from app.domain.store_matching import StoreLocation


class StoresRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, active_status: str) -> list[StoreLocation]:
        rows = await self._pool.fetch(
            """
            SELECT store_id, department_store, branch, city, brand, latitude, longitude,
                   allowed_radius_meter, status, notes
            FROM stores
            WHERE status = $1
            ORDER BY brand, department_store, branch, city
            """,
            active_status,
        )
        return [_to_store(row) for row in rows]

    async def get_by_id(self, store_id: str) -> StoreLocation | None:
        row = await self._pool.fetchrow(
            """
            SELECT store_id, department_store, branch, city, brand, latitude, longitude,
                   allowed_radius_meter, status, notes
            FROM stores
            WHERE store_id = $1
            """,
            store_id,
        )
        return _to_store(row) if row else None


def _to_store(row: asyncpg.Record) -> StoreLocation:
    return StoreLocation(
        store_id=row["store_id"],
        department_store=row["department_store"],
        branch=row["branch"],
        city=row["city"],
        brand=row["brand"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        allowed_radius_meter=row["allowed_radius_meter"],
        status=row["status"],
        notes=row["notes"],
    )

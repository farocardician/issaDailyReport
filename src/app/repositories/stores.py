import asyncpg

from app.domain.store_matching import StoreLocation


class StoresRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, active_status: str) -> list[StoreLocation]:
        rows = await self._pool.fetch(
            """
            SELECT store_id, outlet, branch, city, brand, latitude, longitude,
                   allowed_radius_meter, status, notes
            FROM stores
            WHERE status = $1
            ORDER BY brand, outlet, branch, city
            """,
            active_status,
        )
        return [_to_store(row) for row in rows]

    async def list_all(self) -> list[StoreLocation]:
        rows = await self._pool.fetch(
            """
            SELECT store_id, outlet, branch, city, brand, latitude, longitude,
                   allowed_radius_meter, status, notes
            FROM stores
            ORDER BY brand, outlet, branch, city
            """,
        )
        return [_to_store(row) for row in rows]

    async def get_by_id(self, store_id: str) -> StoreLocation | None:
        row = await self._pool.fetchrow(
            """
            SELECT store_id, outlet, branch, city, brand, latitude, longitude,
                   allowed_radius_meter, status, notes
            FROM stores
            WHERE store_id = $1
            """,
            store_id,
        )
        return _to_store(row) if row else None

    async def create_store(
        self,
        store_id: str,
        brand: str,
        outlet: str,
        branch: str,
        city: str,
        latitude: float,
        longitude: float,
        allowed_radius_meter: int,
        notes: str | None,
        status: str,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO stores (
                store_id, brand, outlet, branch, city, latitude, longitude,
                allowed_radius_meter, notes, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            store_id,
            brand,
            outlet,
            branch,
            city,
            latitude,
            longitude,
            allowed_radius_meter,
            notes,
            status,
        )

    async def update_store(
        self,
        store_id: str,
        brand: str,
        outlet: str,
        branch: str,
        city: str,
        latitude: float,
        longitude: float,
        allowed_radius_meter: int,
        notes: str | None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE stores
            SET brand = $2,
                outlet = $3,
                branch = $4,
                city = $5,
                latitude = $6,
                longitude = $7,
                allowed_radius_meter = $8,
                notes = $9
            WHERE store_id = $1
            """,
            store_id,
            brand,
            outlet,
            branch,
            city,
            latitude,
            longitude,
            allowed_radius_meter,
            notes,
        )

    async def set_status(self, store_id: str, status: str) -> None:
        await self._pool.execute(
            """
            UPDATE stores
            SET status = $2
            WHERE store_id = $1
            """,
            store_id,
            status,
        )


def _to_store(row: asyncpg.Record) -> StoreLocation:
    return StoreLocation(
        store_id=row["store_id"],
        outlet=row["outlet"],
        branch=row["branch"],
        city=row["city"],
        brand=row["brand"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        allowed_radius_meter=row["allowed_radius_meter"],
        status=row["status"],
        notes=row["notes"],
    )

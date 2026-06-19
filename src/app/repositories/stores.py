import asyncpg

from app.domain.store_matching import StoreLocation


class StoresRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, active_status: str) -> list[StoreLocation]:
        rows = await self._pool.fetch(
            """
            SELECT s.store_id, s.outlet, s.branch, s.city, s.province, s.brand,
                   s.latitude, s.longitude, s.allowed_radius_meter, s.status, s.notes,
                   b.short_code AS brand_short, o.short_code AS outlet_short,
                   r.short_code AS city_short
            FROM stores s
            LEFT JOIN brands b ON b.label = s.brand
            LEFT JOIN outlet o ON o.label = s.outlet
            LEFT JOIN regions r ON r.province = s.province AND r.city = s.city
            WHERE s.status = $1
            ORDER BY s.brand, s.outlet, s.branch, s.city
            """,
            active_status,
        )
        return [_to_store(row) for row in rows]

    async def list_all(self) -> list[StoreLocation]:
        rows = await self._pool.fetch(
            """
            SELECT s.store_id, s.outlet, s.branch, s.city, s.province, s.brand,
                   s.latitude, s.longitude, s.allowed_radius_meter, s.status, s.notes,
                   b.short_code AS brand_short, o.short_code AS outlet_short,
                   r.short_code AS city_short
            FROM stores s
            LEFT JOIN brands b ON b.label = s.brand
            LEFT JOIN outlet o ON o.label = s.outlet
            LEFT JOIN regions r ON r.province = s.province AND r.city = s.city
            ORDER BY s.brand, s.outlet, s.branch, s.city
            """,
        )
        return [_to_store(row) for row in rows]

    async def get_by_id(self, store_id: str) -> StoreLocation | None:
        row = await self._pool.fetchrow(
            """
            SELECT s.store_id, s.outlet, s.branch, s.city, s.province, s.brand,
                   s.latitude, s.longitude, s.allowed_radius_meter, s.status, s.notes,
                   b.short_code AS brand_short, o.short_code AS outlet_short,
                   r.short_code AS city_short
            FROM stores s
            LEFT JOIN brands b ON b.label = s.brand
            LEFT JOIN outlet o ON o.label = s.outlet
            LEFT JOIN regions r ON r.province = s.province AND r.city = s.city
            WHERE s.store_id = $1
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
        province: str,
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
                store_id, brand, outlet, branch, province, city, latitude, longitude,
                allowed_radius_meter, notes, status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            store_id,
            brand,
            outlet,
            branch,
            province,
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
        province: str,
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
                province = $5,
                city = $6,
                latitude = $7,
                longitude = $8,
                allowed_radius_meter = $9,
                notes = $10
            WHERE store_id = $1
            """,
            store_id,
            brand,
            outlet,
            branch,
            province,
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
        province=row["province"],
        brand_short=_short_or_none(row["brand_short"]),
        outlet_short=_short_or_none(row["outlet_short"]),
        city_short=_short_or_none(row["city_short"]),
    )


def _short_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None

from datetime import date
from typing import Any

import asyncpg


class ReportsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def exists_for_store_date(self, store_id: str, report_date: date) -> bool:
        return await self._pool.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM daily_reports
                WHERE store_id = $1 AND report_date = $2
            )
            """,
            store_id,
            report_date,
        )

    async def report_id_exists(self, report_id: str) -> bool:
        return await self._pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM daily_reports WHERE report_id = $1)",
            report_id,
        )

    async def create(self, report: dict[str, Any], sales_rows: list[dict[str, Any]]) -> None:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    INSERT INTO daily_reports (
                        report_id, report_date, store_id, user_id, stock_issue,
                        submitted_latitude, submitted_longitude, distance_from_store_meter,
                        note, submission_status, location_status, created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    report["report_id"],
                    report["report_date"],
                    report["store_id"],
                    report["user_id"],
                    report["stock_issue"],
                    report["submitted_latitude"],
                    report["submitted_longitude"],
                    report["distance_from_store_meter"],
                    report["note"],
                    report["submission_status"],
                    report["location_status"],
                    report["created_at"],
                )
                for row in sales_rows:
                    await connection.execute(
                        """
                        INSERT INTO daily_report_sales (
                            report_id, gmv_source_id, source_label, source_type,
                            requires_traffic, traffic, gmv, order_count, pieces_sold, sort_order
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        report["report_id"],
                        row["gmv_source_id"],
                        row["source_label"],
                        row["source_type"],
                        row["requires_traffic"],
                        row["traffic"],
                        row["gmv"],
                        row["order_count"],
                        row["pieces_sold"],
                        row["sort_order"],
                    )

    async def list_for_export(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT dr.report_id, dr.report_date, dr.user_id,
                   u.name  AS staff_name, u.email AS staff_email,
                   dr.store_id, s.brand, s.outlet, s.branch, s.city,
                   drs.source_label AS sales_source, drs.source_type,
                   drs.traffic, drs.gmv, drs.order_count, drs.pieces_sold,
                   dr.stock_issue, dr.note, dr.submission_status,
                   dr.location_status, dr.distance_from_store_meter, dr.created_at
            FROM daily_reports dr
            JOIN stores s ON s.store_id = dr.store_id
            JOIN users  u ON u.user_id  = dr.user_id
            LEFT JOIN daily_report_sales drs ON drs.report_id = dr.report_id
            ORDER BY dr.created_at, dr.report_id, drs.sort_order
            """
        )
        return [dict(row) for row in rows]

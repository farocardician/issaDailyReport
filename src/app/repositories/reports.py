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

    async def create(self, report: dict[str, Any]) -> None:
        await self._pool.execute(
            """
            INSERT INTO daily_reports (
                report_id, report_date, store_id, user_id, traffic, offline_gmv,
                online_gmv, order_count, pieces_sold, no_buy_reason, stock_issue,
                submitted_latitude, submitted_longitude, distance_from_store_meter,
                note, submission_status, location_status, created_at
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, $17, $18
            )
            """,
            report["report_id"],
            report["report_date"],
            report["store_id"],
            report["user_id"],
            report["traffic"],
            report["offline_gmv"],
            report["online_gmv"],
            report["order_count"],
            report["pieces_sold"],
            report["no_buy_reason"],
            report["stock_issue"],
            report["submitted_latitude"],
            report["submitted_longitude"],
            report["distance_from_store_meter"],
            report["note"],
            report["submission_status"],
            report["location_status"],
            report["created_at"],
        )

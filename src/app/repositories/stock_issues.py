import asyncpg

from app.domain.stock_issues import StockIssue


class StockIssuesRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_active(self, active_status: str) -> list[StockIssue]:
        rows = await self._pool.fetch(
            """
            SELECT stock_issue_id, label, sort_order, status
            FROM stock_issues
            WHERE status = $1
            ORDER BY sort_order, label
            """,
            active_status,
        )
        return [_to_stock_issue(row) for row in rows]


def _to_stock_issue(row: asyncpg.Record) -> StockIssue:
    return StockIssue(
        stock_issue_id=row["stock_issue_id"],
        label=row["label"],
        sort_order=row["sort_order"],
        status=row["status"],
    )

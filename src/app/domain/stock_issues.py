from dataclasses import dataclass


@dataclass(frozen=True)
class StockIssue:
    stock_issue_id: str
    label: str
    sort_order: int
    status: str

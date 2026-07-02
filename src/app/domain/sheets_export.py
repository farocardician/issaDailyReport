from datetime import date, datetime
from decimal import Decimal
from typing import Any

MASTER_FLAT_HEADER: list[str] = [
    "report_id",
    "report_date",
    "user_id",
    "staff_name",
    "staff_email",
    "store_id",
    "brand",
    "outlet",
    "branch",
    "city",
    "sales_source",
    "source_type",
    "traffic",
    "gmv",
    "order_count",
    "pieces_sold",
    "stock_issue",
    "note",
    "submission_status",
    "location_status",
    "distance_from_store_meter",
    "created_at",
]

_NUMERIC_COLUMNS = {
    "traffic",
    "gmv",
    "order_count",
    "pieces_sold",
    "distance_from_store_meter",
}


def build_master_flat_rows(records: list[dict[str, Any]]) -> list[list[Any]]:
    """One sheet row per record, cells in MASTER_FLAT_HEADER order."""
    return [[_format_cell(column, record.get(column)) for column in MASTER_FLAT_HEADER] for record in records]


def _format_cell(column: str, value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if column in _NUMERIC_COLUMNS:
        return _format_number(value)
    return value


def _format_number(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value

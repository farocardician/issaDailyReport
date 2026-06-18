from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class GmvSource:
    gmv_source_id: str
    label: str
    source_type: str
    requires_traffic: bool
    sort_order: int
    status: str


SALES_FIELDS = ("gmv", "order_count", "pieces_sold")


def source_fields(requires_traffic: bool) -> tuple[str, ...]:
    return ("traffic", *SALES_FIELDS) if requires_traffic else SALES_FIELDS


def input_plan(specs: list[tuple[str, bool]]) -> list[tuple[str, str]]:
    return [
        (source_id, field)
        for source_id, requires_traffic in specs
        for field in source_fields(requires_traffic)
    ]


def sales_totals(sales_data: Mapping[str, Mapping[str, int]]) -> dict[str, int]:
    return {
        "gmv": sum(int(row.get("gmv", 0)) for row in sales_data.values()),
        "order_count": sum(int(row.get("order_count", 0)) for row in sales_data.values()),
        "pieces_sold": sum(int(row.get("pieces_sold", 0)) for row in sales_data.values()),
    }

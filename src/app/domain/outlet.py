from dataclasses import dataclass


@dataclass(frozen=True)
class Outlet:
    outlet_id: str
    label: str
    short_code: str
    sort_order: int
    status: str

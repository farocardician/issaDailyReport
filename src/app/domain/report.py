import random
import re
from datetime import datetime
from typing import Any

_RANDOM = random.SystemRandom()
REPORT_ID_PATTERN = re.compile(r"^RPT-\d{8}-\d{6}-\d{4}$")


def generate_report_id(now: datetime) -> str:
    return f"RPT-{now:%Y%m%d-%H%M%S}-{_RANDOM.randint(0, 9999):04d}"


def location_status(distance: float | None, effective_radius: int | None) -> str:
    if distance is None or effective_radius is None:
        return "manual_store_selection"
    return "in_radius" if distance <= effective_radius else "out_of_radius"


def build_summary(draft_report: dict[str, Any], store_label: str) -> dict[str, Any]:
    return {
        "store_label": store_label,
        "sales_breakdown": draft_report["sales_breakdown"],
        "total_gmv": draft_report["total_gmv"],
        "total_order": draft_report["total_order"],
        "total_pieces": draft_report["total_pieces"],
        "stock_issue": draft_report["stock_issue"],
        "note": draft_report["note"],
    }

import random
import re
from datetime import datetime
from typing import Any

_RANDOM = random.SystemRandom()
REPORT_ID_PATTERN = re.compile(r"^RPT-\d{8}-\d{6}-\d{4}$")


def generate_report_id(now: datetime) -> str:
    return f"RPT-{now:%Y%m%d-%H%M%S}-{_RANDOM.randint(0, 9999):04d}"


def location_status(distance: float, effective_radius: int) -> str:
    return "in_radius" if distance <= effective_radius else "out_of_radius"


def build_summary(draft_report: dict[str, Any], store_label: str) -> dict[str, Any]:
    return {
        "store_label": store_label,
        "traffic": draft_report["traffic"],
        "gmv": draft_report["offline_gmv"],
        "online_gmv": draft_report["online_gmv"],
        "order": draft_report["order_count"],
        "pieces": draft_report["pieces_sold"],
        "no_buy_reason": draft_report["no_buy_reason"],
        "stock_issue": draft_report["stock_issue"],
        "note": draft_report["note"],
    }

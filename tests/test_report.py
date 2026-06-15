import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.report import generate_report_id, location_status


def test_location_status() -> None:
    assert location_status(99.9, 100) == "in_radius"
    assert location_status(100, 100) == "in_radius"
    assert location_status(100.1, 100) == "out_of_radius"
    assert location_status(None, None) == "manual_store_selection"


def test_generate_report_id_format() -> None:
    now = datetime(2026, 6, 13, 22, 26, 0, tzinfo=ZoneInfo("Asia/Jakarta"))

    report_id = generate_report_id(now)

    assert re.match(r"^RPT-20260613-222600-\d{4}$", report_id)

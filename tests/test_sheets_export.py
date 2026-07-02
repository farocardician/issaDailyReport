from datetime import date, datetime, timezone
from decimal import Decimal

from app.domain.sheets_export import MASTER_FLAT_HEADER, build_master_flat_rows


def test_master_flat_header_is_stable() -> None:
    assert MASTER_FLAT_HEADER == [
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
    assert len(MASTER_FLAT_HEADER) == 22


def test_build_master_flat_rows_formats_values_in_header_order() -> None:
    created_at = datetime(2026, 7, 2, 9, 30, 15, tzinfo=timezone.utc)
    records = [
        {
            "report_id": "RPT-1",
            "report_date": date(2026, 7, 2),
            "user_id": "U1",
            "staff_name": "Staff One",
            "staff_email": None,
            "store_id": "S1",
            "brand": "VIZU",
            "outlet": "Outlet",
            "branch": "Branch",
            "city": "Jakarta",
            "sales_source": "Store",
            "source_type": "offline",
            "traffic": None,
            "gmv": Decimal("100000.50"),
            "order_count": 2,
            "pieces_sold": 3,
            "stock_issue": "-",
            "note": "OK",
            "submission_status": "submitted",
            "location_status": "in_radius",
            "distance_from_store_meter": Decimal("12.5"),
            "created_at": created_at,
        },
        {
            "report_id": "RPT-1",
            "report_date": date(2026, 7, 2),
            "user_id": "U1",
            "staff_name": "Staff One",
            "staff_email": "staff@example.com",
            "store_id": "S1",
            "brand": "VIZU",
            "outlet": "Outlet",
            "branch": "Branch",
            "city": "Jakarta",
            "sales_source": "Online",
            "source_type": "online",
            "traffic": 10,
            "gmv": Decimal("250000"),
            "order_count": 4,
            "pieces_sold": 5,
            "stock_issue": "-",
            "note": "OK",
            "submission_status": "submitted",
            "location_status": "in_radius",
            "distance_from_store_meter": Decimal("12"),
            "created_at": created_at,
        },
        {
            "report_id": "RPT-2",
            "report_date": date(2026, 7, 3),
            "user_id": "U2",
            "staff_name": "Staff Two",
            "staff_email": None,
            "store_id": "S2",
            "brand": "VIZU",
            "outlet": "Outlet",
            "branch": "Branch",
            "city": "Bandung",
            "sales_source": None,
            "source_type": None,
            "traffic": None,
            "gmv": None,
            "order_count": None,
            "pieces_sold": None,
            "stock_issue": "Tidak Ada Penjualan",
            "note": "",
            "submission_status": "submitted",
            "location_status": "manual_store_selection",
            "distance_from_store_meter": None,
            "created_at": created_at,
        },
    ]

    rows = build_master_flat_rows(records)

    assert rows[0] == [
        "RPT-1",
        "2026-07-02",
        "U1",
        "Staff One",
        "",
        "S1",
        "VIZU",
        "Outlet",
        "Branch",
        "Jakarta",
        "Store",
        "offline",
        "",
        100000.5,
        2,
        3,
        "-",
        "OK",
        "submitted",
        "in_radius",
        12.5,
        "2026-07-02T09:30:15+00:00",
    ]
    assert rows[1][0] == "RPT-1"
    assert rows[1][13] == 250000
    assert rows[1][20] == 12
    assert rows[2][10:16] == ["", "", "", "", "", ""]

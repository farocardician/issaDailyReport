from app.domain.outlet import Outlet
from app.repositories.outlet import _to_outlet


def test_outlet_model_uses_master_table_fields() -> None:
    outlet = Outlet("SOG", "Sogo", "SOG", 1, "Aktif")

    assert outlet.outlet_id == "SOG"
    assert outlet.label == "Sogo"
    assert outlet.short_code == "SOG"
    assert outlet.sort_order == 1
    assert outlet.status == "Aktif"


def test_outlet_repository_row_mapping() -> None:
    row = {
        "outlet_id": "CRL",
        "label": "Central",
        "short_code": "CRL",
        "sort_order": 2,
        "status": "Aktif",
    }

    assert _to_outlet(row) == Outlet("CRL", "Central", "CRL", 2, "Aktif")

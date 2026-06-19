from datetime import UTC, datetime

import pytest

from app.domain.store_management import (
    generate_store_id,
    is_duplicate_identity,
    store_identity,
    validate_store_field,
)
from app.domain.store_matching import StoreLocation


@pytest.mark.parametrize(
    ("field", "error_key"),
    [
        ("brand", "STORE_ERROR_BRAND_REQUIRED"),
        ("outlet", "STORE_ERROR_OUTLET_REQUIRED"),
        ("branch", "STORE_ERROR_BRANCH_REQUIRED"),
        ("province", "STORE_ERROR_PROVINCE_REQUIRED"),
        ("city", "STORE_ERROR_CITY_REQUIRED"),
    ],
)
def test_validate_store_field_requires_text_fields(field: str, error_key: str) -> None:
    result = validate_store_field(field, " ")

    assert result.ok is False
    assert result.error_key == error_key


def test_validate_store_field_accepts_comma_decimal_coordinates() -> None:
    latitude = validate_store_field("latitude", "-6,2")
    longitude = validate_store_field("longitude", "106,8")

    assert latitude.ok is True
    assert latitude.value == -6.2
    assert longitude.ok is True
    assert longitude.value == 106.8


@pytest.mark.parametrize(
    ("field", "value", "error_key"),
    [
        ("latitude", "-91", "STORE_ERROR_LATITUDE_INVALID"),
        ("latitude", "91", "STORE_ERROR_LATITUDE_INVALID"),
        ("latitude", "abc", "STORE_ERROR_LATITUDE_INVALID"),
        ("longitude", "-181", "STORE_ERROR_LONGITUDE_INVALID"),
        ("longitude", "181", "STORE_ERROR_LONGITUDE_INVALID"),
        ("longitude", "abc", "STORE_ERROR_LONGITUDE_INVALID"),
    ],
)
def test_validate_store_field_rejects_invalid_coordinates(field: str, value: str, error_key: str) -> None:
    result = validate_store_field(field, value)

    assert result.ok is False
    assert result.error_key == error_key


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_validate_store_field_rejects_non_positive_radius(value: str) -> None:
    result = validate_store_field("allowed_radius", value)

    assert result.ok is False
    assert result.error_key == "STORE_ERROR_RADIUS_INVALID"


def test_validate_store_field_accepts_positive_radius() -> None:
    result = validate_store_field("allowed_radius", "1.000")

    assert result.ok is True
    assert result.value == 1000


def test_store_identity_normalizes_case_and_spaces() -> None:
    assert store_identity(" VIZU ", "Mall  Besar", " Utama ", "JAKARTA") == store_identity(
        "vizu",
        "Mall Besar",
        "Utama",
        "jakarta",
    )


def test_is_duplicate_identity_matches_active_inputs_and_excludes_self() -> None:
    stores = [_store("S1", "VIZU", "Mall Besar", "Utama", "Jakarta")]

    assert is_duplicate_identity(stores, " vIzu ", "Mall Besar", "Utama", "Jakarta", None) is True
    assert is_duplicate_identity(stores, "VIZU", "Mall Besar", "Utama", "Jakarta", "S1") is False
    assert is_duplicate_identity([], "VIZU", "Mall Besar", "Utama", "Jakarta", None) is False


def test_generate_store_id_format() -> None:
    store_id = generate_store_id(datetime(2026, 6, 18, 9, 30, 5, tzinfo=UTC))

    assert store_id.startswith("STR-20260618-093005-")
    assert len(store_id) == len("STR-20260618-093005-0000")


def _store(
    store_id: str,
    brand: str,
    outlet: str,
    branch: str,
    city: str,
) -> StoreLocation:
    return StoreLocation(
        store_id=store_id,
        brand=brand,
        outlet=outlet,
        branch=branch,
        city=city,
        latitude=-6.2,
        longitude=106.8,
        allowed_radius_meter=100,
        status="Aktif",
        notes=None,
    )

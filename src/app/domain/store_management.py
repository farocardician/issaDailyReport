from __future__ import annotations

import random
import re
from collections.abc import Iterable
from datetime import datetime

from app.domain.store_matching import StoreLocation
from app.domain.user_management import FieldResult
from app.domain.validation import normalize_text_dash, parse_int_lenient

STORE_FORM_FIELDS = (
    "brand",
    "outlet",
    "branch",
    "city",
    "latitude",
    "longitude",
    "allowed_radius",
    "notes",
)
OPTIONAL_FIELDS = {"notes"}
STORE_ID_PATTERN = re.compile(r"^STR-\d{8}-\d{6}-\d{4}$")
_RANDOM = random.SystemRandom()


def validate_store_field(field: str, raw: object | None) -> FieldResult:
    value = "" if raw is None else str(raw).strip()
    if field in {"brand", "outlet", "branch", "city"}:
        if not value or value == "-":
            return FieldResult(False, None, f"STORE_ERROR_{_field_error_suffix(field)}_REQUIRED")
        return FieldResult(True, normalize_text_dash(value), None)

    if field == "latitude":
        return _validate_coordinate(value, -90, 90, "STORE_ERROR_LATITUDE_INVALID")

    if field == "longitude":
        return _validate_coordinate(value, -180, 180, "STORE_ERROR_LONGITUDE_INVALID")

    if field == "allowed_radius":
        try:
            radius = parse_int_lenient(value)
        except ValueError:
            return FieldResult(False, None, "STORE_ERROR_RADIUS_INVALID")
        if radius <= 0:
            return FieldResult(False, None, "STORE_ERROR_RADIUS_INVALID")
        return FieldResult(True, radius, None)

    if field == "notes":
        if not value or value == "-":
            return FieldResult(True, None, None)
        return FieldResult(True, normalize_text_dash(value), None)

    raise ValueError(f"Unknown store field: {field}")


def store_identity(
    brand: str,
    outlet: str,
    branch: str,
    city: str,
) -> tuple[str, str, str, str]:
    return (
        _normalize_identity_part(brand),
        _normalize_identity_part(outlet),
        _normalize_identity_part(branch),
        _normalize_identity_part(city),
    )


def is_duplicate_identity(
    active_stores: Iterable[StoreLocation],
    brand: str,
    outlet: str,
    branch: str,
    city: str,
    exclude_store_id: str | None,
) -> bool:
    candidate = store_identity(brand, outlet, branch, city)
    return any(
        store.store_id != exclude_store_id
        and store_identity(store.brand, store.outlet, store.branch, store.city) == candidate
        for store in active_stores
    )


def generate_store_id(now: datetime) -> str:
    return f"STR-{now:%Y%m%d-%H%M%S}-{_RANDOM.randint(0, 9999):04d}"


def _validate_coordinate(value: str, lower: float, upper: float, error_key: str) -> FieldResult:
    normalized = value.replace(",", ".") if "," in value and "." not in value else value
    try:
        coordinate = float(normalized)
    except ValueError:
        return FieldResult(False, None, error_key)
    if coordinate < lower or coordinate > upper:
        return FieldResult(False, None, error_key)
    return FieldResult(True, coordinate, None)


def _normalize_identity_part(value: str) -> str:
    return " ".join(value.split()).casefold()


def _field_error_suffix(field: str) -> str:
    return field.upper()

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.store_management import STORE_FORM_FIELDS
from app.domain.store_matching import StoreLocation
from app.templates import MessageTemplates

FIELD_KEY_SUFFIXES = {
    "brand": "BRAND",
    "department_store": "DEPARTMENT",
    "branch": "BRANCH",
    "city": "CITY",
    "latitude": "LATITUDE",
    "longitude": "LONGITUDE",
    "allowed_radius": "RADIUS",
    "notes": "NOTES",
}


def store_list_button_labels(
    templates: MessageTemplates,
    stores: Sequence[StoreLocation],
) -> dict[str, str]:
    return {
        store.store_id: templates.render_plain(
            "STORE_LIST_BUTTON",
            store_label=templates.render_store_label(store),
            brand=store.brand,
            department_store=store.department_store,
            branch=store.branch,
            city=store.city,
            status=store.status,
        )
        for store in stores
    }


def store_detail_tokens(templates: MessageTemplates, store: StoreLocation, notice: str = "") -> dict[str, str]:
    return {
        "notice": notice,
        "store_id": _value(store.store_id),
        "store_label": templates.render_store_label(store),
        "brand": _value(store.brand),
        "department_store": _value(store.department_store),
        "branch": _value(store.branch),
        "city": _value(store.city),
        "latitude": _value(store.latitude),
        "longitude": _value(store.longitude),
        "allowed_radius": _value(store.allowed_radius_meter),
        "notes": _value(store.notes),
        "status": _value(store.status),
    }


def store_form_review_tokens(fields: Mapping[str, Any], notice: str = "") -> dict[str, str]:
    return {
        "notice": notice,
        "brand": _value(fields.get("brand")),
        "department_store": _value(fields.get("department_store")),
        "branch": _value(fields.get("branch")),
        "city": _value(fields.get("city")),
        "latitude": _value(fields.get("latitude")),
        "longitude": _value(fields.get("longitude")),
        "allowed_radius": _value(fields.get("allowed_radius")),
        "notes": _value(fields.get("notes")),
    }


def store_field_button_labels(templates: MessageTemplates) -> list[tuple[str, str]]:
    return [
        (field, templates.render(f"BUTTON_STORE_FIELD_{FIELD_KEY_SUFFIXES[field]}"))
        for field in STORE_FORM_FIELDS
    ]


def store_field_prompt_key(field: str) -> str:
    return f"ASK_STORE_{FIELD_KEY_SUFFIXES[field]}"


def _value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)

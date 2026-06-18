from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.bot.management_scope import ManagementScope
from app.domain.user_management import USER_FORM_FIELDS
from app.templates import MessageTemplates

FIELD_KEY_SUFFIXES = {
    "name": "NAME",
    "phone": "PHONE",
    "email": "EMAIL",
    "notes": "NOTES",
}


def user_list_button_labels(
    templates: MessageTemplates,
    scope: ManagementScope,
    users: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    return {
        str(user["user_id"]): templates.render_plain(
            scope.key("LIST_BUTTON"),
            user_name=user["name"],
            status=user["status"],
        )
        for user in users
    }


def user_detail_tokens(templates: MessageTemplates, user: Mapping[str, Any], notice: str = "") -> dict[str, str]:
    return {
        "notice": notice,
        "user_id": str(user["user_id"]),
        "name": _value(user.get("name")),
        "phone": _value(user.get("phone")),
        "email": _value(user.get("email")),
        "notes": _value(user.get("notes")),
        "status": _value(user.get("status")),
        "telegram_link_status": _telegram_link_status(templates, user),
    }


def user_form_review_tokens(fields: Mapping[str, Any], notice: str = "") -> dict[str, str]:
    return {
        "notice": notice,
        "name": _value(fields.get("name")),
        "phone": _value(fields.get("phone")),
        "email": _value(fields.get("email")),
        "notes": _value(fields.get("notes")),
    }


def user_field_button_labels(templates: MessageTemplates, scope: ManagementScope) -> list[tuple[str, str]]:
    return [
        (field, templates.render(f"BUTTON_{scope.entity}_FIELD_{FIELD_KEY_SUFFIXES[field]}"))
        for field in USER_FORM_FIELDS
    ]


def user_field_prompt_key(field: str, scope: ManagementScope) -> str:
    return f"ASK_{scope.entity}_{FIELD_KEY_SUFFIXES[field]}"


def _telegram_link_status(templates: MessageTemplates, user: Mapping[str, Any]) -> str:
    key = "USER_TELEGRAM_LINKED_YES" if user.get("telegram_user_id") is not None else "USER_TELEGRAM_LINKED_NO"
    return templates.render(key)


def _value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)

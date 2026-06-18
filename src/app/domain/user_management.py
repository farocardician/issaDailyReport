from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from app.domain.activation import normalize_phone
from app.domain.validation import normalize_text_dash

USER_FORM_FIELDS = ("name", "phone", "email", "notes")
OPTIONAL_FIELDS = {"email", "notes"}
USER_ID_PATTERN = re.compile(r"^USR-\d{8}-\d{6}-\d{4}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_ALLOWED_PATTERN = re.compile(r"^[\d\s+().-]+$")
_RANDOM = random.SystemRandom()


@dataclass(frozen=True)
class FieldResult:
    ok: bool
    value: str | None
    error_key: str | None


def validate_field(field: str, raw: str | None) -> FieldResult:
    value = "" if raw is None else raw.strip()
    if field == "name":
        if not value:
            return FieldResult(False, None, "USER_ERROR_NAME_REQUIRED")
        return FieldResult(True, normalize_text_dash(value), None)

    if field == "phone":
        if not value or value == "-":
            return FieldResult(False, None, "USER_ERROR_PHONE_REQUIRED")
        if not _PHONE_ALLOWED_PATTERN.fullmatch(value):
            return FieldResult(False, None, "USER_ERROR_PHONE_INVALID")
        normalized_phone = normalize_phone(value)
        if not normalized_phone:
            return FieldResult(False, None, "USER_ERROR_PHONE_INVALID")
        return FieldResult(True, normalized_phone, None)

    if field == "email":
        if not value or value == "-":
            return FieldResult(True, None, None)
        email = normalize_text_dash(value)
        if not _EMAIL_PATTERN.fullmatch(email):
            return FieldResult(False, None, "USER_ERROR_EMAIL_INVALID")
        return FieldResult(True, email, None)

    if field == "notes":
        if not value or value == "-":
            return FieldResult(True, None, None)
        return FieldResult(True, normalize_text_dash(value), None)

    raise ValueError(f"Unknown user field: {field}")


def is_duplicate_phone(
    all_users: Iterable[dict[str, Any]],
    phone: str,
    exclude_user_id: str | None,
) -> bool:
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        return False

    return any(
        user.get("user_id") != exclude_user_id
        and normalize_phone(user.get("phone")) == normalized_phone
        for user in all_users
    )


def generate_user_id(now: datetime) -> str:
    return f"USR-{now:%Y%m%d-%H%M%S}-{_RANDOM.randint(0, 9999):04d}"

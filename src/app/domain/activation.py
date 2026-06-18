from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ActivationOutcome(StrEnum):
    ACTIVATED = "ACTIVATED"
    ALREADY_LINKED = "ALREADY_LINKED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class ActivationResult:
    outcome: ActivationOutcome
    user: dict[str, Any] | None = None


def normalize_phone(raw: str | None) -> str:
    if raw is None:
        return ""

    digits = "".join(character for character in raw if character.isdigit())
    if digits.startswith("62"):
        return f"0{digits[2:]}"
    if digits.startswith("8"):
        return f"0{digits}"
    return digits


def match_active_users_by_phone(active_users: list[dict[str, Any]], shared_phone: str) -> list[dict[str, Any]]:
    normalized_shared_phone = normalize_phone(shared_phone)
    if not normalized_shared_phone:
        return []
    return [
        user
        for user in active_users
        if normalize_phone(user.get("phone")) == normalized_shared_phone
    ]


def decide_activation(
    current_telegram_user_id: int,
    phone_matches: list[dict[str, Any]],
) -> ActivationResult:
    if len(phone_matches) != 1:
        return ActivationResult(ActivationOutcome.BLOCKED)

    user = phone_matches[0]
    linked_telegram_user_id = user.get("telegram_user_id")
    if linked_telegram_user_id is None:
        return ActivationResult(ActivationOutcome.ACTIVATED, user)
    if int(linked_telegram_user_id) == current_telegram_user_id:
        return ActivationResult(ActivationOutcome.ALREADY_LINKED, user)
    return ActivationResult(ActivationOutcome.BLOCKED)

from app.domain.activation import (
    ActivationOutcome,
    decide_activation,
    match_active_users_by_phone,
    normalize_phone,
)


def test_normalize_phone() -> None:
    assert normalize_phone("081280003276") == "081280003276"
    assert normalize_phone("6281280003276") == "081280003276"
    assert normalize_phone("+6281280003276") == "081280003276"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_match_active_users_by_phone() -> None:
    users = [
        {"user_id": "USR-1", "phone": "081280003276"},
        {"user_id": "USR-2", "phone": "+628999"},
    ]

    assert match_active_users_by_phone(users, "+6281280003276") == [users[0]]


def test_match_active_users_by_phone_ignores_blank_shared_phone() -> None:
    users = [{"user_id": "USR-1", "phone": ""}]

    assert match_active_users_by_phone(users, "") == []


def test_decide_activation_blocks_no_match() -> None:
    result = decide_activation(7, [])

    assert result.outcome == ActivationOutcome.BLOCKED
    assert result.user is None


def test_decide_activation_blocks_duplicate_match() -> None:
    result = decide_activation(7, [{"user_id": "USR-1"}, {"user_id": "USR-2"}])

    assert result.outcome == ActivationOutcome.BLOCKED
    assert result.user is None


def test_decide_activation_activates_unlinked_user() -> None:
    user = {"user_id": "USR-1", "telegram_user_id": None}

    result = decide_activation(7, [user])

    assert result.outcome == ActivationOutcome.ACTIVATED
    assert result.user == user


def test_decide_activation_accepts_same_linked_user() -> None:
    user = {"user_id": "USR-1", "telegram_user_id": 7}

    result = decide_activation(7, [user])

    assert result.outcome == ActivationOutcome.ALREADY_LINKED
    assert result.user == user


def test_decide_activation_blocks_other_linked_user() -> None:
    user = {"user_id": "USR-1", "telegram_user_id": 8}

    result = decide_activation(7, [user])

    assert result.outcome == ActivationOutcome.BLOCKED
    assert result.user is None

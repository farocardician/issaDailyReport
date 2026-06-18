from datetime import UTC, datetime

from app.domain.user_management import (
    USER_ID_PATTERN,
    generate_user_id,
    is_duplicate_phone,
    validate_field,
)


def test_validate_name() -> None:
    assert validate_field("name", "Ani").value == "Ani"

    result = validate_field("name", "")

    assert result.ok is False
    assert result.error_key == "USER_ERROR_NAME_REQUIRED"


def test_validate_phone_normalizes_and_rejects_invalid_values() -> None:
    assert validate_field("phone", "+6281280003276").value == "081280003276"
    assert validate_field("phone", "81280003276").value == "081280003276"

    required = validate_field("phone", "")
    invalid = validate_field("phone", "abc")
    too_short = validate_field("phone", "08123456")
    too_long = validate_field("phone", "0812345678901234")

    assert required.ok is False
    assert required.error_key == "USER_ERROR_PHONE_REQUIRED"
    assert invalid.ok is False
    assert invalid.error_key == "USER_ERROR_PHONE_INVALID"
    assert too_short.ok is False
    assert too_short.error_key == "USER_ERROR_PHONE_INVALID"
    assert too_long.ok is False
    assert too_long.error_key == "USER_ERROR_PHONE_INVALID"


def test_validate_email_optional_and_format_checked() -> None:
    assert validate_field("email", "").value is None
    assert validate_field("email", "-").value is None
    assert validate_field("email", "ani@example.com").value == "ani@example.com"

    result = validate_field("email", "bad-email")

    assert result.ok is False
    assert result.error_key == "USER_ERROR_EMAIL_INVALID"


def test_validate_notes_optional() -> None:
    assert validate_field("notes", "").value is None
    assert validate_field("notes", "-").value is None
    assert validate_field("notes", "Area Jakarta").value == "Area Jakarta"


def test_duplicate_phone_checks_all_roles_and_statuses_with_exclude_self() -> None:
    users = [
        {"user_id": "USR-1", "role": "USER", "phone": "081280003276", "status": "Nonaktif"},
        {"user_id": "USR-2", "role": "ADMIN", "phone": "081299900011", "status": "Aktif"},
        {"user_id": "USR-3", "role": "SUPER_ADMIN", "phone": "081277700011", "status": "Aktif"},
    ]

    assert is_duplicate_phone(users, "+6281280003276", None) is True
    assert is_duplicate_phone(users, "081299900011", None) is True
    assert is_duplicate_phone(users, "081277700011", None) is True
    assert is_duplicate_phone(users, "081280003276", "USR-1") is False
    assert is_duplicate_phone(users, "081200000000", None) is False


def test_duplicate_phone_uses_shared_canonical_normalization() -> None:
    users = [
        {"user_id": "USR-1", "role": "USER", "phone": "+6281280003276"},
        {"user_id": "USR-2", "role": "ADMIN", "phone": "6281290003276"},
        {"user_id": "USR-3", "role": "SUPER_ADMIN", "phone": "081230003276"},
        {"user_id": "USR-4", "role": "USER", "phone": "81240003276"},
    ]

    assert is_duplicate_phone(users, "081280003276", None) is True
    assert is_duplicate_phone(users, "081290003276", None) is True
    assert is_duplicate_phone(users, "+6281230003276", None) is True
    assert is_duplicate_phone(users, "6281240003276", None) is True


def test_generate_user_id_format() -> None:
    user_id = generate_user_id(datetime(2026, 6, 18, 9, 10, 11, tzinfo=UTC))

    assert USER_ID_PATTERN.fullmatch(user_id)
    assert user_id.startswith("USR-20260618-091011-")

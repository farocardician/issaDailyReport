import pytest

from app.domain.validation import normalize_text_dash, parse_int_lenient


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("500.000", 500000),
        ("500,000", 500000),
        ("500 000", 500000),
        ("0", 0),
    ],
)
def test_parse_int_lenient_accepts_indonesian_separators(raw: str, expected: int) -> None:
    assert parse_int_lenient(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "123abc", "-1"])
def test_parse_int_lenient_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_int_lenient(raw)


def test_normalize_text_dash_keeps_bare_dash_literal() -> None:
    assert normalize_text_dash(" - ") == "-"

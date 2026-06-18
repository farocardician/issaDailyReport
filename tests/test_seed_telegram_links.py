from app.scripts.seed import _int_or_none


def test_blank_telegram_seed_cells_are_none_for_link_preservation() -> None:
    assert _int_or_none("") is None
    assert _int_or_none("   ") is None


def test_nonblank_telegram_seed_cells_are_parsed_for_override() -> None:
    assert _int_or_none("466643614") == 466643614

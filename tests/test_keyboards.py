from app.bot.keyboards import share_location_keyboard


def test_share_location_keyboard_includes_skip_option_on_second_row() -> None:
    keyboard = share_location_keyboard("Bagikan Lokasi", "Lewati").to_dict()

    assert keyboard["keyboard"] == [
        [{"request_location": True, "text": "Bagikan Lokasi"}],
        [{"text": "Lewati"}],
    ]

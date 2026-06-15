from app.bot.keyboards import retry_location_keyboard, start_location_keyboard, stock_issue_detail_keyboard


def test_start_location_keyboard_includes_manual_store_button() -> None:
    keyboard = start_location_keyboard("Bagikan Lokasi", "Pilih Toko Manual").to_dict()

    assert keyboard["keyboard"] == [
        [{"request_location": True, "text": "Bagikan Lokasi"}],
        [{"text": "Pilih Toko Manual"}],
    ]
    assert all(button["text"] != "Lewati" for row in keyboard["keyboard"] for button in row)


def test_retry_location_keyboard_only_shows_share_location() -> None:
    keyboard = retry_location_keyboard("Bagikan Lokasi").to_dict()

    assert keyboard["keyboard"] == [[{"request_location": True, "text": "Bagikan Lokasi"}]]
    assert all(button["text"] != "Lewati" for row in keyboard["keyboard"] for button in row)


def test_stock_issue_detail_keyboard_uses_context_continue_not_done() -> None:
    keyboard = stock_issue_detail_keyboard("Lanjut ke Warna Habis", "Lewati SKU").to_dict()

    buttons = keyboard["inline_keyboard"][0]
    assert buttons == [
        {"callback_data": "stock_issue:detail_continue", "text": "Lanjut ke Warna Habis"},
        {"callback_data": "stock_issue:detail_skip", "text": "Lewati SKU"},
    ]
    assert all(button["text"] != "Selesai" for button in buttons)


def test_stock_issue_detail_keyboard_hides_skip_when_sku_exists() -> None:
    keyboard = stock_issue_detail_keyboard("Lanjut ke Catatan", None).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "stock_issue:detail_continue", "text": "Lanjut ke Catatan"}]
    ]

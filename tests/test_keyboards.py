from app.bot.keyboards import (
    retry_location_keyboard,
    sales_edit_menu_keyboard,
    sales_input_navigation_keyboard,
    sales_source_keyboard,
    sales_summary_keyboard,
    start_again_keyboard,
    start_location_keyboard,
    stock_issue_keyboard,
)


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


def test_start_again_keyboard() -> None:
    keyboard = start_again_keyboard("Mulai").to_dict()

    assert keyboard["keyboard"] == [[{"text": "Mulai"}]]


def test_stock_issue_keyboard_empty_selection_shows_none_only() -> None:
    keyboard = stock_issue_keyboard(
        [("size_empty", "Size Habis"), ("color_empty", "Warna Habis")],
        set(),
        "✓",
        "Tidak Ada",
        None,
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "stock_issue:toggle:size_empty", "text": "Size Habis"}],
        [{"callback_data": "stock_issue:toggle:color_empty", "text": "Warna Habis"}],
        [{"callback_data": "stock_issue:none", "text": "Tidak Ada"}],
    ]


def test_stock_issue_keyboard_selected_shows_dynamic_next_only() -> None:
    keyboard = stock_issue_keyboard(
        [("size_empty", "Size Habis"), ("color_empty", "Warna Habis")],
        {"color_empty"},
        "✓",
        "Tidak Ada",
        "Lanjut input Warna Habis",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "stock_issue:toggle:size_empty", "text": "Size Habis"}],
        [{"callback_data": "stock_issue:toggle:color_empty", "text": "✓ Warna Habis"}],
        [{"callback_data": "stock_issue:continue", "text": "Lanjut input Warna Habis"}],
    ]


def test_sales_source_keyboard_hides_done_when_empty() -> None:
    keyboard = sales_source_keyboard(
        [("outlet", "Outlet"), ("shopee", "Shopee")],
        set(),
        "✓",
        "Tidak Ada Penjualan",
        None,
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [
            {"callback_data": "sales_source:toggle:outlet", "text": "Outlet"},
            {"callback_data": "sales_source:toggle:shopee", "text": "Shopee"},
        ],
        [{"callback_data": "sales_source:no_sales", "text": "Tidak Ada Penjualan"}],
    ]


def test_sales_source_keyboard_shows_dynamic_next_when_selected() -> None:
    keyboard = sales_source_keyboard(
        [("outlet", "Outlet"), ("shopee", "Shopee"), ("tokopedia", "Tokopedia")],
        {"shopee"},
        "✓",
        "Tidak Ada Penjualan",
        "Lanjut input Shopee",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [
            {"callback_data": "sales_source:toggle:outlet", "text": "Outlet"},
            {"callback_data": "sales_source:toggle:shopee", "text": "✓ Shopee"},
        ],
        [{"callback_data": "sales_source:toggle:tokopedia", "text": "Tokopedia"}],
        [{"callback_data": "sales_source:done", "text": "Lanjut input Shopee"}],
    ]


def test_sales_input_navigation_keyboard() -> None:
    keyboard = sales_input_navigation_keyboard("Sebelumnya", "Batal").to_dict()

    assert keyboard["keyboard"] == [[{"text": "Sebelumnya"}, {"text": "Batal"}]]


def test_sales_summary_keyboard_reply_layout() -> None:
    keyboard = sales_summary_keyboard("Lanjutkan", "Ubah", "Batal").to_dict()

    assert keyboard["keyboard"] == [
        [{"text": "Lanjutkan"}, {"text": "Ubah"}],
        [{"text": "Batal"}],
    ]


def test_sales_edit_menu_keyboard() -> None:
    keyboard = sales_edit_menu_keyboard(
        [("outlet", "Outlet"), ("shopee", "Shopee")],
        "Tambah / Hapus Sumber Penjualan",
        "Kembali ke Ringkasan",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "sales_edit:source:outlet", "text": "Outlet"}],
        [{"callback_data": "sales_edit:source:shopee", "text": "Shopee"}],
        [{"callback_data": "sales_edit:sources", "text": "Tambah / Hapus Sumber Penjualan"}],
        [{"callback_data": "sales_edit:back", "text": "Kembali ke Ringkasan"}],
    ]

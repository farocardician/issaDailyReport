from app.bot.keyboards import (
    activation_contact_keyboard,
    admin_menu_keyboard,
    confirm_keyboard,
    manage_users_menu_keyboard,
    management_detail_keyboard,
    management_edit_menu_keyboard,
    management_list_keyboard,
    management_menu_keyboard,
    retry_location_keyboard,
    sales_edit_menu_keyboard,
    sales_input_navigation_keyboard,
    sales_source_keyboard,
    sales_summary_keyboard,
    start_again_keyboard,
    start_location_keyboard,
    stock_issue_keyboard,
    super_admin_menu_keyboard,
    user_detail_keyboard,
    user_edit_menu_keyboard,
    user_form_navigation_keyboard,
    user_form_review_keyboard,
    user_list_keyboard,
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


def test_activation_contact_keyboard_requests_contact() -> None:
    keyboard = activation_contact_keyboard("Bagikan Nomor HP").to_dict()

    assert keyboard["keyboard"] == [[{"request_contact": True, "text": "Bagikan Nomor HP"}]]


def test_admin_menu_keyboard() -> None:
    keyboard = admin_menu_keyboard("Input Laporan Harian", "Kelola User").to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "menu:report", "text": "Input Laporan Harian"}],
        [{"callback_data": "menu:users", "text": "Kelola User"}],
    ]


def test_super_admin_menu_keyboard() -> None:
    keyboard = super_admin_menu_keyboard(
        "Input Laporan Harian",
        "Kelola User",
        "Kelola Admin",
        "Kelola Store",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "menu:report", "text": "Input Laporan Harian"}],
        [{"callback_data": "menu:users", "text": "Kelola User"}],
        [{"callback_data": "menu:admins", "text": "Kelola Admin"}],
        [{"callback_data": "menu:stores", "text": "Kelola Store"}],
    ]


def test_manage_users_menu_keyboard() -> None:
    keyboard = manage_users_menu_keyboard("Tambah User", "Daftar User", "Kembali").to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "users:add", "text": "Tambah User"}],
        [{"callback_data": "users:list", "text": "Daftar User"}],
        [{"callback_data": "users:back:menu", "text": "Kembali"}],
    ]


def test_management_menu_keyboard_admin_prefix() -> None:
    keyboard = management_menu_keyboard("admins", "Tambah Admin", "Daftar Admin", "Kembali").to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "admins:add", "text": "Tambah Admin"}],
        [{"callback_data": "admins:list", "text": "Daftar Admin"}],
        [{"callback_data": "admins:back:menu", "text": "Kembali"}],
    ]


def test_user_list_keyboard() -> None:
    keyboard = user_list_keyboard(
        [{"user_id": "USR-1"}],
        {"USR-1": "Ani - Aktif"},
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "users:view:USR-1", "text": "Ani - Aktif"}],
        [{"callback_data": "users:back:menu", "text": "Kembali"}],
    ]


def test_management_list_keyboard_admin_prefix() -> None:
    keyboard = management_list_keyboard(
        "admins",
        [{"user_id": "ADM-1"}],
        {"ADM-1": "Adi - Aktif"},
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "admins:view:ADM-1", "text": "Adi - Aktif"}],
        [{"callback_data": "admins:back:menu", "text": "Kembali"}],
    ]


def test_user_detail_keyboard_active_user() -> None:
    keyboard = user_detail_keyboard(
        "USR-1",
        True,
        "Ubah Data",
        "Nonaktifkan",
        "Aktifkan Kembali",
        "Reset Link Telegram",
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "users:edit:USR-1", "text": "Ubah Data"}],
        [{"callback_data": "users:deactivate:USR-1", "text": "Nonaktifkan"}],
        [{"callback_data": "users:reset_link:USR-1", "text": "Reset Link Telegram"}],
        [{"callback_data": "users:back:list", "text": "Kembali"}],
    ]


def test_management_detail_keyboard_admin_prefix() -> None:
    keyboard = management_detail_keyboard(
        "admins",
        "ADM-1",
        True,
        "Ubah Data",
        "Nonaktifkan",
        "Aktifkan Kembali",
        "Reset Link Telegram",
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "admins:edit:ADM-1", "text": "Ubah Data"}],
        [{"callback_data": "admins:deactivate:ADM-1", "text": "Nonaktifkan"}],
        [{"callback_data": "admins:reset_link:ADM-1", "text": "Reset Link Telegram"}],
        [{"callback_data": "admins:back:list", "text": "Kembali"}],
    ]


def test_user_detail_keyboard_inactive_user() -> None:
    keyboard = user_detail_keyboard(
        "USR-1",
        False,
        "Ubah Data",
        "Nonaktifkan",
        "Aktifkan Kembali",
        "Reset Link Telegram",
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"][1] == [
        {"callback_data": "users:reactivate:USR-1", "text": "Aktifkan Kembali"}
    ]


def test_management_edit_menu_keyboard_admin_prefix() -> None:
    keyboard = management_edit_menu_keyboard(
        "admins",
        [("name", "Nama"), ("phone", "Nomor HP")],
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "admins:field:name", "text": "Nama"}],
        [{"callback_data": "admins:field:phone", "text": "Nomor HP"}],
        [{"callback_data": "admins:back:detail", "text": "Kembali"}],
    ]


def test_user_edit_menu_keyboard() -> None:
    keyboard = user_edit_menu_keyboard(
        [("name", "Nama"), ("phone", "Nomor HP")],
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "users:field:name", "text": "Nama"}],
        [{"callback_data": "users:field:phone", "text": "Nomor HP"}],
        [{"callback_data": "users:back:detail", "text": "Kembali"}],
    ]


def test_confirm_keyboard() -> None:
    keyboard = confirm_keyboard("Ya", "Kembali", "users:confirm_status", "users:back:detail").to_dict()

    assert keyboard["inline_keyboard"] == [
        [
            {"callback_data": "users:confirm_status", "text": "Ya"},
            {"callback_data": "users:back:detail", "text": "Kembali"},
        ]
    ]


def test_user_form_navigation_keyboard_with_skip() -> None:
    keyboard = user_form_navigation_keyboard("Sebelumnya", "Batal", "Lewati").to_dict()

    assert keyboard["keyboard"] == [[{"text": "Sebelumnya"}, {"text": "Lewati"}, {"text": "Batal"}]]


def test_user_form_review_keyboard() -> None:
    keyboard = user_form_review_keyboard("Simpan", "Ubah", "Batal").to_dict()

    assert keyboard["keyboard"] == [
        [{"text": "Simpan"}, {"text": "Ubah"}],
        [{"text": "Batal"}],
    ]


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

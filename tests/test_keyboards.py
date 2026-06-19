from app.bot.keyboards import (
    activation_contact_keyboard,
    admin_menu_keyboard,
    confirm_keyboard,
    manage_users_menu_keyboard,
    management_detail_keyboard,
    management_edit_menu_keyboard,
    management_list_keyboard,
    management_menu_keyboard,
    option_picker_keyboard,
    paginated_option_keyboard,
    pagination_nav_row,
    retry_location_keyboard,
    sales_edit_menu_keyboard,
    sales_input_navigation_keyboard,
    sales_source_keyboard,
    sales_summary_keyboard,
    start_again_keyboard,
    start_location_keyboard,
    stock_issue_keyboard,
    store_candidate_list_keyboard,
    store_detail_keyboard,
    store_list_keyboard,
    super_admin_menu_keyboard,
    user_detail_keyboard,
    user_edit_menu_keyboard,
    user_form_navigation_keyboard,
    user_form_review_keyboard,
    user_list_keyboard,
)
from app.domain.store_matching import StoreCandidate, StoreLocation


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


def test_store_management_list_keyboard() -> None:
    keyboard = store_list_keyboard(
        [_store("STR-1")],
        {"STR-1": "VIZU - Aktif"},
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "stores:view:STR-1", "text": "VIZU - Aktif"}],
        [{"callback_data": "stores:back:menu", "text": "Kembali"}],
    ]


def test_store_detail_keyboard_has_no_reset_link() -> None:
    keyboard = store_detail_keyboard(
        "STR-1",
        True,
        "Ubah Data",
        "Nonaktifkan",
        "Aktifkan Kembali",
        "Kembali",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "stores:edit:STR-1", "text": "Ubah Data"}],
        [{"callback_data": "stores:deactivate:STR-1", "text": "Nonaktifkan"}],
        [{"callback_data": "stores:back:list", "text": "Kembali"}],
    ]


def test_store_candidate_list_keyboard_keeps_report_callbacks() -> None:
    candidate = StoreCandidate(_store("STR-1"), 12.0, 100, True)
    keyboard = store_candidate_list_keyboard(
        [candidate],
        {"STR-1": "VIZU (12 m)"},
        other_store_label="Pilih toko lain",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "store:STR-1", "text": "VIZU (12 m)"}],
        [{"callback_data": "manual:stores", "text": "Pilih toko lain"}],
    ]


def test_store_candidate_list_keyboard_does_not_paginate_by_default() -> None:
    candidates = [
        StoreCandidate(_store(f"STR-{index}"), float(index), 100, True)
        for index in range(8)
    ]
    labels = {candidate.store.store_id: candidate.store.store_id for candidate in candidates}
    keyboard = store_candidate_list_keyboard(candidates, labels).to_dict()

    buttons = [button for row in keyboard["inline_keyboard"] for button in row]
    callback_data = [button["callback_data"] for button in buttons]

    assert callback_data == [f"store:STR-{index}" for index in range(8)]
    assert all(not callback.startswith("store_page:") for callback in callback_data)
    assert all(button["text"] for button in buttons)


def test_option_picker_keyboard_uses_supplied_callbacks() -> None:
    keyboard = option_picker_keyboard(
        ["VZ", "MYC"],
        {"VZ": "VZ · VIVI ZUBEDI", "MYC": "MYC · Mayyech"},
        callback_data=["brand:0", "brand:1"],
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "brand:0", "text": "VZ · VIVI ZUBEDI"}],
        [{"callback_data": "brand:1", "text": "MYC · Mayyech"}],
    ]


def test_option_picker_keyboard_supports_outlet_ids() -> None:
    keyboard = option_picker_keyboard(
        ["SOG", "CRL"],
        {"SOG": "SOG · Sogo", "CRL": "CRL · Central"},
        callback_data=["stores:setoutlet:SOG", "stores:setoutlet:CRL"],
        previous_label="Sebelumnya",
        previous_callback_data="stores:form:previous",
        cancel_label="Batal",
        cancel_callback_data="stores:form:cancel",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "stores:setoutlet:SOG", "text": "SOG · Sogo"}],
        [{"callback_data": "stores:setoutlet:CRL", "text": "CRL · Central"}],
        [
            {"callback_data": "stores:form:previous", "text": "Sebelumnya"},
            {"callback_data": "stores:form:cancel", "text": "Batal"},
        ],
    ]


def test_paginated_option_keyboard_uses_two_columns_and_nav() -> None:
    option_ids = [str(index) for index in range(12)]
    labels = {str(index): f"Option {index}" for index in range(12)}
    first_page = paginated_option_keyboard(
        option_ids,
        labels,
        lambda option_id: f"set:{option_id}",
        lambda page: f"page:{page}",
        0,
        "Prev",
        "Next",
        "{{current}}/{{total}}",
        "Sebelumnya",
        "previous",
        "Batal",
        "cancel",
    ).to_dict()
    last_page = paginated_option_keyboard(
        option_ids,
        labels,
        lambda option_id: f"set:{option_id}",
        lambda page: f"page:{page}",
        1,
        "Prev",
        "Next",
        "{{current}}/{{total}}",
        "Sebelumnya",
        "previous",
        "Batal",
        "cancel",
    ).to_dict()

    assert first_page["inline_keyboard"] == [
        [{"callback_data": "set:0", "text": "Option 0"}, {"callback_data": "set:1", "text": "Option 1"}],
        [{"callback_data": "set:2", "text": "Option 2"}, {"callback_data": "set:3", "text": "Option 3"}],
        [{"callback_data": "set:4", "text": "Option 4"}, {"callback_data": "set:5", "text": "Option 5"}],
        [{"callback_data": "set:6", "text": "Option 6"}, {"callback_data": "set:7", "text": "Option 7"}],
        [{"callback_data": "set:8", "text": "Option 8"}, {"callback_data": "set:9", "text": "Option 9"}],
        [{"callback_data": "page:noop", "text": "1/2"}, {"callback_data": "page:1", "text": "Next"}],
        [{"callback_data": "previous", "text": "Sebelumnya"}, {"callback_data": "cancel", "text": "Batal"}],
    ]
    assert last_page["inline_keyboard"] == [
        [{"callback_data": "set:10", "text": "Option 10"}, {"callback_data": "set:11", "text": "Option 11"}],
        [{"callback_data": "page:0", "text": "Prev"}, {"callback_data": "page:noop", "text": "2/2"}],
        [{"callback_data": "previous", "text": "Sebelumnya"}, {"callback_data": "cancel", "text": "Batal"}],
    ]
    assert all(
        button["text"]
        for keyboard in (first_page, last_page)
        for row in keyboard["inline_keyboard"]
        for button in row
    )


def test_pagination_nav_row_hides_prev_on_first_and_next_on_last() -> None:
    first = pagination_nav_row(
        0,
        3,
        lambda page: f"users:page:{page}",
        "‹ Sebelumnya",
        "Berikutnya ›",
        "Hal. {{current}}/{{total}}",
    )
    last = pagination_nav_row(
        2,
        3,
        lambda page: f"users:page:{page}",
        "‹ Sebelumnya",
        "Berikutnya ›",
        "Hal. {{current}}/{{total}}",
    )

    assert [button.to_dict() for button in first] == [
        {"callback_data": "users:noop", "text": "Hal. 1/3"},
        {"callback_data": "users:page:1", "text": "Berikutnya ›"},
    ]
    assert [button.to_dict() for button in last] == [
        {"callback_data": "users:page:1", "text": "‹ Sebelumnya"},
        {"callback_data": "users:noop", "text": "Hal. 3/3"},
    ]


def test_management_list_keyboard_pages_at_six() -> None:
    users = [{"user_id": f"USR-{index}"} for index in range(8)]
    labels = {str(user["user_id"]): str(user["user_id"]) for user in users}
    keyboard = management_list_keyboard(
        "users",
        users,
        labels,
        "Kembali",
        page=1,
        prev_label="‹ Sebelumnya",
        next_label="Berikutnya ›",
        indicator_label="Hal. {{current}}/{{total}}",
    ).to_dict()

    assert keyboard["inline_keyboard"] == [
        [{"callback_data": "users:view:USR-6", "text": "USR-6"}],
        [{"callback_data": "users:view:USR-7", "text": "USR-7"}],
        [
            {"callback_data": "users:page:0", "text": "‹ Sebelumnya"},
            {"callback_data": "users:noop", "text": "Hal. 2/2"},
        ],
        [{"callback_data": "users:back:menu", "text": "Kembali"}],
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


def _store(store_id: str) -> StoreLocation:
    return StoreLocation(
        store_id=store_id,
        outlet="Mall",
        branch="Utama",
        city="Jakarta",
        brand="VIZU",
        latitude=-6.2,
        longitude=106.8,
        allowed_radius_meter=100,
        status="Aktif",
        notes=None,
    )

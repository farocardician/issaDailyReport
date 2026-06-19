from collections.abc import Mapping, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.domain.pagination import paginate as paginate_items
from app.domain.store_matching import StoreCandidate, StoreLocation

PAGE_SIZE = 6
PICKER_PAGE_SIZE = 10


def start_location_keyboard(location_label: str, manual_store_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(location_label, request_location=True)],
            [manual_store_label],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def retry_location_keyboard(location_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(location_label, request_location=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def activation_contact_keyboard(share_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(share_label, request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_menu_keyboard(report_label: str, users_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(report_label, callback_data="menu:report")],
            [InlineKeyboardButton(users_label, callback_data="menu:users")],
        ]
    )


def super_admin_menu_keyboard(
    report_label: str,
    users_label: str,
    admins_label: str,
    stores_label: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(report_label, callback_data="menu:report")],
            [InlineKeyboardButton(users_label, callback_data="menu:users")],
            [InlineKeyboardButton(admins_label, callback_data="menu:admins")],
            [InlineKeyboardButton(stores_label, callback_data="menu:stores")],
        ]
    )


def management_menu_keyboard(
    prefix: str,
    add_label: str,
    list_label: str,
    back_label: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(add_label, callback_data=f"{prefix}:add")],
            [InlineKeyboardButton(list_label, callback_data=f"{prefix}:list")],
            [InlineKeyboardButton(back_label, callback_data=f"{prefix}:back:menu")],
        ]
    )


def management_list_keyboard(
    prefix: str,
    users: Sequence[Mapping[str, object]],
    labels: Mapping[str, str],
    back_label: str,
    page: int = 0,
    prev_label: str = "",
    next_label: str = "",
    indicator_label: str = "",
) -> InlineKeyboardMarkup:
    user_page = paginate_items(users, page, PAGE_SIZE)
    rows = [
        [InlineKeyboardButton(labels[str(user["user_id"])], callback_data=f"{prefix}:view:{user['user_id']}")]
        for user in user_page.items
    ]
    if user_page.total_pages > 1:
        rows.append(
            pagination_nav_row(
                user_page.page,
                user_page.total_pages,
                lambda target_page: f"{prefix}:page:{target_page}",
                prev_label,
                next_label,
                indicator_label,
            )
        )
    rows.append([InlineKeyboardButton(back_label, callback_data=f"{prefix}:back:menu")])
    return InlineKeyboardMarkup(rows)


def management_detail_keyboard(
    prefix: str,
    user_id: str,
    is_active: bool,
    edit_label: str,
    deactivate_label: str,
    reactivate_label: str,
    reset_link_label: str,
    back_label: str,
) -> InlineKeyboardMarkup:
    status_label = deactivate_label if is_active else reactivate_label
    status_action = "deactivate" if is_active else "reactivate"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(edit_label, callback_data=f"{prefix}:edit:{user_id}")],
            [InlineKeyboardButton(status_label, callback_data=f"{prefix}:{status_action}:{user_id}")],
            [InlineKeyboardButton(reset_link_label, callback_data=f"{prefix}:reset_link:{user_id}")],
            [InlineKeyboardButton(back_label, callback_data=f"{prefix}:back:list")],
        ]
    )


def management_edit_menu_keyboard(
    prefix: str,
    field_labels: Sequence[tuple[str, str]],
    back_label: str,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{prefix}:field:{field}")]
        for field, label in field_labels
    ]
    rows.append([InlineKeyboardButton(back_label, callback_data=f"{prefix}:back:detail")])
    return InlineKeyboardMarkup(rows)


def manage_users_menu_keyboard(add_label: str, list_label: str, back_label: str) -> InlineKeyboardMarkup:
    return management_menu_keyboard("users", add_label, list_label, back_label)


def user_list_keyboard(
    users: Sequence[Mapping[str, object]],
    labels: Mapping[str, str],
    back_label: str,
) -> InlineKeyboardMarkup:
    return management_list_keyboard("users", users, labels, back_label)


def user_detail_keyboard(
    user_id: str,
    is_active: bool,
    edit_label: str,
    deactivate_label: str,
    reactivate_label: str,
    reset_link_label: str,
    back_label: str,
) -> InlineKeyboardMarkup:
    return management_detail_keyboard(
        "users",
        user_id,
        is_active,
        edit_label,
        deactivate_label,
        reactivate_label,
        reset_link_label,
        back_label,
    )


def user_edit_menu_keyboard(field_labels: Sequence[tuple[str, str]], back_label: str) -> InlineKeyboardMarkup:
    return management_edit_menu_keyboard("users", field_labels, back_label)


def confirm_keyboard(
    yes_label: str,
    back_label: str,
    yes_data: str,
    back_data: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(yes_label, callback_data=yes_data),
                InlineKeyboardButton(back_label, callback_data=back_data),
            ]
        ]
    )


def user_form_navigation_keyboard(
    previous_label: str,
    cancel_label: str,
    skip_label: str | None = None,
) -> ReplyKeyboardMarkup:
    row = [previous_label]
    if skip_label is not None:
        row.append(skip_label)
    row.append(cancel_label)
    return ReplyKeyboardMarkup(
        [row],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def user_form_review_keyboard(save_label: str, edit_label: str, cancel_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [save_label, edit_label],
            [cancel_label],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def start_again_keyboard(start_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[start_label]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=start_label,
    )


def confirm_store_keyboard(yes_label: str, other_store_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(yes_label, callback_data="confirm_store:yes"),
                InlineKeyboardButton(other_store_label, callback_data="confirm_store:no"),
            ]
        ]
    )


def store_candidate_list_keyboard(
    candidates: Sequence[StoreCandidate],
    candidate_labels: Mapping[str, str],
    other_store_label: str | None = None,
    page: int = 0,
    paginate: bool = False,
    prev_label: str = "",
    next_label: str = "",
    indicator_label: str = "",
    back_to_brands_label: str | None = None,
) -> InlineKeyboardMarkup:
    candidate_page = paginate_items(candidates, page, PAGE_SIZE)
    page_candidates = candidate_page.items if paginate else list(candidates)
    rows = [
        [
            InlineKeyboardButton(
                candidate_labels[candidate.store.store_id],
                callback_data=f"store:{candidate.store.store_id}",
            )
        ]
        for candidate in page_candidates
    ]
    if paginate and candidate_page.total_pages > 1:
        rows.append(
            pagination_nav_row(
                candidate_page.page,
                candidate_page.total_pages,
                lambda target_page: f"store_page:{target_page}",
                prev_label,
                next_label,
                indicator_label,
            )
        )
    if other_store_label is not None:
        rows.append([InlineKeyboardButton(other_store_label, callback_data="manual:stores")])
    if back_to_brands_label is not None:
        rows.append([InlineKeyboardButton(back_to_brands_label, callback_data="manual:brands")])
    return InlineKeyboardMarkup(rows)


def store_list_keyboard(
    stores: Sequence[StoreLocation],
    labels: Mapping[str, str],
    back_label: str,
    page: int = 0,
    prev_label: str = "",
    next_label: str = "",
    indicator_label: str = "",
) -> InlineKeyboardMarkup:
    store_page = paginate_items(stores, page, PAGE_SIZE)
    rows = [
        [InlineKeyboardButton(labels[store.store_id], callback_data=f"stores:view:{store.store_id}")]
        for store in store_page.items
    ]
    if store_page.total_pages > 1:
        rows.append(
            pagination_nav_row(
                store_page.page,
                store_page.total_pages,
                lambda target_page: f"stores:page:{target_page}",
                prev_label,
                next_label,
                indicator_label,
            )
        )
    rows.append([InlineKeyboardButton(back_label, callback_data="stores:back:menu")])
    return InlineKeyboardMarkup(rows)


def store_detail_keyboard(
    store_id: str,
    is_active: bool,
    edit_label: str,
    deactivate_label: str,
    reactivate_label: str,
    back_label: str,
) -> InlineKeyboardMarkup:
    status_label = deactivate_label if is_active else reactivate_label
    status_action = "deactivate" if is_active else "reactivate"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(edit_label, callback_data=f"stores:edit:{store_id}")],
            [InlineKeyboardButton(status_label, callback_data=f"stores:{status_action}:{store_id}")],
            [InlineKeyboardButton(back_label, callback_data="stores:back:list")],
        ]
    )


def manual_store_list_keyboard(
    stores: Sequence[StoreLocation],
    store_labels: Mapping[str, str],
    page: int = 0,
    paginate: bool = False,
    prev_label: str = "",
    next_label: str = "",
    indicator_label: str = "",
    back_to_brands_label: str | None = None,
) -> InlineKeyboardMarkup:
    store_page = paginate_items(stores, page, PAGE_SIZE)
    page_stores = store_page.items if paginate else list(stores)
    rows = [
        [
            InlineKeyboardButton(
                store_labels[store.store_id],
                callback_data=f"store:{store.store_id}",
            )
        ]
        for store in page_stores
    ]
    if paginate and store_page.total_pages > 1:
        rows.append(
            pagination_nav_row(
                store_page.page,
                store_page.total_pages,
                lambda target_page: f"store_page:{target_page}",
                prev_label,
                next_label,
                indicator_label,
            )
        )
    if back_to_brands_label is not None:
        rows.append([InlineKeyboardButton(back_to_brands_label, callback_data="manual:brands")])
    return InlineKeyboardMarkup(rows)


def option_picker_keyboard(
    option_ids: Sequence[str],
    button_labels: Mapping[str, str],
    callback_data: Sequence[str] | None = None,
    previous_label: str | None = None,
    previous_callback_data: str | None = None,
    cancel_label: str | None = None,
    cancel_callback_data: str | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                button_labels[option_id],
                callback_data=callback_data[index] if callback_data is not None else option_id,
            )
        ]
        for index, option_id in enumerate(option_ids)
    ]
    navigation_row = []
    if previous_label is not None and previous_callback_data is not None:
        navigation_row.append(InlineKeyboardButton(previous_label, callback_data=previous_callback_data))
    if cancel_label is not None and cancel_callback_data is not None:
        navigation_row.append(InlineKeyboardButton(cancel_label, callback_data=cancel_callback_data))
    if navigation_row:
        rows.append(navigation_row)
    return InlineKeyboardMarkup(rows)


def paginated_option_keyboard(
    option_ids: Sequence[str],
    button_labels: Mapping[str, str],
    set_callback,
    page_callback,
    page: int,
    prev_label: str,
    next_label: str,
    indicator_label: str,
    previous_label: str,
    previous_cb: str,
    cancel_label: str,
    cancel_cb: str,
    columns: int = 2,
) -> InlineKeyboardMarkup:
    option_page = paginate_items(option_ids, page, PICKER_PAGE_SIZE)
    buttons = [
        InlineKeyboardButton(
            button_labels[option_id],
            callback_data=set_callback(option_id),
        )
        for option_id in option_page.items
    ]
    rows = [buttons[index : index + columns] for index in range(0, len(buttons), columns)]
    if option_page.total_pages > 1:
        rows.append(
            pagination_nav_row(
                option_page.page,
                option_page.total_pages,
                page_callback,
                prev_label,
                next_label,
                indicator_label,
            )
        )
    rows.append(
        [
            InlineKeyboardButton(previous_label, callback_data=previous_cb),
            InlineKeyboardButton(cancel_label, callback_data=cancel_cb),
        ]
    )
    return InlineKeyboardMarkup(rows)


def pagination_nav_row(
    page: int,
    total_pages: int,
    page_callback,
    prev_label: str,
    next_label: str,
    indicator_label: str,
) -> list[InlineKeyboardButton]:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(prev_label, callback_data=page_callback(page - 1)))
    row.append(
        InlineKeyboardButton(
            _page_indicator_label(indicator_label, page, total_pages),
            callback_data=_noop_callback(page_callback(page)),
        )
    )
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(next_label, callback_data=page_callback(page + 1)))
    return row


def summary_keyboard(submit_label: str, restart_label: str, cancel_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(submit_label, callback_data="summary:submit"),
                InlineKeyboardButton(restart_label, callback_data="summary:restart"),
            ],
            [InlineKeyboardButton(cancel_label, callback_data="summary:cancel")],
        ]
    )


def duplicate_keyboard(confirm_label: str, cancel_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(confirm_label, callback_data="duplicate:yes"),
                InlineKeyboardButton(cancel_label, callback_data="duplicate:cancel"),
            ]
        ]
    )


def none_reply_keyboard(label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[label]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=label,
    )


def sales_source_keyboard(
    options: Sequence[tuple[str, str]],
    selected_source_ids: set[str],
    selected_prefix: str,
    no_sales_label: str,
    done_label: str | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    source_buttons = [
        InlineKeyboardButton(
            f"{selected_prefix} {label}" if source_id in selected_source_ids else label,
            callback_data=f"sales_source:toggle:{source_id}",
        )
        for source_id, label in options
    ]

    for index in range(0, len(source_buttons), 2):
        rows.append(source_buttons[index : index + 2])

    if not selected_source_ids:
        rows.append([InlineKeyboardButton(no_sales_label, callback_data="sales_source:no_sales")])
    if done_label is not None:
        rows.append([InlineKeyboardButton(done_label, callback_data="sales_source:done")])
    return InlineKeyboardMarkup(rows)


def sales_input_navigation_keyboard(previous_label: str, cancel_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[previous_label, cancel_label]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def sales_summary_keyboard(continue_label: str, edit_label: str, cancel_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [continue_label, edit_label],
            [cancel_label],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def sales_edit_menu_keyboard(
    sources: Sequence[tuple[str, str]],
    edit_sources_label: str,
    back_label: str,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"sales_edit:source:{source_id}")]
        for source_id, label in sources
    ]
    rows.append([InlineKeyboardButton(edit_sources_label, callback_data="sales_edit:sources")])
    rows.append([InlineKeyboardButton(back_label, callback_data="sales_edit:back")])
    return InlineKeyboardMarkup(rows)


def stock_issue_keyboard(
    options: Sequence[tuple[str, str]],
    selected_issue_ids: set[str],
    selected_prefix: str,
    none_label: str,
    next_label: str | None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{selected_prefix} {label}" if option_id in selected_issue_ids else label,
                callback_data=f"stock_issue:toggle:{option_id}",
            )
        ]
        for option_id, label in options
    ]
    if not selected_issue_ids:
        rows.append([InlineKeyboardButton(none_label, callback_data="stock_issue:none")])
    if next_label is not None:
        rows.append([InlineKeyboardButton(next_label, callback_data="stock_issue:continue")])
    return InlineKeyboardMarkup(rows)


def _page_indicator_label(indicator_label: str, page: int, total_pages: int) -> str:
    return indicator_label.replace("{{current}}", str(page + 1)).replace("{{total}}", str(total_pages))


def _noop_callback(current_page_callback: str) -> str:
    if ":page:" in current_page_callback:
        return f"{current_page_callback.split(':page:', 1)[0]}:noop"
    if ":" in current_page_callback:
        return f"{current_page_callback.rsplit(':', 1)[0]}:noop"
    return "noop"

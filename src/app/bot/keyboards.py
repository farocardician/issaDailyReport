from collections.abc import Mapping, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.domain.store_matching import StoreCandidate, StoreLocation


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


def store_list_keyboard(
    candidates: Sequence[StoreCandidate],
    candidate_labels: Mapping[str, str],
    other_store_label: str | None = None,
) -> InlineKeyboardMarkup:
    rows = [
            [
                InlineKeyboardButton(
                    candidate_labels[candidate.store.store_id],
                    callback_data=f"store:{candidate.store.store_id}",
                )
            ]
            for candidate in candidates
    ]
    if other_store_label is not None:
        rows.append([InlineKeyboardButton(other_store_label, callback_data="manual:stores")])
    return InlineKeyboardMarkup(rows)


def manual_store_list_keyboard(stores: Sequence[StoreLocation], store_labels: Mapping[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    store_labels[store.store_id],
                    callback_data=f"store:{store.store_id}",
                )
            ]
            for store in stores
        ]
    )


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


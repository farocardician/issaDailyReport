from collections.abc import Mapping, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.domain.store_matching import StoreCandidate, StoreLocation


def share_location_keyboard(location_label: str, skip_label: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(location_label, request_location=True)],
            [skip_label],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
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


def stock_issue_keyboard(
    options: Sequence[tuple[str, str]],
    selected_option_ids: set[str],
    selected_prefix: str,
    none_label: str,
    other_label: str,
    done_label: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    option_buttons = [
        InlineKeyboardButton(
            f"{selected_prefix} {label}" if option_id in selected_option_ids else label,
            callback_data=f"stock_issue:toggle:{option_id}",
        )
        for option_id, label in options
    ]

    for index in range(0, len(option_buttons), 2):
        rows.append(option_buttons[index : index + 2])

    rows.append(
        [
            InlineKeyboardButton(other_label, callback_data="stock_issue:other"),
            InlineKeyboardButton(none_label, callback_data="stock_issue:none"),
        ]
    )
    rows.append([InlineKeyboardButton(done_label, callback_data="stock_issue:done")])
    return InlineKeyboardMarkup(rows)


def stock_issue_detail_keyboard(done_label: str, skip_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(done_label, callback_data="stock_issue:detail_done"),
                InlineKeyboardButton(skip_label, callback_data="stock_issue:detail_skip"),
            ]
        ]
    )

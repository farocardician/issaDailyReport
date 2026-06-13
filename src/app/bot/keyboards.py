from collections.abc import Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.domain.store_matching import StoreCandidate
from app.templates import distance_meter, store_label


def share_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Share Location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def confirm_store_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Ya", callback_data="confirm_store:yes"),
                InlineKeyboardButton("Pilih toko lain", callback_data="confirm_store:no"),
            ]
        ]
    )


def store_list_keyboard(candidates: Sequence[StoreCandidate], include_other_store: bool = False) -> InlineKeyboardMarkup:
    rows = [
            [
                InlineKeyboardButton(
                    f"{store_label(candidate.store)} ({distance_meter(candidate.distance_meter)})",
                    callback_data=f"store:{candidate.store.store_id}",
                )
            ]
            for candidate in candidates
    ]
    if include_other_store:
        rows.append([InlineKeyboardButton("Pilih toko lain", callback_data="manual:stores")])
    return InlineKeyboardMarkup(rows)


def summary_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Submit", callback_data="summary:submit"),
                InlineKeyboardButton("Restart", callback_data="summary:restart"),
            ],
            [InlineKeyboardButton("Cancel", callback_data="summary:cancel")],
        ]
    )


def duplicate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Ya, koreksi", callback_data="duplicate:yes"),
                InlineKeyboardButton("Batal", callback_data="duplicate:cancel"),
            ]
        ]
    )

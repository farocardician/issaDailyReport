from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from telegram.constants import ChatType, ParseMode

from app.bot.flow import ReportFlow
from app.domain.session_state import Step
from app.domain.stock_issues import StockIssue
from app.templates import MessageTemplates


def test_stock_issue_picker_uses_active_db_options_in_sort_order() -> None:
    flow, chat, _sessions = _flow(
        [
            _stock_issue("stock_empty", "Stok Kosong", 3),
            _stock_issue("not_arrived", "Barang Belum Datang", 4, "Nonaktif"),
            _stock_issue("size_empty", "Size Habis", 1),
            _stock_issue("color_empty", "Warna Habis", 2),
        ]
    )

    asyncio.run(flow.handle_message(_text_update(chat, "apa saja"), SimpleNamespace()))

    assert "Belum ada yang dipilih." in chat.sent_messages[-1]["text"]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["inline_keyboard"] == [
        [{"callback_data": "stock_issue:toggle:size_empty", "text": "Size Habis"}],
        [{"callback_data": "stock_issue:toggle:color_empty", "text": "Warna Habis"}],
        [{"callback_data": "stock_issue:toggle:stock_empty", "text": "Stok Kosong"}],
        [{"callback_data": "stock_issue:none", "text": "Tidak Ada"}],
    ]
    button_text = _button_texts(chat.sent_messages[-1])
    assert "Selesai" not in button_text
    assert "Lainnya" not in button_text
    assert "Barang Belum Datang" not in button_text


def test_stock_issue_toggle_updates_selection_and_dynamic_next_button() -> None:
    flow, chat, sessions = _flow(
        [
            _stock_issue("size_empty", "Size Habis", 1),
            _stock_issue("color_empty", "Warna Habis", 2),
        ]
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:size_empty"), SimpleNamespace()))

    assert sessions.session["draft_report"]["stock_issue_ids"] == ["size_empty"]
    assert sessions.session["draft_report"]["stock_issue_labels"] == {"size_empty": "Size Habis"}
    assert "Dipilih:\n✓ Size Habis" in chat.edited_messages[-1]["text"]
    assert chat.edited_messages[-1]["reply_markup"].to_dict()["inline_keyboard"] == [
        [{"callback_data": "stock_issue:toggle:size_empty", "text": "✓ Size Habis"}],
        [{"callback_data": "stock_issue:toggle:color_empty", "text": "Warna Habis"}],
        [{"callback_data": "stock_issue:continue", "text": "Lanjut input Size Habis"}],
    ]

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:color_empty"), SimpleNamespace()))

    assert sessions.session["draft_report"]["stock_issue_ids"] == ["size_empty", "color_empty"]
    assert "Dipilih:\n✓ Size Habis\n✓ Warna Habis" in chat.edited_messages[-1]["text"]
    assert "Tidak Ada" not in _button_texts(chat.edited_messages[-1])
    assert "Lanjut input Size Habis" in _button_texts(chat.edited_messages[-1])

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:size_empty"), SimpleNamespace()))

    assert sessions.session["draft_report"]["stock_issue_ids"] == ["color_empty"]
    assert sessions.session["draft_report"]["stock_issue_labels"] == {"color_empty": "Warna Habis"}
    assert "Dipilih:\n✓ Warna Habis" in chat.edited_messages[-1]["text"]
    assert "Lanjut input Warna Habis" in _button_texts(chat.edited_messages[-1])

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:color_empty"), SimpleNamespace()))

    assert sessions.session["draft_report"]["stock_issue_ids"] == []
    assert "Belum ada yang dipilih." in chat.edited_messages[-1]["text"]
    assert "Tidak Ada" in _button_texts(chat.edited_messages[-1])
    assert all("Lanjut input" not in text for text in _button_texts(chat.edited_messages[-1]))


def test_stock_issue_continue_starts_first_selected_detail_in_db_order() -> None:
    flow, chat, sessions = _flow(
        [
            _stock_issue("stock_empty", "Stok Kosong", 3),
            _stock_issue("color_empty", "Warna Habis", 2),
            _stock_issue("size_empty", "Size Habis", 1),
        ]
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:stock_empty"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:color_empty"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:continue"), SimpleNamespace()))

    draft = sessions.session["draft_report"]
    assert draft["stock_issue_ids"] == ["color_empty", "stock_empty"]
    assert draft["stock_issue_labels"] == {
        "color_empty": "Warna Habis",
        "stock_empty": "Stok Kosong",
    }
    assert draft["stock_issue_detail_option_ids"] == ["color_empty", "stock_empty"]
    assert draft["stock_issue_detail_option_id"] == "color_empty"
    assert "STOCK_ISSUE_DETAIL_PROMPT Warna Habis" in chat.sent_messages[-1]["text"]
    assert "Kendala 1/2 · Warna Habis" in chat.sent_messages[-1]["text"]
    assert "<b>SKU</b>" in chat.sent_messages[-1]["text"]
    assert "&lt;b&gt;" not in chat.sent_messages[-1]["text"]
    assert chat.sent_messages[-1]["parse_mode"] == ParseMode.HTML
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [
        [{"text": "Sebelumnya"}, {"text": "Batal"}]
    ]
    assert "inline_keyboard" not in chat.sent_messages[-1]["reply_markup"].to_dict()


def test_stock_issue_multiple_details_save_multiline_value_then_note_step() -> None:
    draft = {
        "stock_issue_ids": ["size_empty", "color_empty"],
        "stock_issue_labels": {"size_empty": "Size Habis", "color_empty": "Warna Habis"},
        "stock_issue_detail_option_ids": ["size_empty", "color_empty"],
        "stock_issue_detail_option_id": "size_empty",
        "stock_issue_sku_details": {},
    }
    flow, chat, sessions = _flow(
        [
            _stock_issue("size_empty", "Size Habis", 1),
            _stock_issue("color_empty", "Warna Habis", 2),
        ],
        draft=draft,
    )

    asyncio.run(flow.handle_message(_text_update(chat, "SKU-001, SKU-002"), SimpleNamespace()))

    assert sessions.session["draft_report"]["stock_issue_detail_option_id"] == "color_empty"
    assert "STOCK_ISSUE_DETAIL_PROMPT Warna Habis" in chat.sent_messages[-1]["text"]
    assert "Kendala 2/2 · Warna Habis" in chat.sent_messages[-1]["text"]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [
        [{"text": "Sebelumnya"}, {"text": "Batal"}]
    ]

    asyncio.run(flow.handle_message(_text_update(chat, "SKU-003"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ASK_NOTE.value
    assert sessions.session["draft_report"]["stock_issue"] == "Size Habis: SKU-001, SKU-002\nWarna Habis: SKU-003"
    assert "ASK_NOTE" in chat.sent_messages[-1]["text"]


def test_stock_issue_previous_moves_between_details_and_back_to_picker() -> None:
    draft = {
        "stock_issue_ids": ["size_empty", "color_empty"],
        "stock_issue_labels": {"size_empty": "Size Habis", "color_empty": "Warna Habis"},
        "stock_issue_detail_option_ids": ["size_empty", "color_empty"],
        "stock_issue_detail_option_id": "color_empty",
        "stock_issue_sku_details": {"size_empty": ["SKU-001"]},
    }
    flow, chat, sessions = _flow(
        [
            _stock_issue("size_empty", "Size Habis", 1),
            _stock_issue("color_empty", "Warna Habis", 2),
        ],
        draft=draft,
    )

    asyncio.run(flow.handle_message(_text_update(chat, "Sebelumnya"), SimpleNamespace()))

    assert sessions.session["draft_report"]["stock_issue_detail_option_id"] == "size_empty"
    assert "STOCK_ISSUE_DETAIL_PROMPT Size Habis" in chat.sent_messages[-1]["text"]
    assert "✓ SKU-001" in chat.sent_messages[-1]["text"]

    asyncio.run(flow.handle_message(_text_update(chat, "Sebelumnya"), SimpleNamespace()))

    picker_draft = sessions.session["draft_report"]
    assert picker_draft["stock_issue_ids"] == ["size_empty", "color_empty"]
    assert "stock_issue_detail_option_id" not in picker_draft
    assert "stock_issue_detail_option_ids" not in picker_draft
    assert "Dipilih:\n✓ Size Habis\n✓ Warna Habis" in chat.sent_messages[-1]["text"]
    assert "Lanjut input Size Habis" in _button_texts(chat.sent_messages[-1])


def test_stock_issue_selection_edit_preserves_remaining_skus_and_collects_new_issue_only() -> None:
    draft = {
        "stock_issue_ids": ["size_empty", "color_empty"],
        "stock_issue_labels": {"size_empty": "Size Habis", "color_empty": "Warna Habis"},
        "stock_issue_sku_details": {
            "size_empty": ["SKU-001"],
            "color_empty": ["SKU-002"],
        },
    }
    flow, chat, sessions = _flow(
        [
            _stock_issue("size_empty", "Size Habis", 1),
            _stock_issue("color_empty", "Warna Habis", 2),
            _stock_issue("stock_empty", "Stok Kosong", 3),
        ],
        draft=draft,
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:color_empty"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:toggle:stock_empty"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:continue"), SimpleNamespace()))

    detail_draft = sessions.session["draft_report"]
    assert detail_draft["stock_issue_ids"] == ["size_empty", "stock_empty"]
    assert detail_draft["stock_issue_sku_details"] == {"size_empty": ["SKU-001"]}
    assert detail_draft["stock_issue_detail_option_ids"] == ["size_empty", "stock_empty"]
    assert detail_draft["stock_issue_detail_option_id"] == "stock_empty"
    assert "STOCK_ISSUE_DETAIL_PROMPT Stok Kosong" in chat.sent_messages[-1]["text"]
    assert "Kendala 2/2 · Stok Kosong" in chat.sent_messages[-1]["text"]

    asyncio.run(flow.handle_message(_text_update(chat, "SKU-003"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ASK_NOTE.value
    assert sessions.session["draft_report"]["stock_issue"] == "Size Habis: SKU-001\nStok Kosong: SKU-003"


def test_stock_issue_detail_cancel_cancels_session() -> None:
    draft = {
        "stock_issue_ids": ["size_empty"],
        "stock_issue_labels": {"size_empty": "Size Habis"},
        "stock_issue_detail_option_ids": ["size_empty"],
        "stock_issue_detail_option_id": "size_empty",
        "stock_issue_sku_details": {},
    }
    flow, chat, sessions = _flow([_stock_issue("size_empty", "Size Habis", 1)], draft=draft)

    asyncio.run(flow.handle_message(_text_update(chat, "Batal"), SimpleNamespace()))

    assert sessions.session == {}
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [[{"text": "Mulai"}]]


def test_stock_issue_none_goes_to_note_with_dash() -> None:
    flow, chat, sessions = _flow([_stock_issue("size_empty", "Size Habis", 1)])

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:none"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ASK_NOTE.value
    assert sessions.session["draft_report"]["stock_issue"] == "-"
    assert "ASK_NOTE" in chat.sent_messages[-1]["text"]


def test_stock_issue_picker_stray_text_reprompts_without_free_text() -> None:
    flow, chat, sessions = _flow([_stock_issue("size_empty", "Size Habis", 1)])

    asyncio.run(flow.handle_message(_text_update(chat, "kendala manual"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ASK_STOCK_ISSUE.value
    assert "stock_issue" not in sessions.session["draft_report"]
    assert "ASK_STOCK_ISSUE" in chat.sent_messages[-1]["text"]
    assert "Belum ada yang dipilih." in chat.sent_messages[-1]["text"]


def _flow(
    issues: list[StockIssue],
    draft: dict[str, Any] | None = None,
) -> tuple[ReportFlow, "_FakeChat", "_FakeSessions"]:
    templates = _templates()
    chat = _FakeChat()
    sessions = _FakeSessions(draft or {})
    flow = ReportFlow(
        settings=SimpleNamespace(
            active_status="Aktif",
            default_radius_meter=100,
            session_ttl_minutes=30,
            timezone=UTC,
            admin_chat_id=123,
        ),
        templates=MessageTemplates(templates),
        templates_repository=_FakeTemplatesRepository(templates),
        stores=SimpleNamespace(),
        sales_sources=SimpleNamespace(),
        stock_issues=_FakeStockIssues(issues),
        users=SimpleNamespace(),
        reports=SimpleNamespace(),
        sessions=sessions,
    )
    return flow, chat, sessions


def _templates() -> dict[str, str]:
    return {
        "UNKNOWN_COMMAND": "UNKNOWN_COMMAND",
        "CANCELLED": "CANCELLED",
        "ASK_STOCK_ISSUE": "{{progress}}\nASK_STOCK_ISSUE\n{{selected_issues}}",
        "ASK_NOTE": "{{progress}}\nASK_NOTE",
        "STOCK_ISSUE_DETAIL_PROMPT": "{{progress}}\n{{detail_progress}}\nSTOCK_ISSUE_DETAIL_PROMPT {{issue}}\n{{sku_list}}\n{{instructions}}",
        "STOCK_ISSUE_DETAIL_STEP_LABEL": "Kendala",
        "STOCK_ISSUE_SELECTED_EMPTY": "Belum ada yang dipilih.",
        "STOCK_ISSUE_SELECTED_HEADER": "Dipilih:",
        "STOCK_ISSUE_SKU_EMPTY": "Belum ada SKU yang diinput.",
        "STOCK_ISSUE_SKU_HEADER": "SKU yang sudah diinput:",
        "STOCK_ISSUE_DETAIL_INPUT_INSTRUCTION": "Ketik <b>SKU</b> yang terdampak. Kalau ada beberapa SKU, pisahkan dengan koma.",
        "STOCK_ISSUE_DETAIL_SKIP_INSTRUCTION": "Tekan <b>Lewati SKU</b> kalau tidak perlu isi SKU.",
        "STOCK_ISSUE_DETAIL_EMPTY_VALUE": "-",
        "STOCK_ISSUE_DETAIL_LINE": "{{issue}}: {{sku_list}}",
        "SELECTED_PREFIX": "✓",
        "BUTTON_NONE": "Tidak Ada",
        "BUTTON_START": "Mulai",
        "BUTTON_CANCEL": "Batal",
        "BUTTON_PREVIOUS": "Sebelumnya",
        "BUTTON_SKIP_SKU": "Lewati SKU",
        "BUTTON_STOCK_ISSUE_NEXT": "Lanjut input {{issue}}",
        "BUTTON_CONTINUE_TO_NEXT_ISSUE": "Lanjut ke {{next_issue_label}}",
        "BUTTON_CONTINUE_TO_NEXT_PHASE": "Lanjut ke {{next_phase_label}}",
        "NEXT_PHASE_NOTE_LABEL": "Catatan",
        "PROGRESS_MAIN_LABEL": "Langkah",
        "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
        "CONTEXTUAL_STEP_FORMAT": "{{label}} {{current}}/{{total}} · {{title}}",
        "PROGRESS_PHASE_STOCK_ISSUE": "Kendala Stok",
        "PROGRESS_PHASE_NOTE": "Catatan",
    }


def _stock_issue(
    stock_issue_id: str,
    label: str,
    sort_order: int,
    status: str = "Aktif",
) -> StockIssue:
    return StockIssue(
        stock_issue_id=stock_issue_id,
        label=label,
        sort_order=sort_order,
        status=status,
    )


def _button_texts(message: dict[str, Any]) -> list[str]:
    return [
        button["text"]
        for row in message["reply_markup"].to_dict()["inline_keyboard"]
        for button in row
    ]


def _text_update(chat: "_FakeChat", text: str) -> "_FakeUpdate":
    return _FakeUpdate(chat=chat, message=SimpleNamespace(text=text, location=None), callback_query=None)


def _callback_update(chat: "_FakeChat", data: str) -> "_FakeUpdate":
    return _FakeUpdate(chat=chat, message=None, callback_query=_FakeCallbackQuery(chat, data))


class _FakeTemplatesRepository:
    def __init__(self, templates: dict[str, str]) -> None:
        self._templates = templates

    async def list_all(self) -> dict[str, str]:
        return self._templates


class _FakeStockIssues:
    def __init__(self, issues: list[StockIssue]) -> None:
        self._issues = issues

    async def list_active(self, active_status: str) -> list[StockIssue]:
        return sorted(
            [issue for issue in self._issues if issue.status == active_status],
            key=lambda issue: (issue.sort_order, issue.label),
        )


class _FakeSessions:
    def __init__(self, draft: dict[str, Any]) -> None:
        self.session: dict[str, Any] = {
            "current_step": Step.ASK_STOCK_ISSUE.value,
            "draft_report": draft,
            "selected_store_id": "S001",
            "user_id": "U001",
            "expires_at": datetime.now(UTC) + timedelta(minutes=30),
        }

    async def get(self, telegram_chat_id: int) -> dict[str, Any] | None:
        return self.session

    async def upsert(self, **session: Any) -> None:
        self.session = {
            "current_step": session["current_step"].value,
            "draft_report": session["draft_report"],
            "selected_store_id": session["selected_store_id"],
            "user_id": session["user_id"],
            "expires_at": session["expires_at"],
        }

    async def delete(self, telegram_chat_id: int) -> None:
        self.session = {}


class _FakeChat:
    id = 99
    type = ChatType.PRIVATE

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.edited_messages: list[dict[str, Any]] = []

    async def send_message(self, **message: Any) -> None:
        self.sent_messages.append(message)


class _FakeCallbackQuery:
    def __init__(self, chat: _FakeChat, data: str) -> None:
        self.data = data
        self.message = SimpleNamespace()
        self._chat = chat

    async def answer(self) -> None:
        pass

    async def edit_message_text(self, **message: Any) -> None:
        self._chat.edited_messages.append(message)

    async def edit_message_reply_markup(self, **message: Any) -> None:
        self._chat.edited_messages.append(message)


class _FakeUpdate:
    effective_user = SimpleNamespace(id=7)

    def __init__(self, chat: _FakeChat, message: Any, callback_query: Any) -> None:
        self.effective_chat = chat
        self.message = message
        self.callback_query = callback_query

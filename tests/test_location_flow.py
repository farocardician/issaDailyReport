from __future__ import annotations

import asyncio
import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from telegram.constants import ChatType

from app.bot.flow import ReportFlow
from app.domain.session_state import Step
from app.domain.store_matching import StoreLocation
from app.templates import MessageTemplates


def test_start_screen_uses_manual_store_button_not_skip() -> None:
    flow, chat, sessions = _flow_with_stores([])
    update = _text_update(chat, "/start")

    asyncio.run(flow.handle_start(update, SimpleNamespace()))

    assert sessions.upserts[-1]["current_step"] == Step.AWAITING_LOCATION
    assert "START Pilih Toko Manual" in chat.sent_messages[0]["text"]
    assert "Lewati" not in chat.sent_messages[0]["text"]
    assert chat.sent_messages[0]["reply_markup"].to_dict()["keyboard"] == [
        [{"request_location": True, "text": "Bagikan Lokasi"}],
        [{"text": "Pilih Toko Manual"}],
    ]


def test_retry_location_during_manual_selection_re_runs_store_matching() -> None:
    flow, chat, sessions = _flow_with_stores(
        [
            _store("S001", latitude=-6.2, longitude=106.8, allowed_radius_meter=100),
        ]
    )
    update = _location_update(chat, latitude=-6.2, longitude=106.8)

    asyncio.run(flow.handle_message(update, SimpleNamespace()))

    assert sessions.upserts[-1]["current_step"] == Step.CONFIRM_STORE
    assert any("STORE_CONFIRMATION" in message["text"] for message in chat.sent_messages)
    assert all("UNKNOWN_COMMAND" not in message["text"] for message in chat.sent_messages)


def test_retry_location_not_found_keyboard_only_shows_share_location() -> None:
    flow, chat, sessions = _flow_with_stores(
        [
            _store("S001", latitude=-6.2, longitude=106.8, allowed_radius_meter=10),
        ]
    )
    update = _location_update(chat, latitude=0, longitude=0)

    asyncio.run(flow.handle_message(update, SimpleNamespace()))

    assert sessions.upserts[-1]["current_step"] == Step.MANUAL_STORE_SELECTION
    assert len(chat.sent_messages) == 2
    assert "LOCATION_NOT_FOUND" in chat.sent_messages[0]["text"]
    assert chat.sent_messages[0]["reply_markup"].to_dict()["keyboard"] == [
        [{"request_location": True, "text": "Bagikan Lokasi"}]
    ]
    assert "MANUAL_STORE_SELECTION" in chat.sent_messages[1]["text"]
    assert all("UNKNOWN_COMMAND" not in message["text"] for message in chat.sent_messages)


def test_button_skip_remains_available_in_ui_translate() -> None:
    with Path("Reference/ui_translate.csv").open(newline="") as file:
        templates = dict(csv.reader(file))

    assert templates["BUTTON_SKIP"] == "Lewati"
    assert templates["BUTTON_SELECT_STORE_MANUAL"] == "Pilih Toko Manual"


def _flow_with_stores(stores: list[StoreLocation]) -> tuple[ReportFlow, "_FakeChat", "_FakeSessions"]:
    templates = _templates()
    sessions = _FakeSessions()
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
        stores=_FakeStores(stores),
        sales_sources=SimpleNamespace(),
        users=SimpleNamespace(),
        reports=SimpleNamespace(),
        sessions=sessions,
    )
    return flow, _FakeChat(), sessions


def _templates() -> dict[str, str]:
    return {
        "UNKNOWN_COMMAND": "UNKNOWN_COMMAND",
        "START": "{{progress}}\nSTART {{manual_store_button}}",
        "STORE_CONFIRMATION": "{{progress}}\nSTORE_CONFIRMATION {{store_label}} {{distance_meter}}",
        "LOCATION_NOT_FOUND": "{{progress}}\nLOCATION_NOT_FOUND",
        "MANUAL_STORE_SELECTION": "{{progress}}\nMANUAL_STORE_SELECTION",
        "BUTTON_SHARE_LOCATION": "Bagikan Lokasi",
        "BUTTON_START": "Mulai",
        "BUTTON_SELECT_STORE_MANUAL": "Pilih Toko Manual",
        "BUTTON_CONFIRM_YES": "Ya",
        "BUTTON_OTHER_STORE": "Pilih toko lain",
        "PROGRESS_MAIN_LABEL": "Langkah",
        "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
        "PROGRESS_PHASE_STORE": "Pilih Toko",
        "STORE_LABEL_FORMAT": "{{brand}} - {{department_store}} {{branch}}, {{city}}",
        "STORE_BUTTON_LABEL_WITH_DISTANCE": "{{store_label}} ({{distance_meter}})",
        "DISTANCE_METER_FORMAT": "{{distance}} m",
        "DISTANCE_EMPTY": "-",
    }


def _store(
    store_id: str,
    latitude: float,
    longitude: float,
    allowed_radius_meter: int,
) -> StoreLocation:
    return StoreLocation(
        store_id=store_id,
        department_store="Mall",
        branch="Utama",
        city="Jakarta",
        brand="VIZU",
        latitude=latitude,
        longitude=longitude,
        allowed_radius_meter=allowed_radius_meter,
        status="Aktif",
        notes=None,
    )


def _location_update(chat: "_FakeChat", latitude: float, longitude: float) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(
            text=None,
            location=SimpleNamespace(latitude=latitude, longitude=longitude),
        ),
    )


def _text_update(chat: "_FakeChat", text: str) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(
            text=text,
            location=None,
        ),
    )


class _FakeTemplatesRepository:
    def __init__(self, templates: dict[str, str]) -> None:
        self._templates = templates

    async def list_all(self) -> dict[str, str]:
        return self._templates


class _FakeStores:
    def __init__(self, stores: list[StoreLocation]) -> None:
        self._stores = stores

    async def list_active(self, active_status: str) -> list[StoreLocation]:
        return [store for store in self._stores if store.status == active_status]


class _FakeSessions:
    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []
        self._session: dict[str, Any] = {
            "current_step": Step.MANUAL_STORE_SELECTION.value,
            "draft_report": {},
            "selected_store_id": None,
            "user_id": None,
            "expires_at": datetime.now(UTC) + timedelta(minutes=30),
        }

    async def get(self, telegram_chat_id: int) -> dict[str, Any]:
        return self._session

    async def upsert(self, **session: Any) -> None:
        self.upserts.append(session)
        self._session = {
            "current_step": session["current_step"].value,
            "draft_report": session["draft_report"],
            "selected_store_id": session["selected_store_id"],
            "user_id": session["user_id"],
            "expires_at": session["expires_at"],
        }

    async def delete(self, telegram_chat_id: int) -> None:
        self._session = {}


class _FakeChat:
    id = 99
    type = ChatType.PRIVATE

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    async def send_message(self, **message: Any) -> None:
        self.sent_messages.append(message)


class _FakeUpdate:
    effective_user = SimpleNamespace(id=7)

    def __init__(self, chat: _FakeChat, message: Any) -> None:
        self.effective_chat = chat
        self.message = message
        self.callback_query = None

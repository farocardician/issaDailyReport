from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from telegram.constants import ChatType

from app.bot.flow import ReportFlow
from app.domain.session_state import Step
from app.templates import MessageTemplates


def test_start_linked_user_starts_report_flow() -> None:
    user = _user("USR-1", "Ani", "081280003276", telegram_user_id=7)
    flow, chat, sessions, users = _flow(_FakeUsers(linked_users=[user]))

    asyncio.run(flow.handle_start(_text_update(chat, "/start"), SimpleNamespace()))

    assert users.deleted_chat_ids == []
    assert sessions.session["current_step"] == Step.AWAITING_LOCATION.value
    assert sessions.session["user_id"] == "USR-1"
    assert sessions.session["draft_report"] == {"user_name": "Ani"}
    assert "START Pilih Toko Manual" in chat.sent_messages[-1]["text"]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [
        [{"request_location": True, "text": "Bagikan Lokasi"}],
        [{"text": "Pilih Toko Manual"}],
    ]


def test_start_unlinked_user_asks_for_contact() -> None:
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[]))

    asyncio.run(flow.handle_start(_text_update(chat, "/start"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.AWAITING_PHONE.value
    assert sessions.session["draft_report"] == {}
    assert "ACTIVATION_ASK_CONTACT Bagikan Nomor HP" in chat.sent_messages[-1]["text"]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [
        [{"request_contact": True, "text": "Bagikan Nomor HP"}]
    ]


def test_contact_share_success_binds_telegram_and_starts_report_flow() -> None:
    user = _user("USR-1", "Ani", "081280003276")
    flow, chat, sessions, users = _flow(_FakeUsers(active_users=[user]), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "+6281280003276", user_id=7), SimpleNamespace()))

    assert users.binds == [("USR-1", 7, chat.id)]
    assert sessions.session["current_step"] == Step.AWAITING_LOCATION.value
    assert sessions.session["user_id"] == "USR-1"
    assert sessions.session["draft_report"] == {"user_name": "Ani"}
    assert "ACTIVATION_SUCCESS Ani" in chat.sent_messages[-2]["text"]
    assert "START Pilih Toko Manual" in chat.sent_messages[-1]["text"]


def test_contact_share_already_linked_starts_report_flow_without_binding() -> None:
    user = _user("USR-1", "Ani", "081280003276", telegram_user_id=7)
    flow, chat, sessions, users = _flow(_FakeUsers(active_users=[user]), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "6281280003276", user_id=7), SimpleNamespace()))

    assert users.binds == []
    assert sessions.session["current_step"] == Step.AWAITING_LOCATION.value
    assert sessions.session["user_id"] == "USR-1"
    assert len(chat.sent_messages) == 1
    assert "START Pilih Toko Manual" in chat.sent_messages[-1]["text"]


def test_foreign_contact_reprompts_contact_share() -> None:
    flow, chat, sessions, users = _flow(_FakeUsers(), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "6281280003276", user_id=99), SimpleNamespace()))

    assert users.binds == []
    assert sessions.session["current_step"] == Step.AWAITING_PHONE.value
    assert "ACTIVATION_NOT_OWN_CONTACT" in chat.sent_messages[-1]["text"]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [
        [{"request_contact": True, "text": "Bagikan Nomor HP"}]
    ]


def test_missing_contact_reprompts_contact_share() -> None:
    flow, chat, sessions, users = _flow(_FakeUsers(), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_text_update(chat, "hello"), SimpleNamespace()))

    assert users.binds == []
    assert sessions.session["current_step"] == Step.AWAITING_PHONE.value
    assert "ACTIVATION_ASK_CONTACT Bagikan Nomor HP" in chat.sent_messages[-1]["text"]


def test_unknown_phone_blocks_and_stays_on_activation() -> None:
    flow, chat, sessions, users = _flow(_FakeUsers(active_users=[]), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "6281280003276", user_id=7), SimpleNamespace()))

    assert users.binds == []
    assert sessions.session["current_step"] == Step.AWAITING_PHONE.value
    assert "ACTIVATION_FAILED" in chat.sent_messages[-1]["text"]


def test_duplicate_phone_blocks_and_stays_on_activation() -> None:
    users_repo = _FakeUsers(
        active_users=[
            _user("USR-1", "Ani", "081280003276"),
            _user("USR-2", "Budi", "6281280003276"),
        ]
    )
    flow, chat, sessions, users = _flow(users_repo, step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "6281280003276", user_id=7), SimpleNamespace()))

    assert users.binds == []
    assert sessions.session["current_step"] == Step.AWAITING_PHONE.value
    assert "ACTIVATION_FAILED" in chat.sent_messages[-1]["text"]


def test_phone_linked_to_other_account_blocks_and_stays_on_activation() -> None:
    user = _user("USR-1", "Ani", "081280003276", telegram_user_id=99)
    flow, chat, sessions, users = _flow(_FakeUsers(active_users=[user]), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "6281280003276", user_id=7), SimpleNamespace()))

    assert users.binds == []
    assert sessions.session["current_step"] == Step.AWAITING_PHONE.value
    assert "ACTIVATION_FAILED" in chat.sent_messages[-1]["text"]


def _flow(
    users: "_FakeUsers",
    step: Step | None = None,
) -> tuple[ReportFlow, "_FakeChat", "_FakeSessions", "_FakeUsers"]:
    templates = _templates()
    chat = _FakeChat()
    sessions = _FakeSessions(step)
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
        brands=SimpleNamespace(),
        outlets=SimpleNamespace(),
        sales_sources=SimpleNamespace(),
        stock_issues=SimpleNamespace(),
        users=users,
        reports=SimpleNamespace(),
        sessions=sessions,
    )
    return flow, chat, sessions, users


def _templates() -> dict[str, str]:
    return {
        "UNKNOWN_COMMAND": "UNKNOWN_COMMAND",
        "START": "{{progress}}\nSTART {{manual_store_button}}",
        "ACTIVATION_ASK_CONTACT": "ACTIVATION_ASK_CONTACT {{share_contact_button}}",
        "ACTIVATION_SUCCESS": "ACTIVATION_SUCCESS {{user_name}}",
        "ACTIVATION_FAILED": "ACTIVATION_FAILED",
        "ACTIVATION_NOT_OWN_CONTACT": "ACTIVATION_NOT_OWN_CONTACT",
        "BUTTON_SHARE_LOCATION": "Bagikan Lokasi",
        "BUTTON_SHARE_CONTACT": "Bagikan Nomor HP",
        "BUTTON_START": "Mulai",
        "BUTTON_SELECT_STORE_MANUAL": "Pilih Toko Manual",
        "PROGRESS_MAIN_LABEL": "Langkah",
        "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
        "PROGRESS_PHASE_STORE": "Pilih Toko",
    }


def _user(
    user_id: str,
    name: str,
    phone: str,
    telegram_user_id: int | None = None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "role": "SPG",
        "name": name,
        "phone": phone,
        "email": None,
        "telegram_user_id": telegram_user_id,
        "telegram_chat_id": telegram_user_id,
        "status": "Aktif",
        "notes": None,
    }


def _text_update(chat: "_FakeChat", text: str) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(text=text, location=None, contact=None),
    )


def _contact_update(chat: "_FakeChat", phone_number: str, user_id: int) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(
            text=None,
            location=None,
            contact=SimpleNamespace(phone_number=phone_number, user_id=user_id),
        ),
    )


class _FakeTemplatesRepository:
    def __init__(self, templates: dict[str, str]) -> None:
        self._templates = templates

    async def list_all(self) -> dict[str, str]:
        return self._templates


class _FakeUsers:
    def __init__(
        self,
        linked_users: list[dict[str, Any]] | None = None,
        active_users: list[dict[str, Any]] | None = None,
    ) -> None:
        self._linked_users = linked_users or []
        self._active_users = active_users or []
        self.binds: list[tuple[str, int, int]] = []
        self.deleted_chat_ids: list[int] = []

    async def find_active_by_telegram_user_id(
        self,
        telegram_user_id: int,
        active_status: str,
    ) -> list[dict[str, Any]]:
        return [
            user
            for user in self._linked_users
            if user["telegram_user_id"] == telegram_user_id and user["status"] == active_status
        ]

    async def list_active(self, active_status: str) -> list[dict[str, Any]]:
        return [user for user in self._active_users if user["status"] == active_status]

    async def bind_telegram(self, user_id: str, telegram_user_id: int, telegram_chat_id: int) -> None:
        self.binds.append((user_id, telegram_user_id, telegram_chat_id))


class _FakeSessions:
    def __init__(self, step: Step | None) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.deleted_chat_ids: list[int] = []
        self.session: dict[str, Any] | None = None
        if step is not None:
            self.session = {
                "current_step": step.value,
                "draft_report": {},
                "selected_store_id": None,
                "user_id": None,
                "expires_at": datetime.now(UTC) + timedelta(minutes=30),
            }

    async def get(self, telegram_chat_id: int) -> dict[str, Any] | None:
        return self.session

    async def upsert(self, **session: Any) -> None:
        self.upserts.append(session)
        self.session = {
            "current_step": session["current_step"].value,
            "draft_report": session["draft_report"],
            "selected_store_id": session["selected_store_id"],
            "user_id": session["user_id"],
            "expires_at": session["expires_at"],
        }

    async def delete(self, telegram_chat_id: int) -> None:
        self.deleted_chat_ids.append(telegram_chat_id)
        self.session = None


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

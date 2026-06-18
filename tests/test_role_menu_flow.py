from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from telegram.constants import ChatType

from app.bot.flow import ReportFlow
from app.domain.session_state import Step
from app.templates import MessageTemplates


def test_spg_linked_user_start_enters_report_flow() -> None:
    user = _user("USR-1", "Ani", "081280003276", role="SPG", telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]))

    asyncio.run(flow.handle_start(_text_update(chat, "/start"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.AWAITING_LOCATION.value
    assert sessions.session["user_id"] == "USR-1"
    assert sessions.session["draft_report"] == {"user_name": "Ani"}
    assert "START Pilih Toko Manual" in chat.sent_messages[-1]["text"]


def test_admin_linked_user_start_opens_admin_menu() -> None:
    user = _user("USR-1", "Ani", "081280003276", role="ADMIN", telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]))

    asyncio.run(flow.handle_start(_text_update(chat, "/start"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ADMIN_MENU.value
    assert sessions.session["user_id"] == "USR-1"
    assert sessions.session["draft_report"] == {"user_name": "Ani"}
    assert chat.sent_messages[-1]["text"] == "MENU_ADMIN"
    assert _callback_data(chat.sent_messages[-1]) == ["menu:report", "menu:users"]


def test_super_admin_linked_user_start_opens_super_admin_menu() -> None:
    user = _user("USR-1", "Ani", "081280003276", role="SUPER_ADMIN", telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]))

    asyncio.run(flow.handle_start(_text_update(chat, "/start"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.SUPER_ADMIN_MENU.value
    assert sessions.session["user_id"] == "USR-1"
    assert chat.sent_messages[-1]["text"] == "MENU_SUPER_ADMIN"
    assert _callback_data(chat.sent_messages[-1]) == [
        "menu:report",
        "menu:users",
        "menu:admins",
        "menu:stores",
    ]


@pytest.mark.parametrize("role", ["", None, "random"])
def test_blank_or_unknown_role_start_falls_back_to_report_flow(role: str | None) -> None:
    user = _user("USR-1", "Ani", "081280003276", role=role, telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]))

    asyncio.run(flow.handle_start(_text_update(chat, "/start"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.AWAITING_LOCATION.value
    assert "START Pilih Toko Manual" in chat.sent_messages[-1]["text"]


def test_contact_share_activated_admin_routes_to_admin_menu() -> None:
    user = _user("USR-1", "Ani", "081280003276", role="ADMIN")
    flow, chat, sessions, users = _flow(_FakeUsers(active_users=[user]), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "+6281280003276", user_id=7), SimpleNamespace()))

    assert users.binds == [("USR-1", 7, chat.id)]
    assert sessions.session["current_step"] == Step.ADMIN_MENU.value
    assert chat.sent_messages[-2]["text"] == "ACTIVATION_SUCCESS Ani"
    assert chat.sent_messages[-1]["text"] == "MENU_ADMIN"


def test_contact_share_already_linked_super_admin_routes_to_super_admin_menu() -> None:
    user = _user("USR-1", "Ani", "081280003276", role="SUPER_ADMIN", telegram_user_id=7)
    flow, chat, sessions, users = _flow(_FakeUsers(active_users=[user]), step=Step.AWAITING_PHONE)

    asyncio.run(flow.handle_message(_contact_update(chat, "6281280003276", user_id=7), SimpleNamespace()))

    assert users.binds == []
    assert sessions.session["current_step"] == Step.SUPER_ADMIN_MENU.value
    assert chat.sent_messages[-1]["text"] == "MENU_SUPER_ADMIN"


@pytest.mark.parametrize(
    ("step", "role"),
    [(Step.ADMIN_MENU, "ADMIN"), (Step.SUPER_ADMIN_MENU, "SUPER_ADMIN")],
)
def test_menu_report_callback_enters_report_flow(step: Step, role: str) -> None:
    user = _user("USR-1", "Ani", "081280003276", role=role, telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]), step=step)
    update = _callback_update(chat, "menu:report")

    asyncio.run(flow.handle_callback(update, SimpleNamespace()))

    assert update.callback_query.answered is True
    assert sessions.session["current_step"] == Step.AWAITING_LOCATION.value
    assert sessions.session["user_id"] == "USR-1"
    assert "START Pilih Toko Manual" in chat.sent_messages[-1]["text"]


@pytest.mark.parametrize(
    ("step", "role", "data"),
    [
        (Step.ADMIN_MENU, "ADMIN", "menu:users"),
        (Step.SUPER_ADMIN_MENU, "SUPER_ADMIN", "menu:users"),
        (Step.SUPER_ADMIN_MENU, "SUPER_ADMIN", "menu:admins"),
        (Step.SUPER_ADMIN_MENU, "SUPER_ADMIN", "menu:stores"),
    ],
)
def test_management_menu_callbacks_send_placeholder(step: Step, role: str, data: str) -> None:
    user = _user("USR-1", "Ani", "081280003276", role=role, telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]), step=step)

    asyncio.run(flow.handle_callback(_callback_update(chat, data), SimpleNamespace()))

    assert sessions.session["current_step"] == step.value
    assert chat.sent_messages[-1]["text"] == "MENU_PLACEHOLDER"


def test_inactive_linked_user_start_asks_for_contact() -> None:
    user = _user("USR-1", "Ani", "081280003276", role="SUPER_ADMIN", telegram_user_id=7, status="Nonaktif")
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]))

    asyncio.run(flow.handle_start(_text_update(chat, "/start"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.AWAITING_PHONE.value
    assert chat.sent_messages[-1]["text"] == "ACTIVATION_ASK_CONTACT Bagikan Nomor HP"


def test_super_admin_menu_admin_actor_cannot_manage_admins() -> None:
    user = _user("USR-1", "Ani", "081280003276", role="ADMIN", telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[user]), step=Step.SUPER_ADMIN_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "menu:admins"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.SUPER_ADMIN_MENU.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


def test_menu_callback_deactivated_mid_session_is_denied() -> None:
    flow, chat, sessions, _users = _flow(_FakeUsers(linked_users=[]), step=Step.ADMIN_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "menu:users"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ADMIN_MENU.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


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
        "MENU_ADMIN": "MENU_ADMIN",
        "MENU_SUPER_ADMIN": "MENU_SUPER_ADMIN",
        "MENU_PLACEHOLDER": "MENU_PLACEHOLDER",
        "MENU_ACCESS_DENIED": "MENU_ACCESS_DENIED",
        "BUTTON_SHARE_LOCATION": "Bagikan Lokasi",
        "BUTTON_SHARE_CONTACT": "Bagikan Nomor HP",
        "BUTTON_START": "Mulai",
        "BUTTON_SELECT_STORE_MANUAL": "Pilih Toko Manual",
        "BUTTON_MENU_INPUT_REPORT": "Input Laporan Harian",
        "BUTTON_MENU_MANAGE_USERS": "Kelola User",
        "BUTTON_MENU_MANAGE_ADMINS": "Kelola Admin",
        "BUTTON_MENU_MANAGE_STORES": "Kelola Store",
        "PROGRESS_MAIN_LABEL": "Langkah",
        "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
        "PROGRESS_PHASE_STORE": "Pilih Toko",
    }


def _user(
    user_id: str,
    name: str,
    phone: str,
    role: str | None = "SPG",
    telegram_user_id: int | None = None,
    status: str = "Aktif",
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "role": role,
        "name": name,
        "phone": phone,
        "email": None,
        "telegram_user_id": telegram_user_id,
        "telegram_chat_id": telegram_user_id,
        "status": status,
        "notes": None,
    }


def _text_update(chat: "_FakeChat", text: str) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(text=text, location=None, contact=None),
        callback_query=None,
    )


def _contact_update(chat: "_FakeChat", phone_number: str, user_id: int) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(
            text=None,
            location=None,
            contact=SimpleNamespace(phone_number=phone_number, user_id=user_id),
        ),
        callback_query=None,
    )


def _callback_update(chat: "_FakeChat", data: str) -> "_FakeUpdate":
    return _FakeUpdate(chat=chat, message=None, callback_query=_FakeCallbackQuery(data))


def _callback_data(message: dict[str, Any]) -> list[str]:
    keyboard = message["reply_markup"].to_dict()["inline_keyboard"]
    return [button["callback_data"] for row in keyboard for button in row]


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
                "draft_report": {"user_name": "Ani"},
                "selected_store_id": None,
                "user_id": "USR-1",
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


class _FakeCallbackQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = SimpleNamespace()
        self.answered = False

    async def answer(self) -> None:
        self.answered = True


class _FakeUpdate:
    effective_user = SimpleNamespace(id=7)

    def __init__(self, chat: _FakeChat, message: Any, callback_query: Any) -> None:
        self.effective_chat = chat
        self.message = message
        self.callback_query = callback_query

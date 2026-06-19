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


def test_menu_admins_opens_manage_admins_menu() -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers([actor]), Step.SUPER_ADMIN_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "menu:admins"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.MANAGE_ADMINS_MENU.value
    assert _last_message(chat)["text"] == "MANAGE_ADMINS_MENU"
    assert _callback_data(_last_message(chat)) == ["admins:add", "admins:list", "admins:back:menu"]


def test_add_admin_happy_path_creates_admin_only_after_save() -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    users = _FakeUsers([actor])
    flow, chat, sessions, users = _flow(users, Step.MANAGE_ADMINS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:add"), SimpleNamespace()))
    assert users.created == []

    for text in ["Adi Admin", "+6281280003276", "adi@example.com", "Lewati"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_FORM_REVIEW.value
    assert users.created == []

    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    created = users.created[0]
    assert created["role"] == "ADMIN"
    assert created["status"] == "Aktif"
    assert created["telegram_user_id"] is None
    assert created["telegram_chat_id"] is None
    assert created["name"] == "Adi Admin"
    assert created["phone"] == "081280003276"
    assert sessions.session["current_step"] == Step.MANAGE_ADMINS_MENU.value
    assert "ADMIN_ADDED" in _last_message(chat)["text"]


def test_list_and_detail_render_admin_data() -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    target = _user("ADM-1", "Adi", "081280003276", role="ADMIN", email="adi@example.com", notes="Jakarta")
    flow, chat, sessions, _users = _flow(_FakeUsers([actor, target]), Step.MANAGE_ADMINS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:list"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_LIST.value
    assert _callback_data(_last_message(chat)) == ["admins:view:ADM-1", "admins:back:menu"]

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:view:ADM-1"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_DETAIL.value
    assert "Adi" in _last_message(chat)["text"]
    assert "adi@example.com" in _last_message(chat)["text"]
    assert _callback_data(_last_message(chat)) == [
        "admins:edit:ADM-1",
        "admins:deactivate:ADM-1",
        "admins:reset_link:ADM-1",
        "admins:back:list",
    ]


def test_edit_admin_updates_basic_fields_only() -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    target = _user("ADM-1", "Adi", "081280003276", role="ADMIN", telegram_user_id=9, status="Aktif")
    flow, chat, sessions, users = _flow(
        _FakeUsers([actor, target]),
        Step.USER_DETAIL,
        {"user_name": "Super", "mgmt_scope": "admins", "user_target_id": "ADM-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:edit:ADM-1"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:field:phone"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "+6281299990000"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    updated = users.users["ADM-1"]
    assert updated["phone"] == "081299990000"
    assert updated["role"] == "ADMIN"
    assert updated["status"] == "Aktif"
    assert updated["telegram_user_id"] == 9
    assert users.updated_basic == ["ADM-1"]
    assert sessions.session["current_step"] == Step.USER_DETAIL.value
    assert "ADMIN_UPDATED" in _last_message(chat)["text"]


def test_deactivate_and_reactivate_admin_require_confirmation_and_only_change_status() -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    target = _user("ADM-1", "Adi", "081280003276", role="ADMIN", telegram_user_id=9, status="Aktif")
    flow, chat, sessions, users = _flow(
        _FakeUsers([actor, target]),
        Step.USER_DETAIL,
        {"user_name": "Super", "mgmt_scope": "admins", "user_target_id": "ADM-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:deactivate:ADM-1"), SimpleNamespace()))
    assert users.users["ADM-1"]["status"] == "Aktif"
    assert sessions.session["current_step"] == Step.USER_CONFIRM_STATUS.value

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:confirm_status"), SimpleNamespace()))
    assert users.users["ADM-1"]["status"] == "Nonaktif"
    assert users.users["ADM-1"]["telegram_user_id"] == 9

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:reactivate:ADM-1"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:confirm_status"), SimpleNamespace()))
    assert users.users["ADM-1"]["status"] == "Aktif"
    assert users.status_changes == [("ADM-1", "Nonaktif"), ("ADM-1", "Aktif")]


def test_reset_admin_link_requires_confirmation_and_clears_only_telegram_fields() -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    target = _user("ADM-1", "Adi", "081280003276", role="ADMIN", telegram_user_id=9, status="Aktif")
    flow, chat, sessions, users = _flow(
        _FakeUsers([actor, target]),
        Step.USER_DETAIL,
        {"user_name": "Super", "mgmt_scope": "admins", "user_target_id": "ADM-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:reset_link:ADM-1"), SimpleNamespace()))
    assert users.users["ADM-1"]["telegram_user_id"] == 9
    assert sessions.session["current_step"] == Step.USER_CONFIRM_RESET_LINK.value

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:confirm_reset"), SimpleNamespace()))
    assert users.users["ADM-1"]["telegram_user_id"] is None
    assert users.users["ADM-1"]["telegram_chat_id"] is None
    assert users.users["ADM-1"]["role"] == "ADMIN"
    assert users.users["ADM-1"]["status"] == "Aktif"
    assert users.reset_links == ["ADM-1"]


@pytest.mark.parametrize("conflict_role", ["USER", "SUPER_ADMIN"])
def test_add_admin_duplicate_phone_rejects_all_roles(conflict_role: str) -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    conflict_id = "USR-1" if conflict_role == "USER" else "SA-2"
    conflict = _user(conflict_id, "Conflict", "081280003276", role=conflict_role)
    flow, chat, sessions, users = _flow(_FakeUsers([actor, conflict]), Step.MANAGE_ADMINS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:add"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Adi"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "+6281280003276"), SimpleNamespace()))

    assert users.created == []
    assert sessions.session["current_step"] == Step.USER_FORM_INPUT.value
    assert "USER_ERROR_PHONE_DUPLICATE" in chat.sent_messages[-1]["text"]


@pytest.mark.parametrize("target_role", ["USER", "SUPER_ADMIN"])
def test_admin_target_role_guard_blocks_non_admin_records(target_role: str) -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    target_id = "USR-1" if target_role == "USER" else "SA-2"
    target = _user(target_id, "Target", "081280003276", role=target_role)
    flow, chat, sessions, _users = _flow(_FakeUsers([actor, target]), Step.USER_LIST)

    asyncio.run(flow.handle_callback(_callback_update(chat, f"admins:view:{target['user_id']}"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_LIST.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


def test_self_deactivation_is_blocked() -> None:
    actor = _user("ADM-SELF", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    flow, chat, sessions, users = _flow(_FakeUsers([actor]), Step.USER_DETAIL)

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:deactivate:ADM-SELF"), SimpleNamespace()))

    assert users.status_changes == []
    assert sessions.session["current_step"] == Step.USER_DETAIL.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


@pytest.mark.parametrize("role", ["ADMIN", "USER"])
def test_non_super_admin_actor_hitting_menu_admins_is_denied(role: str) -> None:
    actor = _user("ACTOR", "Actor", "081200000001", role=role, telegram_user_id=7)
    step = Step.ADMIN_MENU if role == "ADMIN" else Step.SUPER_ADMIN_MENU
    flow, chat, sessions, _users = _flow(_FakeUsers([actor]), step)

    asyncio.run(flow.handle_callback(_callback_update(chat, "menu:admins"), SimpleNamespace()))

    assert sessions.session["current_step"] == step.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


@pytest.mark.parametrize("role", ["ADMIN", "USER"])
def test_non_super_admin_actor_hitting_admins_callback_is_denied(role: str) -> None:
    actor = _user("ACTOR", "Actor", "081200000001", role=role, telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers([actor]), Step.MANAGE_ADMINS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:list"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.MANAGE_ADMINS_MENU.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


def test_newly_created_admin_can_activate_and_land_on_admin_menu() -> None:
    actor = _user("SA-1", "Super", "081200000001", role="SUPER_ADMIN", telegram_user_id=7)
    users = _FakeUsers([actor])
    flow, chat, _sessions, users = _flow(users, Step.MANAGE_ADMINS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "admins:add"), SimpleNamespace()))
    for text in ["Adi Admin", "81280003276", "Lewati", "Lewati", "Simpan"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    created = users.created[0]
    assert created["phone"] == "081280003276"
    admin_chat = _FakeChat(chat_id=100)
    admin_sessions = _FakeSessions(Step.AWAITING_PHONE)
    admin_flow = _report_flow(users, admin_chat, admin_sessions)

    asyncio.run(
        admin_flow.handle_message(
            _contact_update(admin_chat, "+6281280003276", telegram_user_id=8),
            SimpleNamespace(),
        )
    )

    assert users.users[created["user_id"]]["telegram_user_id"] == 8
    assert admin_sessions.session["current_step"] == Step.ADMIN_MENU.value
    assert admin_sessions.session["user_id"] == created["user_id"]
    assert admin_chat.sent_messages[-1]["text"] == "MENU_ADMIN"


def _flow(
    users: "_FakeUsers",
    step: Step,
    draft: dict[str, Any] | None = None,
) -> tuple[ReportFlow, "_FakeChat", "_FakeSessions", "_FakeUsers"]:
    chat = _FakeChat()
    sessions = _FakeSessions(step, draft)
    return _report_flow(users, chat, sessions), chat, sessions, users


def _report_flow(users: "_FakeUsers", chat: "_FakeChat", sessions: "_FakeSessions") -> ReportFlow:
    templates = _templates()
    return ReportFlow(
        settings=SimpleNamespace(
            active_status="Aktif",
            inactive_status="Nonaktif",
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
        "MANAGE_ADMINS_MENU": "{{notice}}MANAGE_ADMINS_MENU",
        "ADMIN_LIST": "{{notice}}ADMIN_LIST",
        "ADMIN_LIST_EMPTY": "{{notice}}ADMIN_LIST_EMPTY",
        "ADMIN_LIST_BUTTON": "{{user_name}} - {{status}}",
        "ADMIN_DETAIL": "{{notice}}ADMIN_DETAIL {{name}} {{phone}} {{email}} {{notes}} {{status}} {{telegram_link_status}}",
        "ADMIN_FORM_REVIEW": "{{notice}}ADMIN_FORM_REVIEW {{name}} {{phone}} {{email}} {{notes}}",
        "ADMIN_EDIT_MENU": "ADMIN_EDIT_MENU",
        "ADMIN_CONFIRM_DEACTIVATE": "ADMIN_CONFIRM_DEACTIVATE {{user_name}}",
        "ADMIN_CONFIRM_REACTIVATE": "ADMIN_CONFIRM_REACTIVATE {{user_name}}",
        "ADMIN_CONFIRM_RESET_LINK": "ADMIN_CONFIRM_RESET_LINK {{user_name}}",
        "ADMIN_ADDED": "ADMIN_ADDED\n",
        "ADMIN_UPDATED": "ADMIN_UPDATED\n",
        "ADMIN_DEACTIVATED": "ADMIN_DEACTIVATED\n",
        "ADMIN_REACTIVATED": "ADMIN_REACTIVATED\n",
        "ADMIN_LINK_RESET": "ADMIN_LINK_RESET\n",
        "ASK_ADMIN_NAME": "{{error}}ASK_ADMIN_NAME",
        "ASK_ADMIN_PHONE": "{{error}}ASK_ADMIN_PHONE",
        "ASK_ADMIN_EMAIL": "{{error}}ASK_ADMIN_EMAIL",
        "ASK_ADMIN_NOTES": "{{error}}ASK_ADMIN_NOTES",
        "USER_ERROR_NAME_REQUIRED": "USER_ERROR_NAME_REQUIRED\n",
        "USER_ERROR_PHONE_REQUIRED": "USER_ERROR_PHONE_REQUIRED\n",
        "USER_ERROR_PHONE_INVALID": "USER_ERROR_PHONE_INVALID\n",
        "USER_ERROR_PHONE_DUPLICATE": "USER_ERROR_PHONE_DUPLICATE\n",
        "USER_ERROR_EMAIL_INVALID": "USER_ERROR_EMAIL_INVALID\n",
        "USER_TELEGRAM_LINKED_YES": "Terhubung",
        "USER_TELEGRAM_LINKED_NO": "Belum terhubung",
        "BUTTON_SHARE_LOCATION": "Bagikan Lokasi",
        "BUTTON_SHARE_CONTACT": "Bagikan Nomor HP",
        "BUTTON_START": "Mulai",
        "BUTTON_SELECT_STORE_MANUAL": "Pilih Toko Manual",
        "BUTTON_MENU_INPUT_REPORT": "Input Laporan Harian",
        "BUTTON_MENU_MANAGE_USERS": "Kelola User",
        "BUTTON_MENU_MANAGE_ADMINS": "Kelola Admin",
        "BUTTON_MENU_MANAGE_STORES": "Kelola Store",
        "BUTTON_ADMIN_ADD": "Tambah Admin",
        "BUTTON_ADMIN_LIST": "Daftar Admin",
        "BUTTON_BACK": "Kembali",
        "BUTTON_ADMIN_EDIT": "Ubah Data",
        "BUTTON_ADMIN_DEACTIVATE": "Nonaktifkan",
        "BUTTON_ADMIN_REACTIVATE": "Aktifkan Kembali",
        "BUTTON_ADMIN_RESET_LINK": "Reset Link Telegram",
        "BUTTON_ADMIN_FIELD_NAME": "Nama",
        "BUTTON_ADMIN_FIELD_PHONE": "Nomor HP",
        "BUTTON_ADMIN_FIELD_EMAIL": "Email",
        "BUTTON_ADMIN_FIELD_NOTES": "Catatan",
        "BUTTON_SAVE": "Simpan",
        "BUTTON_EDIT": "Ubah",
        "BUTTON_CONFIRM_YES": "Ya",
        "BUTTON_CANCEL": "Batal",
        "BUTTON_PREVIOUS": "Sebelumnya",
        "BUTTON_SKIP": "Lewati",
        "PROGRESS_MAIN_LABEL": "Langkah",
        "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
        "PROGRESS_PHASE_STORE": "Pilih Toko",
    }


def _user(
    user_id: str,
    name: str,
    phone: str,
    role: str = "ADMIN",
    telegram_user_id: int | None = None,
    status: str = "Aktif",
    email: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "role": role,
        "name": name,
        "phone": phone,
        "email": email,
        "telegram_user_id": telegram_user_id,
        "telegram_chat_id": telegram_user_id,
        "status": status,
        "notes": notes,
    }


def _text_update(chat: "_FakeChat", text: str, telegram_user_id: int = 7) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(text=text, location=None, contact=None),
        callback_query=None,
        telegram_user_id=telegram_user_id,
    )


def _contact_update(chat: "_FakeChat", phone_number: str, telegram_user_id: int) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(
            text=None,
            location=None,
            contact=SimpleNamespace(phone_number=phone_number, user_id=telegram_user_id),
        ),
        callback_query=None,
        telegram_user_id=telegram_user_id,
    )


def _callback_update(chat: "_FakeChat", data: str, telegram_user_id: int = 7) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=None,
        callback_query=_FakeCallbackQuery(chat, data),
        telegram_user_id=telegram_user_id,
    )


def _last_message(chat: "_FakeChat") -> dict[str, Any]:
    return chat.messages[-1]


def _callback_data(message: dict[str, Any]) -> list[str]:
    keyboard = message["reply_markup"].to_dict()["inline_keyboard"]
    return [button["callback_data"] for row in keyboard for button in row]


class _FakeTemplatesRepository:
    def __init__(self, templates: dict[str, str]) -> None:
        self._templates = templates

    async def list_all(self) -> dict[str, str]:
        return self._templates


class _FakeUsers:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self.users = {user["user_id"]: dict(user) for user in users}
        self.created: list[dict[str, Any]] = []
        self.updated_basic: list[str] = []
        self.status_changes: list[tuple[str, str]] = []
        self.reset_links: list[str] = []
        self.binds: list[tuple[str, int, int]] = []

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        user = self.users.get(user_id)
        return dict(user) if user is not None else None

    async def list_by_role(self, role: str) -> list[dict[str, Any]]:
        return sorted(
            [dict(user) for user in self.users.values() if user["role"] == role],
            key=lambda user: user["name"],
        )

    async def list_all(self) -> list[dict[str, Any]]:
        return [dict(user) for user in self.users.values()]

    async def find_active_by_telegram_user_id(
        self,
        telegram_user_id: int,
        active_status: str,
    ) -> list[dict[str, Any]]:
        return [
            dict(user)
            for user in self.users.values()
            if user["telegram_user_id"] == telegram_user_id and user["status"] == active_status
        ]

    async def list_active(self, active_status: str) -> list[dict[str, Any]]:
        return [dict(user) for user in self.users.values() if user["status"] == active_status]

    async def bind_telegram(self, user_id: str, telegram_user_id: int, telegram_chat_id: int) -> None:
        self.binds.append((user_id, telegram_user_id, telegram_chat_id))
        self.users[user_id]["telegram_user_id"] = telegram_user_id
        self.users[user_id]["telegram_chat_id"] = telegram_chat_id

    async def create_user(
        self,
        user_id: str,
        role: str,
        name: str,
        phone: str,
        email: str | None,
        notes: str | None,
        status: str,
    ) -> None:
        user = {
            "user_id": user_id,
            "role": role,
            "name": name,
            "phone": phone,
            "email": email,
            "telegram_user_id": None,
            "telegram_chat_id": None,
            "status": status,
            "notes": notes,
        }
        self.users[user_id] = user
        self.created.append(user)

    async def update_basic(
        self,
        user_id: str,
        name: str,
        phone: str,
        email: str | None,
        notes: str | None,
    ) -> None:
        self.updated_basic.append(user_id)
        self.users[user_id].update(name=name, phone=phone, email=email, notes=notes)

    async def set_status(self, user_id: str, status: str) -> None:
        self.status_changes.append((user_id, status))
        self.users[user_id]["status"] = status

    async def reset_telegram_link(self, user_id: str) -> None:
        self.reset_links.append(user_id)
        self.users[user_id]["telegram_user_id"] = None
        self.users[user_id]["telegram_chat_id"] = None


class _FakeSessions:
    def __init__(self, step: Step, draft: dict[str, Any] | None = None) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.deleted_chat_ids: list[int] = []
        self.session: dict[str, Any] | None = {
            "current_step": step.value,
            "draft_report": draft or {"user_name": "Super", "mgmt_scope": "admins"},
            "selected_store_id": None,
            "user_id": "SA-1",
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
    type = ChatType.PRIVATE

    def __init__(self, chat_id: int = 99) -> None:
        self.id = chat_id
        self.messages: list[dict[str, Any]] = []
        self.sent_messages: list[dict[str, Any]] = []
        self.edited_messages: list[dict[str, Any]] = []

    async def send_message(self, **message: Any) -> None:
        self.messages.append(message)
        self.sent_messages.append(message)


class _FakeCallbackQuery:
    def __init__(self, chat: _FakeChat, data: str) -> None:
        self.data = data
        self.message = SimpleNamespace()
        self._chat = chat
        self.answered = False

    async def answer(self) -> None:
        self.answered = True

    async def edit_message_text(self, **message: Any) -> None:
        self._chat.messages.append(message)
        self._chat.edited_messages.append(message)

    async def edit_message_reply_markup(self, **message: Any) -> None:
        self._chat.messages.append(message)
        self._chat.edited_messages.append(message)


class _FakeUpdate:
    def __init__(self, chat: _FakeChat, message: Any, callback_query: Any, telegram_user_id: int) -> None:
        self.effective_chat = chat
        self.effective_user = SimpleNamespace(id=telegram_user_id)
        self.message = message
        self.callback_query = callback_query

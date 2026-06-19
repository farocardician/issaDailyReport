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


@pytest.mark.parametrize("actor_role", ["ADMIN", "SUPER_ADMIN"])
def test_menu_users_opens_manage_users_menu_for_admin_and_super_admin(actor_role: str) -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role=actor_role, telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers([actor]), _root_step(actor_role))

    asyncio.run(flow.handle_callback(_callback_update(chat, "menu:users"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.MANAGE_USERS_MENU.value
    assert _last_message(chat)["text"] == "MANAGE_USERS_MENU"
    assert _callback_data(_last_message(chat)) == ["users:add", "users:list", "users:back:menu"]


@pytest.mark.parametrize("actor_role", ["ADMIN", "SUPER_ADMIN"])
def test_add_user_happy_path_creates_user_only_after_save(actor_role: str) -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role=actor_role, telegram_user_id=7)
    users = _FakeUsers([actor])
    flow, chat, sessions, users = _flow(users, Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:add"), SimpleNamespace()))
    assert users.created == []
    assert sessions.session["current_step"] == Step.USER_FORM_INPUT.value

    for text in ["Budi", "+6281280003276", "budi@example.com", "Lewati"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    assert users.created == []
    assert sessions.session["current_step"] == Step.USER_FORM_REVIEW.value
    assert "USER_FORM_REVIEW" in chat.sent_messages[-1]["text"]

    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    created = users.created[0]
    assert created["role"] == "USER"
    assert created["status"] == "Aktif"
    assert created["telegram_user_id"] is None
    assert created["telegram_chat_id"] is None
    assert created["name"] == "Budi"
    assert created["phone"] == "081280003276"
    assert created["email"] == "budi@example.com"
    assert created["notes"] is None
    assert sessions.session["current_step"] == Step.MANAGE_USERS_MENU.value
    assert "USER_ADDED" in chat.sent_messages[-1]["text"]


def test_add_user_duplicate_phone_rejects_inactive_conflict() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    inactive = _user("USR-OLD", "Old", "081280003276", role="USER", status="Nonaktif")
    flow, chat, sessions, users = _flow(_FakeUsers([actor, inactive]), Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:add"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Budi"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "+6281280003276"), SimpleNamespace()))

    assert users.created == []
    assert sessions.session["current_step"] == Step.USER_FORM_INPUT.value
    assert sessions.session["draft_report"]["user_form"]["pos"] == 1
    assert "USER_ERROR_PHONE_DUPLICATE" in chat.sent_messages[-1]["text"]


def test_add_user_invalid_email_reprompts() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    flow, chat, sessions, _users = _flow(_FakeUsers([actor]), Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:add"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Budi"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "081280003276"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "bad-email"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_FORM_INPUT.value
    assert sessions.session["draft_report"]["user_form"]["pos"] == 2
    assert "USER_ERROR_EMAIL_INVALID" in chat.sent_messages[-1]["text"]


def test_save_time_duplicate_phone_revalidates_before_create() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    users = _FakeUsers([actor])
    flow, chat, sessions, users = _flow(users, Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:add"), SimpleNamespace()))
    for text in ["Budi", "081280003276", "Lewati", "Lewati"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    users.users["USR-CONFLICT"] = _user("USR-CONFLICT", "Conflict", "+6281280003276", role="SUPER_ADMIN")
    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    assert users.created == []
    assert sessions.session["current_step"] == Step.USER_FORM_INPUT.value
    assert sessions.session["draft_report"]["user_form"]["plan"] == ["phone"]
    assert "USER_ERROR_PHONE_DUPLICATE" in chat.sent_messages[-1]["text"]


def test_list_and_detail_render_user_data() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    target = _user("USR-1", "Budi", "081280003276", role="USER", email="budi@example.com", notes="Jakarta")
    flow, chat, sessions, _users = _flow(_FakeUsers([actor, target]), Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:list"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_LIST.value
    assert _callback_data(_last_message(chat)) == ["users:view:USR-1", "users:back:menu"]

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:view:USR-1"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_DETAIL.value
    assert "Budi" in _last_message(chat)["text"]
    assert "budi@example.com" in _last_message(chat)["text"]
    assert _callback_data(_last_message(chat)) == [
        "users:edit:USR-1",
        "users:deactivate:USR-1",
        "users:reset_link:USR-1",
        "users:back:list",
    ]


def test_user_list_paginates_and_rerenders_page_callback() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    users = [
        _user(f"USR-{index}", f"User {index}", f"0812000000{index:02d}", role="USER")
        for index in range(8)
    ]
    flow, chat, sessions, _users = _flow(_FakeUsers([actor, *users]), Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:list"), SimpleNamespace()))

    assert sessions.session["draft_report"]["list_page"] == 0
    assert _callback_data(_last_message(chat)) == [
        "users:view:USR-0",
        "users:view:USR-1",
        "users:view:USR-2",
        "users:view:USR-3",
        "users:view:USR-4",
        "users:view:USR-5",
        "users:noop",
        "users:page:1",
        "users:back:menu",
    ]

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:page:1"), SimpleNamespace()))

    assert sessions.session["draft_report"]["list_page"] == 1
    assert _callback_data(_last_message(chat)) == [
        "users:view:USR-6",
        "users:view:USR-7",
        "users:page:0",
        "users:noop",
        "users:back:menu",
    ]


def test_edit_user_updates_basic_fields_without_touching_role_status_or_telegram() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    target = _user("USR-1", "Budi", "081280003276", role="USER", telegram_user_id=9, status="Aktif")
    flow, chat, sessions, users = _flow(
        _FakeUsers([actor, target]),
        Step.USER_DETAIL,
        {"user_name": "Admin", "user_target_id": "USR-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:edit:USR-1"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "users:field:phone"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "+6281299990000"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    updated = users.users["USR-1"]
    assert updated["phone"] == "081299990000"
    assert updated["role"] == "USER"
    assert updated["status"] == "Aktif"
    assert updated["telegram_user_id"] == 9
    assert users.updated_basic == ["USR-1"]
    assert sessions.session["current_step"] == Step.USER_DETAIL.value
    assert "USER_UPDATED" in _last_message(chat)["text"]


def test_deactivate_and_reactivate_require_confirmation_and_only_change_status() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    target = _user("USR-1", "Budi", "081280003276", role="USER", telegram_user_id=9, status="Aktif")
    flow, chat, sessions, users = _flow(
        _FakeUsers([actor, target]),
        Step.USER_DETAIL,
        {"user_name": "Admin", "user_target_id": "USR-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:deactivate:USR-1"), SimpleNamespace()))
    assert users.users["USR-1"]["status"] == "Aktif"
    assert sessions.session["current_step"] == Step.USER_CONFIRM_STATUS.value

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:confirm_status"), SimpleNamespace()))
    assert users.users["USR-1"]["status"] == "Nonaktif"
    assert users.users["USR-1"]["telegram_user_id"] == 9
    assert sessions.session["current_step"] == Step.USER_DETAIL.value

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:reactivate:USR-1"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "users:confirm_status"), SimpleNamespace()))
    assert users.users["USR-1"]["status"] == "Aktif"
    assert users.status_changes == [("USR-1", "Nonaktif"), ("USR-1", "Aktif")]


def test_reset_link_requires_confirmation_and_clears_only_telegram_fields() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    target = _user("USR-1", "Budi", "081280003276", role="USER", telegram_user_id=9, status="Aktif")
    flow, chat, sessions, users = _flow(
        _FakeUsers([actor, target]),
        Step.USER_DETAIL,
        {"user_name": "Admin", "user_target_id": "USR-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:reset_link:USR-1"), SimpleNamespace()))
    assert users.users["USR-1"]["telegram_user_id"] == 9
    assert sessions.session["current_step"] == Step.USER_CONFIRM_RESET_LINK.value

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:confirm_reset"), SimpleNamespace()))
    assert users.users["USR-1"]["telegram_user_id"] is None
    assert users.users["USR-1"]["telegram_chat_id"] is None
    assert users.users["USR-1"]["name"] == "Budi"
    assert users.users["USR-1"]["status"] == "Aktif"
    assert users.reset_links == ["USR-1"]


@pytest.mark.parametrize("scenario", ["user_role", "unlinked", "deactivated"])
def test_unauthorized_actor_hitting_users_callback_is_denied(scenario: str) -> None:
    users = {
        "user_role": [_user("ACTOR", "User", "081200000001", role="USER", telegram_user_id=7)],
        "unlinked": [],
        "deactivated": [_user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7, status="Nonaktif")],
    }[scenario]
    flow, chat, sessions, _users = _flow(_FakeUsers(users), Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:list"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.MANAGE_USERS_MENU.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


def test_target_role_guard_blocks_admin_record() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    target_admin = _user("ADM-1", "Other Admin", "081280003276", role="ADMIN")
    flow, chat, sessions, _users = _flow(_FakeUsers([actor, target_admin]), Step.USER_LIST)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:view:ADM-1"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.USER_LIST.value
    assert chat.sent_messages[-1]["text"] == "MENU_ACCESS_DENIED"


def test_newly_created_user_can_activate_and_enter_report_flow() -> None:
    actor = _user("ACTOR", "Admin", "081200000001", role="ADMIN", telegram_user_id=7)
    users = _FakeUsers([actor])
    flow, chat, _sessions, users = _flow(users, Step.MANAGE_USERS_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "users:add"), SimpleNamespace()))
    for text in ["Budi", "81280003276", "Lewati", "Lewati", "Simpan"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    created = users.created[0]
    assert created["phone"] == "081280003276"
    user_chat = _FakeChat(chat_id=100)
    user_sessions = _FakeSessions(Step.AWAITING_PHONE)
    user_flow = _report_flow(users, user_chat, user_sessions)

    asyncio.run(
        user_flow.handle_message(
            _contact_update(user_chat, "+6281280003276", telegram_user_id=8),
            SimpleNamespace(),
        )
    )

    assert users.users[created["user_id"]]["telegram_user_id"] == 8
    assert user_sessions.session["current_step"] == Step.AWAITING_LOCATION.value
    assert user_sessions.session["user_id"] == created["user_id"]
    assert "START Pilih Toko Manual" in user_chat.sent_messages[-1]["text"]


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
        "MANAGE_USERS_MENU": "{{notice}}MANAGE_USERS_MENU",
        "USER_LIST": "{{notice}}USER_LIST",
        "USER_LIST_EMPTY": "{{notice}}USER_LIST_EMPTY",
        "USER_LIST_BUTTON": "{{user_name}} - {{status}}",
        "USER_DETAIL": "{{notice}}USER_DETAIL {{name}} {{phone}} {{email}} {{notes}} {{status}} {{telegram_link_status}}",
        "USER_TELEGRAM_LINKED_YES": "Terhubung",
        "USER_TELEGRAM_LINKED_NO": "Belum terhubung",
        "ASK_USER_NAME": "{{error}}ASK_USER_NAME",
        "ASK_USER_PHONE": "{{error}}ASK_USER_PHONE",
        "ASK_USER_EMAIL": "{{error}}ASK_USER_EMAIL",
        "ASK_USER_NOTES": "{{error}}ASK_USER_NOTES",
        "USER_ERROR_NAME_REQUIRED": "USER_ERROR_NAME_REQUIRED\n",
        "USER_ERROR_PHONE_REQUIRED": "USER_ERROR_PHONE_REQUIRED\n",
        "USER_ERROR_PHONE_INVALID": "USER_ERROR_PHONE_INVALID\n",
        "USER_ERROR_PHONE_DUPLICATE": "USER_ERROR_PHONE_DUPLICATE\n",
        "USER_ERROR_EMAIL_INVALID": "USER_ERROR_EMAIL_INVALID\n",
        "USER_FORM_REVIEW": "{{notice}}USER_FORM_REVIEW {{name}} {{phone}} {{email}} {{notes}}",
        "USER_EDIT_MENU": "USER_EDIT_MENU",
        "USER_CONFIRM_DEACTIVATE": "USER_CONFIRM_DEACTIVATE {{user_name}}",
        "USER_CONFIRM_REACTIVATE": "USER_CONFIRM_REACTIVATE {{user_name}}",
        "USER_CONFIRM_RESET_LINK": "USER_CONFIRM_RESET_LINK {{user_name}}",
        "USER_ADDED": "USER_ADDED\n",
        "USER_UPDATED": "USER_UPDATED\n",
        "USER_DEACTIVATED": "USER_DEACTIVATED\n",
        "USER_REACTIVATED": "USER_REACTIVATED\n",
        "USER_LINK_RESET": "USER_LINK_RESET\n",
        "BUTTON_SHARE_LOCATION": "Bagikan Lokasi",
        "BUTTON_SHARE_CONTACT": "Bagikan Nomor HP",
        "BUTTON_START": "Mulai",
        "BUTTON_SELECT_STORE_MANUAL": "Pilih Toko Manual",
        "BUTTON_MENU_INPUT_REPORT": "Input Laporan Harian",
        "BUTTON_MENU_MANAGE_USERS": "Kelola User",
        "BUTTON_MENU_MANAGE_ADMINS": "Kelola Admin",
        "BUTTON_MENU_MANAGE_STORES": "Kelola Store",
        "BUTTON_USER_ADD": "Tambah User",
        "BUTTON_USER_LIST": "Daftar User",
        "BUTTON_BACK": "Kembali",
        "BUTTON_USER_EDIT": "Ubah Data",
        "BUTTON_USER_DEACTIVATE": "Nonaktifkan",
        "BUTTON_USER_REACTIVATE": "Aktifkan Kembali",
        "BUTTON_USER_RESET_LINK": "Reset Link Telegram",
        "BUTTON_PAGE_PREV": "‹ Sebelumnya",
        "BUTTON_PAGE_NEXT": "Berikutnya ›",
        "BUTTON_USER_FIELD_NAME": "Nama",
        "BUTTON_USER_FIELD_PHONE": "Nomor HP",
        "BUTTON_USER_FIELD_EMAIL": "Email",
        "BUTTON_USER_FIELD_NOTES": "Catatan",
        "BUTTON_SAVE": "Simpan",
        "BUTTON_EDIT": "Ubah",
        "BUTTON_CONFIRM_YES": "Ya",
        "BUTTON_CANCEL": "Batal",
        "BUTTON_PREVIOUS": "Sebelumnya",
        "BUTTON_SKIP": "Lewati",
        "PROGRESS_MAIN_LABEL": "Langkah",
        "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
        "PROGRESS_PHASE_STORE": "Pilih Toko",
        "PAGE_INDICATOR": "Hal. {{current}}/{{total}}",
    }


def _root_step(role: str) -> Step:
    return Step.SUPER_ADMIN_MENU if role == "SUPER_ADMIN" else Step.ADMIN_MENU


def _user(
    user_id: str,
    name: str,
    phone: str,
    role: str = "USER",
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
            "draft_report": draft or {"user_name": "Admin"},
            "selected_store_id": None,
            "user_id": "ACTOR",
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

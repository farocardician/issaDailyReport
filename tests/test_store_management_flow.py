from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from telegram.constants import ChatType

from app.bot.flow import ReportFlow
from app.domain.session_state import Step
from app.domain.store_matching import StoreLocation
from app.templates import MessageTemplates


def test_menu_stores_opens_manage_stores_menu() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    flow, chat, sessions, _stores = _flow(_FakeStores([]), _FakeUsers([actor]), Step.SUPER_ADMIN_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "menu:stores"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.MANAGE_STORES_MENU.value
    assert _last_message(chat)["text"] == "MANAGE_STORES_MENU"
    assert _callback_data(_last_message(chat)) == ["stores:add", "stores:list", "stores:back:menu"]


def test_add_store_happy_path_creates_active_store_only_after_save() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    stores = _FakeStores([])
    flow, chat, sessions, stores = _flow(stores, _FakeUsers([actor]), Step.MANAGE_STORES_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:add"), SimpleNamespace()))
    assert stores.created == []

    for text in ["VIZU", "Mall Besar", "Utama", "Jakarta", "-6,2", "106.8", "100", "Lewati"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.STORE_FORM_REVIEW.value
    assert stores.created == []

    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    created = stores.created[0]
    assert created.status == "Aktif"
    assert created.brand == "VIZU"
    assert created.department_store == "Mall Besar"
    assert created.branch == "Utama"
    assert created.city == "Jakarta"
    assert created.latitude == -6.2
    assert created.longitude == 106.8
    assert created.allowed_radius_meter == 100
    assert created.notes is None
    assert sessions.session["current_step"] == Step.MANAGE_STORES_MENU.value
    assert "STORE_ADDED" in _last_message(chat)["text"]


def test_list_and_detail_render_store_data() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    target = _store("STR-1", branch="Utama", notes="Lantai 1")
    flow, chat, sessions, _stores = _flow(_FakeStores([target]), _FakeUsers([actor]), Step.MANAGE_STORES_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:list"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.STORE_LIST.value
    assert _callback_data(_last_message(chat)) == ["stores:view:STR-1", "stores:back:menu"]

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:view:STR-1"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.STORE_DETAIL.value
    assert "VIZU" in _last_message(chat)["text"]
    assert "Utama" in _last_message(chat)["text"]
    assert "Lantai 1" in _last_message(chat)["text"]
    assert _callback_data(_last_message(chat)) == [
        "stores:edit:STR-1",
        "stores:deactivate:STR-1",
        "stores:back:list",
    ]


def test_edit_store_updates_fields_without_changing_status() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    target = _store("STR-1", branch="Lama", status="Aktif")
    flow, chat, sessions, stores = _flow(
        _FakeStores([target]),
        _FakeUsers([actor]),
        Step.STORE_DETAIL,
        {"user_name": "Super", "store_target_id": "STR-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:edit:STR-1"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:field:branch"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Baru"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    updated = stores.stores["STR-1"]
    assert updated.branch == "Baru"
    assert updated.status == "Aktif"
    assert stores.updated == ["STR-1"]
    assert sessions.session["current_step"] == Step.STORE_DETAIL.value
    assert "STORE_UPDATED" in _last_message(chat)["text"]


def test_deactivate_and_reactivate_store_require_confirmation_and_only_change_status() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    target = _store("STR-1", branch="Utama", status="Aktif")
    flow, chat, sessions, stores = _flow(
        _FakeStores([target]),
        _FakeUsers([actor]),
        Step.STORE_DETAIL,
        {"user_name": "Super", "store_target_id": "STR-1"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:deactivate:STR-1"), SimpleNamespace()))
    assert stores.stores["STR-1"].status == "Aktif"
    assert sessions.session["current_step"] == Step.STORE_CONFIRM_STATUS.value

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:confirm_status"), SimpleNamespace()))
    assert stores.stores["STR-1"].status == "Nonaktif"
    assert stores.stores["STR-1"].branch == "Utama"

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:reactivate:STR-1"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:confirm_status"), SimpleNamespace()))
    assert stores.stores["STR-1"].status == "Aktif"
    assert stores.status_changes == [("STR-1", "Nonaktif"), ("STR-1", "Aktif")]


def test_duplicate_identity_rejected_on_add_save() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    stores = _FakeStores([_store("STR-1", branch="Utama")])
    flow, chat, sessions, stores = _flow(stores, _FakeUsers([actor]), Step.MANAGE_STORES_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:add"), SimpleNamespace()))
    for text in [" vIzu ", "Mall Besar", "Utama", "Jakarta", "-6.2", "106.8", "100", "Lewati"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    assert len(stores.created) == 0
    assert sessions.session["current_step"] == Step.STORE_FORM_REVIEW.value
    assert "STORE_ERROR_DUPLICATE_IDENTITY" in _last_message(chat)["text"]


def test_duplicate_identity_rejected_on_editing_active_store() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    stores = _FakeStores(
        [
            _store("STR-1", branch="Utama", status="Aktif"),
            _store("STR-2", branch="Kedua", status="Aktif"),
        ]
    )
    flow, chat, sessions, stores = _flow(
        stores,
        _FakeUsers([actor]),
        Step.STORE_DETAIL,
        {"user_name": "Super", "store_target_id": "STR-2"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:edit:STR-2"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:field:branch"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Utama"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Simpan"), SimpleNamespace()))

    assert stores.stores["STR-2"].branch == "Kedua"
    assert stores.updated == []
    assert sessions.session["current_step"] == Step.STORE_FORM_REVIEW.value
    assert "STORE_ERROR_DUPLICATE_IDENTITY" in _last_message(chat)["text"]


def test_reactivation_duplicate_guard_blocks_then_allows_when_identity_available() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    stores = _FakeStores(
        [
            _store("STR-1", branch="Utama", status="Aktif"),
            _store("STR-2", branch="Utama", status="Nonaktif"),
        ]
    )
    flow, chat, sessions, stores = _flow(
        stores,
        _FakeUsers([actor]),
        Step.STORE_DETAIL,
        {"user_name": "Super", "store_target_id": "STR-2"},
    )

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:reactivate:STR-2"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:confirm_status"), SimpleNamespace()))

    assert stores.stores["STR-2"].status == "Nonaktif"
    assert "STORE_ERROR_DUPLICATE_IDENTITY" in _last_message(chat)["text"]

    stores.stores["STR-1"] = replace(stores.stores["STR-1"], status="Nonaktif")
    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:reactivate:STR-2"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:confirm_status"), SimpleNamespace()))

    assert stores.stores["STR-2"].status == "Aktif"
    assert stores.status_changes == [("STR-2", "Aktif")]
    assert sessions.session["current_step"] == Step.STORE_DETAIL.value


def test_coordinate_and_radius_validation_errors_reprompt() -> None:
    actor = _user("SA-1", "Super", role="SUPER_ADMIN", telegram_user_id=7)
    flow, chat, sessions, _stores = _flow(_FakeStores([]), _FakeUsers([actor]), Step.MANAGE_STORES_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:add"), SimpleNamespace()))
    for text in ["VIZU", "Mall Besar", "Utama", "Jakarta"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    asyncio.run(flow.handle_message(_text_update(chat, "91"), SimpleNamespace()))
    assert sessions.session["current_step"] == Step.STORE_FORM_INPUT.value
    assert "STORE_ERROR_LATITUDE_INVALID" in _last_message(chat)["text"]

    for text in ["-6.2", "106.8"]:
        asyncio.run(flow.handle_message(_text_update(chat, text), SimpleNamespace()))

    asyncio.run(flow.handle_message(_text_update(chat, "0"), SimpleNamespace()))
    assert sessions.session["current_step"] == Step.STORE_FORM_INPUT.value
    assert "STORE_ERROR_RADIUS_INVALID" in _last_message(chat)["text"]


@pytest.mark.parametrize("role", ["ADMIN", "USER"])
def test_non_super_admin_actor_hitting_store_callback_is_denied(role: str) -> None:
    actor = _user("ACTOR", "Actor", role=role, telegram_user_id=7)
    flow, chat, sessions, _stores = _flow(_FakeStores([]), _FakeUsers([actor]), Step.MANAGE_STORES_MENU)

    asyncio.run(flow.handle_callback(_callback_update(chat, "stores:list"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.MANAGE_STORES_MENU.value
    assert _last_message(chat)["text"] == "MENU_ACCESS_DENIED"


def test_deactivated_store_is_excluded_from_manual_matching_keyboard() -> None:
    stores = _FakeStores(
        [
            _store("STR-INACTIVE", branch="Nonaktif", status="Nonaktif", latitude=-6.2, longitude=106.8),
            _store("STR-ACTIVE", branch="Aktif", status="Aktif", latitude=-6.2, longitude=106.8),
        ]
    )
    reports = _FakeReports()
    flow, chat, sessions, _stores = _flow(
        stores,
        _FakeUsers([_user("USR-1", "Ani", role="USER", telegram_user_id=7)]),
        Step.MANUAL_STORE_SELECTION,
        {},
        user_id="USR-1",
        reports=reports,
    )

    asyncio.run(flow.handle_message(_location_update(chat, latitude=0, longitude=0), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.MANUAL_STORE_SELECTION.value
    assert _callback_data(_last_message(chat)) == ["store:STR-ACTIVE"]
    assert reports.writes == []


def _flow(
    stores: "_FakeStores",
    users: "_FakeUsers",
    step: Step,
    draft: dict[str, Any] | None = None,
    user_id: str = "SA-1",
    reports: Any | None = None,
) -> tuple[ReportFlow, "_FakeChat", "_FakeSessions", "_FakeStores"]:
    templates = _templates()
    chat = _FakeChat()
    sessions = _FakeSessions(step, draft, user_id)
    return (
        ReportFlow(
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
            stores=stores,
            sales_sources=SimpleNamespace(),
            stock_issues=SimpleNamespace(),
            users=users,
            reports=reports or SimpleNamespace(),
            sessions=sessions,
        ),
        chat,
        sessions,
        stores,
    )


def _templates() -> dict[str, str]:
    return {
        "UNKNOWN_COMMAND": "UNKNOWN_COMMAND",
        "START": "{{progress}}\nSTART {{manual_store_button}}",
        "LOCATION_NOT_FOUND": "{{progress}}\nLOCATION_NOT_FOUND",
        "MANUAL_STORE_SELECTION": "{{progress}}\nMANUAL_STORE_SELECTION",
        "MENU_ADMIN": "MENU_ADMIN",
        "MENU_SUPER_ADMIN": "MENU_SUPER_ADMIN",
        "MENU_ACCESS_DENIED": "MENU_ACCESS_DENIED",
        "MANAGE_STORES_MENU": "{{notice}}MANAGE_STORES_MENU",
        "STORE_LIST": "{{notice}}STORE_LIST",
        "STORE_LIST_EMPTY": "{{notice}}STORE_LIST_EMPTY",
        "STORE_LIST_BUTTON": "{{store_label}} - {{status}}",
        "STORE_DETAIL": (
            "{{notice}}STORE_DETAIL {{store_id}} {{brand}} {{department_store}} {{branch}} {{city}} "
            "{{latitude}} {{longitude}} {{allowed_radius}} {{notes}} {{status}}"
        ),
        "STORE_FORM_REVIEW": (
            "{{notice}}STORE_FORM_REVIEW {{brand}} {{department_store}} {{branch}} {{city}} "
            "{{latitude}} {{longitude}} {{allowed_radius}} {{notes}}"
        ),
        "STORE_EDIT_MENU": "STORE_EDIT_MENU",
        "STORE_CONFIRM_DEACTIVATE": "STORE_CONFIRM_DEACTIVATE {{store_label}}",
        "STORE_CONFIRM_REACTIVATE": "STORE_CONFIRM_REACTIVATE {{store_label}}",
        "STORE_ADDED": "STORE_ADDED\n",
        "STORE_UPDATED": "STORE_UPDATED\n",
        "STORE_DEACTIVATED": "STORE_DEACTIVATED\n",
        "STORE_REACTIVATED": "STORE_REACTIVATED\n",
        "STORE_ERROR_BRAND_REQUIRED": "STORE_ERROR_BRAND_REQUIRED\n",
        "STORE_ERROR_DEPARTMENT_REQUIRED": "STORE_ERROR_DEPARTMENT_REQUIRED\n",
        "STORE_ERROR_BRANCH_REQUIRED": "STORE_ERROR_BRANCH_REQUIRED\n",
        "STORE_ERROR_CITY_REQUIRED": "STORE_ERROR_CITY_REQUIRED\n",
        "STORE_ERROR_LATITUDE_INVALID": "STORE_ERROR_LATITUDE_INVALID\n",
        "STORE_ERROR_LONGITUDE_INVALID": "STORE_ERROR_LONGITUDE_INVALID\n",
        "STORE_ERROR_RADIUS_INVALID": "STORE_ERROR_RADIUS_INVALID\n",
        "STORE_ERROR_DUPLICATE_IDENTITY": "STORE_ERROR_DUPLICATE_IDENTITY\n",
        "ASK_STORE_BRAND": "{{error}}ASK_STORE_BRAND",
        "ASK_STORE_DEPARTMENT": "{{error}}ASK_STORE_DEPARTMENT",
        "ASK_STORE_BRANCH": "{{error}}ASK_STORE_BRANCH",
        "ASK_STORE_CITY": "{{error}}ASK_STORE_CITY",
        "ASK_STORE_LATITUDE": "{{error}}ASK_STORE_LATITUDE",
        "ASK_STORE_LONGITUDE": "{{error}}ASK_STORE_LONGITUDE",
        "ASK_STORE_RADIUS": "{{error}}ASK_STORE_RADIUS",
        "ASK_STORE_NOTES": "{{error}}ASK_STORE_NOTES",
        "BUTTON_SHARE_LOCATION": "Bagikan Lokasi",
        "BUTTON_START": "Mulai",
        "BUTTON_SELECT_STORE_MANUAL": "Pilih Toko Manual",
        "BUTTON_MENU_INPUT_REPORT": "Input Laporan Harian",
        "BUTTON_MENU_MANAGE_USERS": "Kelola User",
        "BUTTON_MENU_MANAGE_ADMINS": "Kelola Admin",
        "BUTTON_MENU_MANAGE_STORES": "Kelola Store",
        "BUTTON_STORE_ADD": "Tambah Store",
        "BUTTON_STORE_LIST": "Daftar Store",
        "BUTTON_STORE_EDIT": "Ubah Data",
        "BUTTON_STORE_DEACTIVATE": "Nonaktifkan",
        "BUTTON_STORE_REACTIVATE": "Aktifkan Kembali",
        "BUTTON_STORE_FIELD_BRAND": "Brand",
        "BUTTON_STORE_FIELD_DEPARTMENT": "Department",
        "BUTTON_STORE_FIELD_BRANCH": "Branch",
        "BUTTON_STORE_FIELD_CITY": "City",
        "BUTTON_STORE_FIELD_LATITUDE": "Latitude",
        "BUTTON_STORE_FIELD_LONGITUDE": "Longitude",
        "BUTTON_STORE_FIELD_RADIUS": "Radius",
        "BUTTON_STORE_FIELD_NOTES": "Catatan",
        "BUTTON_BACK": "Kembali",
        "BUTTON_SAVE": "Simpan",
        "BUTTON_EDIT": "Ubah",
        "BUTTON_CONFIRM_YES": "Ya",
        "BUTTON_CANCEL": "Batal",
        "BUTTON_PREVIOUS": "Sebelumnya",
        "BUTTON_SKIP": "Lewati",
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
    branch: str,
    status: str = "Aktif",
    latitude: float = -6.2,
    longitude: float = 106.8,
    notes: str | None = None,
) -> StoreLocation:
    return StoreLocation(
        store_id=store_id,
        department_store="Mall Besar",
        branch=branch,
        city="Jakarta",
        brand="VIZU",
        latitude=latitude,
        longitude=longitude,
        allowed_radius_meter=100,
        status=status,
        notes=notes,
    )


def _user(
    user_id: str,
    name: str,
    role: str,
    telegram_user_id: int | None = None,
    status: str = "Aktif",
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "role": role,
        "name": name,
        "phone": "081280003276",
        "email": None,
        "telegram_user_id": telegram_user_id,
        "telegram_chat_id": telegram_user_id,
        "status": status,
        "notes": None,
    }


def _text_update(chat: "_FakeChat", text: str, telegram_user_id: int = 7) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(text=text, location=None, contact=None),
        callback_query=None,
        telegram_user_id=telegram_user_id,
    )


def _location_update(chat: "_FakeChat", latitude: float, longitude: float) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=SimpleNamespace(
            text=None,
            location=SimpleNamespace(latitude=latitude, longitude=longitude),
            contact=None,
        ),
        callback_query=None,
        telegram_user_id=7,
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


class _FakeStores:
    def __init__(self, stores: list[StoreLocation]) -> None:
        self.stores = {store.store_id: store for store in stores}
        self.created: list[StoreLocation] = []
        self.updated: list[str] = []
        self.status_changes: list[tuple[str, str]] = []

    async def list_active(self, active_status: str) -> list[StoreLocation]:
        return [store for store in self.stores.values() if store.status == active_status]

    async def list_all(self) -> list[StoreLocation]:
        return sorted(self.stores.values(), key=lambda store: (store.brand, store.branch, store.city))

    async def get_by_id(self, store_id: str) -> StoreLocation | None:
        return self.stores.get(store_id)

    async def create_store(
        self,
        store_id: str,
        brand: str,
        department_store: str,
        branch: str,
        city: str,
        latitude: float,
        longitude: float,
        allowed_radius_meter: int,
        notes: str | None,
        status: str,
    ) -> None:
        store = StoreLocation(
            store_id=store_id,
            brand=brand,
            department_store=department_store,
            branch=branch,
            city=city,
            latitude=latitude,
            longitude=longitude,
            allowed_radius_meter=allowed_radius_meter,
            status=status,
            notes=notes,
        )
        self.stores[store_id] = store
        self.created.append(store)

    async def update_store(
        self,
        store_id: str,
        brand: str,
        department_store: str,
        branch: str,
        city: str,
        latitude: float,
        longitude: float,
        allowed_radius_meter: int,
        notes: str | None,
    ) -> None:
        self.updated.append(store_id)
        self.stores[store_id] = replace(
            self.stores[store_id],
            brand=brand,
            department_store=department_store,
            branch=branch,
            city=city,
            latitude=latitude,
            longitude=longitude,
            allowed_radius_meter=allowed_radius_meter,
            notes=notes,
        )

    async def set_status(self, store_id: str, status: str) -> None:
        self.status_changes.append((store_id, status))
        self.stores[store_id] = replace(self.stores[store_id], status=status)


class _FakeUsers:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self.users = users

    async def find_active_by_telegram_user_id(
        self,
        telegram_user_id: int,
        active_status: str,
    ) -> list[dict[str, Any]]:
        return [
            user
            for user in self.users
            if user["telegram_user_id"] == telegram_user_id and user["status"] == active_status
        ]


class _FakeReports:
    def __init__(self) -> None:
        self.writes: list[Any] = []


class _FakeSessions:
    def __init__(self, step: Step, draft: dict[str, Any] | None, user_id: str) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.deleted_chat_ids: list[int] = []
        self.session: dict[str, Any] | None = {
            "current_step": step.value,
            "draft_report": draft or {"user_name": "Super"},
            "selected_store_id": None,
            "user_id": user_id,
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

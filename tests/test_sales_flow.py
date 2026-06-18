from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from telegram.constants import ChatType

from app.bot.flow import ReportFlow
from app.domain.sales_sources import GmvSource
from app.domain.session_state import Step
from app.domain.stock_issues import StockIssue
from app.domain.store_matching import StoreLocation
from app.templates import MessageTemplates


def test_inactive_source_not_in_picker() -> None:
    flow, chat, _sessions, _reports, _bot = _flow(
        Step.ASK_SALES_SOURCES,
        {},
        sources=[_source("outlet", "Outlet"), _source("old", "Old Source", status="Nonaktif")],
    )

    asyncio.run(flow.handle_message(_text_update(chat, "x"), SimpleNamespace()))

    keyboard = chat.sent_messages[-1]["reply_markup"].to_dict()["inline_keyboard"]
    button_text = [button["text"] for row in keyboard for button in row]
    assert "Outlet" in button_text
    assert "Old Source" not in button_text
    assert "Selesai" not in button_text


def test_no_sales_reaches_stock_issue_and_final_review_admin_show_zero_totals() -> None:
    flow, chat, sessions, reports, bot = _flow(Step.ASK_SALES_SOURCES, {"user_name": "Ani"})

    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_source:no_sales"), SimpleNamespace()))
    assert sessions.session["current_step"] == Step.ASK_STOCK_ISSUE.value
    assert sessions.session["draft_report"]["sales_no_sales"] is True

    asyncio.run(flow.handle_callback(_callback_update(chat, "stock_issue:none"), SimpleNamespace()))
    asyncio.run(flow.handle_message(_text_update(chat, "Tidak Ada"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.REVIEW_SUMMARY.value
    assert "Tidak Ada Penjualan" in chat.sent_messages[-1]["text"]
    assert "Total GMV: 0" in chat.sent_messages[-1]["text"]

    asyncio.run(flow.handle_callback(_callback_update(chat, "summary:submit"), SimpleNamespace(bot=bot)))

    assert reports.created[0]["sales_rows"] == []
    assert "Tidak Ada Penjualan" in bot.sent_messages[0]["text"]
    assert "Total GMV: 0" in bot.sent_messages[0]["text"]


def test_multi_source_selection_input_order_and_summary_totals() -> None:
    flow, chat, sessions, _reports, _bot = _flow(Step.ASK_SALES_SOURCES, {"user_name": "Ani"})

    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_source:toggle:outlet"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_source:toggle:shopee"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_source:done"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ASK_SALES_INPUT.value
    assert sessions.session["draft_report"]["sales_input_plan"] == [
        ["outlet", "traffic"],
        ["outlet", "gmv"],
        ["outlet", "order_count"],
        ["outlet", "pieces_sold"],
        ["shopee", "gmv"],
        ["shopee", "order_count"],
        ["shopee", "pieces_sold"],
    ]
    assert "ASK_SALES_TRAFFIC Outlet" in chat.sent_messages[-1]["text"]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [
        [{"text": "Sebelumnya"}, {"text": "Batal"}]
    ]

    for value in ["10", "100.000", "2", "3", "200000", "4", "5"]:
        asyncio.run(flow.handle_message(_text_update(chat, value), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.REVIEW_SALES_SUMMARY.value
    assert "Outlet | traffic=10 | gmv=100.000 | order=2 | pieces=3" in chat.sent_messages[-1]["text"]
    assert "Shopee | traffic=- | gmv=200.000 | order=4 | pieces=5" in chat.sent_messages[-1]["text"]
    assert "Total GMV: 300.000" in chat.sent_messages[-1]["text"]


def test_invalid_sales_input_reprompts_same_field_without_advancing() -> None:
    draft = _sales_draft(["outlet"], {"outlet": _sales_row("Outlet", True)}, [["outlet", "gmv"]])
    flow, chat, sessions, _reports, _bot = _flow(Step.ASK_SALES_INPUT, draft)

    asyncio.run(flow.handle_message(_text_update(chat, "-1"), SimpleNamespace()))

    assert sessions.session["draft_report"]["sales_input_pos"] == 0
    assert "ASK_SALES_GMV Outlet" in chat.sent_messages[-1]["text"]


def test_sales_input_previous_returns_to_picker_on_first_field() -> None:
    draft = _sales_draft(["outlet"], {"outlet": _sales_row("Outlet", True)}, [["outlet", "gmv"]])
    draft["sales_input_back_step"] = Step.ASK_SALES_SOURCES.value
    flow, chat, sessions, _reports, _bot = _flow(Step.ASK_SALES_INPUT, draft)

    asyncio.run(flow.handle_message(_text_update(chat, "Sebelumnya"), SimpleNamespace()))

    assert sessions.session["current_step"] == Step.ASK_SALES_SOURCES.value
    assert "ASK_SALES_SOURCES" in chat.sent_messages[-1]["text"]


def test_sales_input_cancel_cancels_session() -> None:
    draft = _sales_draft(["outlet"], {"outlet": _sales_row("Outlet", True)}, [["outlet", "gmv"]])
    flow, chat, sessions, _reports, _bot = _flow(Step.ASK_SALES_INPUT, draft)

    asyncio.run(flow.handle_message(_text_update(chat, "Batal"), SimpleNamespace()))

    assert sessions.deleted_chat_ids == [chat.id]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [[{"text": "Mulai"}]]


def test_sales_summary_text_routing() -> None:
    draft = _complete_sales_draft()
    flow, chat, sessions, _reports, _bot = _flow(Step.REVIEW_SALES_SUMMARY, draft)

    asyncio.run(flow.handle_message(_text_update(chat, "gibberish"), SimpleNamespace()))
    assert sessions.session["current_step"] == Step.REVIEW_SALES_SUMMARY.value
    assert "SALES_SUMMARY" in chat.sent_messages[-1]["text"]

    asyncio.run(flow.handle_message(_text_update(chat, "Lanjutkan"), SimpleNamespace()))
    assert sessions.session["current_step"] == Step.ASK_STOCK_ISSUE.value

    flow, chat, sessions, _reports, _bot = _flow(Step.REVIEW_SALES_SUMMARY, draft)
    asyncio.run(flow.handle_message(_text_update(chat, "Batal"), SimpleNamespace()))
    assert sessions.deleted_chat_ids == [chat.id]
    assert chat.sent_messages[-1]["reply_markup"].to_dict()["keyboard"] == [[{"text": "Mulai"}]]


def test_edit_one_source_then_add_and_remove_sources() -> None:
    draft = _complete_sales_draft()
    flow, chat, sessions, _reports, _bot = _flow(Step.REVIEW_SALES_SUMMARY, draft)

    asyncio.run(flow.handle_message(_text_update(chat, "Ubah"), SimpleNamespace()))
    assert sessions.session["current_step"] == Step.EDIT_SALES_MENU.value

    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_edit:source:shopee"), SimpleNamespace()))
    assert sessions.session["draft_report"]["sales_input_plan"] == [
        ["shopee", "gmv"],
        ["shopee", "order_count"],
        ["shopee", "pieces_sold"],
    ]
    for value in ["300000", "6", "7"]:
        asyncio.run(flow.handle_message(_text_update(chat, value), SimpleNamespace()))
    assert "Total GMV: 400.000" in chat.sent_messages[-1]["text"]

    asyncio.run(flow.handle_message(_text_update(chat, "Ubah"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_edit:sources"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_source:toggle:tokopedia"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_source:toggle:outlet"), SimpleNamespace()))
    asyncio.run(flow.handle_callback(_callback_update(chat, "sales_source:done"), SimpleNamespace()))

    assert sessions.session["draft_report"]["sales_source_ids"] == ["shopee", "tokopedia"]
    assert "outlet" not in sessions.session["draft_report"]["sales_data"]
    assert sessions.session["draft_report"]["sales_input_plan"] == [
        ["tokopedia", "gmv"],
        ["tokopedia", "order_count"],
        ["tokopedia", "pieces_sold"],
    ]

    for value in ["500000", "8", "9"]:
        asyncio.run(flow.handle_message(_text_update(chat, value), SimpleNamespace()))

    assert "Shopee Snapshot | traffic=- | gmv=300.000 | order=6 | pieces=7" in chat.sent_messages[-1]["text"]
    assert "Tokopedia | traffic=- | gmv=500.000 | order=8 | pieces=9" in chat.sent_messages[-1]["text"]
    assert "Outlet |" not in chat.sent_messages[-1]["text"]


def test_submit_passes_snapshot_sales_rows() -> None:
    draft = {
        **_complete_sales_draft(),
        "stock_issue": "-",
        "note": "OK",
        "submitted_latitude": -6.2,
        "submitted_longitude": 106.8,
        "distance_from_store_meter": 10,
        "effective_radius_meter": 100,
    }
    flow, chat, sessions, reports, bot = _flow(Step.REVIEW_SUMMARY, draft)

    asyncio.run(flow.handle_callback(_callback_update(chat, "summary:submit"), SimpleNamespace(bot=bot)))

    assert sessions.deleted_chat_ids == [chat.id]
    sales_rows = reports.created[0]["sales_rows"]
    assert sales_rows == [
        {
            "report_id": reports.created[0]["report"]["report_id"],
            "gmv_source_id": "outlet",
            "source_label": "Outlet",
            "source_type": "outlet",
            "requires_traffic": True,
            "traffic": 10,
            "gmv": 100000,
            "order_count": 2,
            "pieces_sold": 3,
            "sort_order": 1,
        },
        {
            "report_id": reports.created[0]["report"]["report_id"],
            "gmv_source_id": "shopee",
            "source_label": "Shopee Snapshot",
            "source_type": "marketplace",
            "requires_traffic": False,
            "traffic": None,
            "gmv": 200000,
            "order_count": 4,
            "pieces_sold": 5,
            "sort_order": 3,
        },
    ]
    assert "Shopee Snapshot" in bot.sent_messages[0]["text"]


def _flow(
    step: Step,
    draft: dict[str, Any],
    sources: list[GmvSource] | None = None,
) -> tuple[ReportFlow, "_FakeChat", "_FakeSessions", "_FakeReports", "_FakeBot"]:
    templates = _templates()
    chat = _FakeChat()
    sessions = _FakeSessions(step, draft)
    reports = _FakeReports()
    bot = _FakeBot()
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
        stores=_FakeStores([_store()]),
        sales_sources=_FakeSalesSources(sources or [_source("outlet", "Outlet", True, 1), _source("shopee", "Shopee", sort_order=3), _source("tokopedia", "Tokopedia", sort_order=4)]),
        stock_issues=_FakeStockIssues([_stock_issue("size_empty", "Size Habis")]),
        users=SimpleNamespace(),
        reports=reports,
        sessions=sessions,
    )
    return flow, chat, sessions, reports, bot


def _templates() -> dict[str, str]:
    return {
        "UNKNOWN_COMMAND": "UNKNOWN_COMMAND",
        "ASK_SALES_SOURCES": "{{progress}}\nASK_SALES_SOURCES\n{{selected_sources}}",
        "ASK_SALES_TRAFFIC": "{{progress}}\n{{source_progress}}\nASK_SALES_TRAFFIC {{source}}",
        "ASK_SALES_GMV": "{{progress}}\n{{source_progress}}\nASK_SALES_GMV {{source}}",
        "ASK_SALES_ORDER": "{{progress}}\n{{source_progress}}\nASK_SALES_ORDER {{source}}",
        "ASK_SALES_PIECES": "{{progress}}\n{{source_progress}}\nASK_SALES_PIECES {{source}}",
        "SALES_SUMMARY": "{{progress}}\nSALES_SUMMARY\n{{sales_breakdown}}\nTotal GMV: {{total_gmv}}\nTotal Order: {{total_order}}\nTotal Pieces: {{total_pieces}}",
        "EDIT_SALES_MENU": "{{progress}}\nEDIT_SALES_MENU",
        "ASK_STOCK_ISSUE": "{{progress}}\nASK_STOCK_ISSUE\n{{selected_issues}}",
        "ASK_NOTE": "{{progress}}\nASK_NOTE",
        "REPORT_SUMMARY": "{{progress}}\nREPORT_SUMMARY\n{{sales_breakdown}}\nTotal GMV: {{total_gmv}}\nTotal Order: {{total_order}}\nTotal Pieces: {{total_pieces}}\n{{stock_issue}}\n{{note}}",
        "SUBMIT_SUCCESS": "SUBMIT_SUCCESS",
        "CANCELLED": "CANCELLED",
        "REPORT_ALREADY_EXISTS": "REPORT_ALREADY_EXISTS",
        "ADMIN_NOTIFICATION": "ADMIN {{store_label}} {{user_name}} {{sales_breakdown}} Total GMV: {{total_gmv}} {{location_status}}",
        "ADMIN_NOTIFICATION_CORRECTION": "ADMIN CORRECTION {{store_label}} {{user_name}} {{sales_breakdown}} Total GMV: {{total_gmv}} {{location_status}}",
        "BUTTON_NONE": "Tidak Ada",
        "BUTTON_START": "Mulai",
        "BUTTON_NO_SALES": "Tidak Ada Penjualan",
        "BUTTON_PREVIOUS": "Sebelumnya",
        "BUTTON_SALES_INPUT_NEXT": "Lanjut input {{source}}",
        "BUTTON_STOCK_ISSUE_NEXT": "Lanjut input {{issue}}",
        "BUTTON_SALES_CONTINUE": "Lanjutkan",
        "BUTTON_SALES_EDIT": "Ubah",
        "BUTTON_CANCEL": "Batal",
        "BUTTON_EDIT_SOURCES": "Tambah / Hapus Sumber Penjualan",
        "BUTTON_BACK_TO_SUMMARY": "Kembali ke Ringkasan",
        "BUTTON_SUBMIT": "Kirim",
        "BUTTON_RESTART": "Ulangi",
        "BUTTON_DUPLICATE_CONFIRM": "Ya, koreksi",
        "BUTTON_DUPLICATE_CANCEL": "Batal",
        "SELECTED_PREFIX": "✓",
        "SALES_SOURCES_SELECTED_EMPTY": "Belum ada sumber penjualan yang dipilih.",
        "SALES_SOURCES_SELECTED_HEADER": "Dipilih:",
        "STOCK_ISSUE_SELECTED_EMPTY": "Belum ada yang dipilih.",
        "STOCK_ISSUE_SELECTED_HEADER": "Dipilih:",
        "SALES_SUMMARY_LINE": "{{source}} | traffic={{traffic}} | gmv={{gmv}} | order={{order_count}} | pieces={{pieces_sold}}",
        "SALES_NO_SALES_LABEL": "Tidak Ada Penjualan",
        "PROGRESS_MAIN_LABEL": "Langkah",
        "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
        "CONTEXTUAL_STEP_FORMAT": "{{label}} {{current}}/{{total}} · {{title}}",
        "PROGRESS_PHASE_STORE": "Pilih Toko",
        "PROGRESS_PHASE_SALES": "Sumber Penjualan",
        "PROGRESS_PHASE_STOCK_ISSUE": "Kendala Stok",
        "PROGRESS_PHASE_NOTE": "Catatan",
        "PROGRESS_PHASE_REVIEW_SUBMIT": "Review & Submit",
        "SALES_SOURCE_STEP_LABEL": "Sumber",
        "STORE_LABEL_FORMAT": "{{brand}} - {{department_store}} {{branch}}, {{city}}",
        "DISTANCE_METER_FORMAT": "{{distance}} m",
        "DISTANCE_EMPTY": "-",
        "LOCATION_STATUS_IN_RADIUS": "Dalam radius",
        "LOCATION_STATUS_OUT_OF_RADIUS": "Di luar radius",
        "LOCATION_STATUS_MANUAL_STORE_SELECTION": "Pilih toko manual",
    }


def _source(
    source_id: str,
    label: str,
    requires_traffic: bool = False,
    sort_order: int = 2,
    status: str = "Aktif",
) -> GmvSource:
    return GmvSource(
        gmv_source_id=source_id,
        label=label,
        source_type="outlet" if requires_traffic else "marketplace",
        requires_traffic=requires_traffic,
        sort_order=sort_order,
        status=status,
    )


def _stock_issue(
    stock_issue_id: str,
    label: str,
    sort_order: int = 1,
    status: str = "Aktif",
) -> StockIssue:
    return StockIssue(
        stock_issue_id=stock_issue_id,
        label=label,
        sort_order=sort_order,
        status=status,
    )


def _store() -> StoreLocation:
    return StoreLocation(
        store_id="S001",
        department_store="Mall",
        branch="Utama",
        city="Jakarta",
        brand="VIZU",
        latitude=-6.2,
        longitude=106.8,
        allowed_radius_meter=100,
        status="Aktif",
        notes=None,
    )


def _sales_row(label: str, requires_traffic: bool, **values: int) -> dict[str, Any]:
    return {
        "label": label,
        "source_type": "outlet" if requires_traffic else "marketplace",
        "requires_traffic": requires_traffic,
        "sort_order": 1 if requires_traffic else 3,
        **values,
    }


def _sales_draft(
    source_ids: list[str],
    sales_data: dict[str, dict[str, Any]],
    plan: list[list[str]] | None = None,
) -> dict[str, Any]:
    draft = {
        "user_name": "Ani",
        "sales_source_ids": source_ids,
        "sales_data": sales_data,
        "sales_no_sales": False,
    }
    if plan is not None:
        draft["sales_input_plan"] = plan
        draft["sales_input_pos"] = 0
    return draft


def _complete_sales_draft() -> dict[str, Any]:
    return _sales_draft(
        ["outlet", "shopee"],
        {
            "outlet": _sales_row(
                "Outlet",
                True,
                traffic=10,
                gmv=100000,
                order_count=2,
                pieces_sold=3,
                sort_order=1,
            ),
            "shopee": _sales_row(
                "Shopee Snapshot",
                False,
                gmv=200000,
                order_count=4,
                pieces_sold=5,
                sort_order=3,
            ),
        },
    )


def _text_update(chat: "_FakeChat", text: str) -> "_FakeUpdate":
    return _FakeUpdate(chat=chat, message=SimpleNamespace(text=text, location=None), callback_query=None)


def _callback_update(chat: "_FakeChat", data: str) -> "_FakeUpdate":
    return _FakeUpdate(
        chat=chat,
        message=None,
        callback_query=_FakeCallbackQuery(chat, data),
    )


class _FakeTemplatesRepository:
    def __init__(self, templates: dict[str, str]) -> None:
        self._templates = templates

    async def list_all(self) -> dict[str, str]:
        return self._templates


class _FakeStores:
    def __init__(self, stores: list[StoreLocation]) -> None:
        self._stores = {store.store_id: store for store in stores}

    async def get_by_id(self, store_id: str) -> StoreLocation | None:
        return self._stores.get(store_id)


class _FakeSalesSources:
    def __init__(self, sources: list[GmvSource]) -> None:
        self._sources = sources

    async def list_active(self, active_status: str) -> list[GmvSource]:
        return [source for source in self._sources if source.status == active_status]


class _FakeStockIssues:
    def __init__(self, issues: list[StockIssue]) -> None:
        self._issues = issues

    async def list_active(self, active_status: str) -> list[StockIssue]:
        return [issue for issue in self._issues if issue.status == active_status]


class _FakeReports:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    async def exists_for_store_date(self, store_id: str, report_date: datetime) -> bool:
        return False

    async def report_id_exists(self, report_id: str) -> bool:
        return False

    async def create(self, report: dict[str, Any], sales_rows: list[dict[str, Any]]) -> None:
        self.created.append({"report": report, "sales_rows": sales_rows})


class _FakeSessions:
    def __init__(self, step: Step, draft: dict[str, Any]) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.deleted_chat_ids: list[int] = []
        self.session: dict[str, Any] = {
            "current_step": step.value,
            "draft_report": draft,
            "selected_store_id": "S001",
            "user_id": "U001",
            "expires_at": datetime.now(UTC) + timedelta(minutes=30),
        }

    async def get(self, telegram_chat_id: int) -> dict[str, Any] | None:
        return self.session if self.session else None

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
        self.answered = False

    async def answer(self) -> None:
        self.answered = True

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


class _FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    async def send_message(self, **message: Any) -> None:
        self.sent_messages.append(message)

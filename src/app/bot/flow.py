from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.bot.keyboards import (
    activation_contact_keyboard,
    admin_menu_keyboard,
    confirm_keyboard,
    confirm_store_keyboard,
    duplicate_keyboard,
    management_detail_keyboard,
    management_edit_menu_keyboard,
    management_list_keyboard,
    management_menu_keyboard,
    manual_store_list_keyboard,
    none_reply_keyboard,
    retry_location_keyboard,
    sales_edit_menu_keyboard,
    sales_input_navigation_keyboard,
    sales_source_keyboard,
    sales_summary_keyboard,
    start_again_keyboard,
    stock_issue_keyboard,
    start_location_keyboard,
    store_list_keyboard,
    super_admin_menu_keyboard,
    summary_keyboard,
    user_form_navigation_keyboard,
    user_form_review_keyboard,
)
from app.bot.management_scope import (
    SCOPE_ADMINS,
    SCOPE_USERS,
    ManagementScope,
    scope_from_callback,
    scope_from_draft,
)
from app.bot.notifications import send_admin_notification
from app.bot.progress import contextual_step_progress, progress_for_step
from app.bot.sales_text import (
    selected_sources_text,
    sales_summary_text,
    source_input_count,
    source_input_position,
)
from app.bot.stock_issue_text import (
    current_detail_position,
    current_sku_values,
    detail_instruction_text,
    merge_sku_values,
    next_detail_option_id,
    parse_sku_values,
    selected_issue_text,
    sku_list_text,
)
from app.bot.user_admin_text import (
    user_detail_tokens,
    user_field_button_labels,
    user_field_prompt_key,
    user_form_review_tokens,
    user_list_button_labels,
)
from app.config import Settings
from app.domain.activation import (
    ActivationOutcome,
    decide_activation,
    match_active_users_by_phone,
)
from app.domain.geo import haversine_meters
from app.domain.report import build_summary, generate_report_id, location_status
from app.domain.roles import (
    Role,
    can_manage_admins,
    can_manage_stores,
    can_manage_users,
    menu_step_for_role,
    normalize_role,
)
from app.domain.sales_sources import GmvSource, input_plan, source_fields
from app.domain.session_state import Step, next_step
from app.domain.stock_issues import StockIssue
from app.domain.store_matching import MatchType, StoreCandidate, StoreLocation, match_stores
from app.domain.user_management import (
    OPTIONAL_FIELDS,
    USER_FORM_FIELDS,
    generate_user_id,
    is_duplicate_phone,
    validate_field,
)
from app.domain.validation import normalize_text_dash, parse_int_lenient
from app.repositories.reports import ReportsRepository
from app.repositories.sales_sources import SalesSourcesRepository
from app.repositories.sessions import SessionsRepository
from app.repositories.stock_issues import StockIssuesRepository
from app.repositories.stores import StoresRepository
from app.repositories.templates import TemplatesRepository
from app.repositories.users import UsersRepository
from app.templates import MessageTemplates


TEXT_STEPS: dict[Step, str] = {
    Step.ASK_NOTE: "note",
}

SALES_FIELD_TEMPLATE_KEYS = {
    "traffic": "ASK_SALES_TRAFFIC",
    "gmv": "ASK_SALES_GMV",
    "order_count": "ASK_SALES_ORDER",
    "pieces_sold": "ASK_SALES_PIECES",
}

MANAGEMENT_CALLBACK_STEPS = {
    Step.MANAGE_USERS_MENU,
    Step.MANAGE_ADMINS_MENU,
    Step.USER_LIST,
    Step.USER_DETAIL,
    Step.USER_EDIT_MENU,
    Step.USER_CONFIRM_STATUS,
    Step.USER_CONFIRM_RESET_LINK,
}

class ReportFlow:
    def __init__(
        self,
        settings: Settings,
        templates: MessageTemplates,
        templates_repository: TemplatesRepository,
        stores: StoresRepository,
        sales_sources: SalesSourcesRepository,
        stock_issues: StockIssuesRepository,
        users: UsersRepository,
        reports: ReportsRepository,
        sessions: SessionsRepository,
    ) -> None:
        self._settings = settings
        self._templates = templates
        self._templates_repository = templates_repository
        self._stores = stores
        self._sales_sources = sales_sources
        self._stock_issues = stock_issues
        self._users = users
        self._reports = reports
        self._sessions = sessions

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private(update):
            return
        await self._sessions.delete(update.effective_chat.id)
        users = await self._users.find_active_by_telegram_user_id(
            update.effective_user.id,
            self._settings.active_status,
        )
        if len(users) == 1:
            await self._route_after_auth(update, users[0])
            return

        await self._persist(update, Step.AWAITING_PHONE, {})
        await self._send_activation_contact_prompt(update)

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private(update):
            return
        await self._cancel(update)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private(update):
            return

        text = _message_text(update)
        if text is not None and await self._is_start_answer(text):
            await self.handle_start(update, context)
            return

        session = await self._load_session_or_notify(update)
        if session is None:
            return

        step = Step(session["current_step"])
        if step == Step.AWAITING_PHONE:
            await self._handle_phone_contact(update, session)
        elif step == Step.AWAITING_LOCATION:
            await self._handle_location(update, session)
        elif step == Step.MANUAL_STORE_SELECTION and _message_has_location(update):
            await self._handle_location(update, session, allow_manual_store_selection=False)
        elif step == Step.ASK_SALES_SOURCES:
            await self._send_sales_sources_prompt(update, dict(session["draft_report"]))
        elif step == Step.ASK_SALES_INPUT:
            await self._handle_sales_input(update, session)
        elif step == Step.REVIEW_SALES_SUMMARY:
            await self._handle_sales_summary_text(update, session)
        elif step == Step.ASK_STOCK_ISSUE:
            await self._handle_stock_issue_text(update, session)
        elif step == Step.USER_FORM_INPUT:
            scope = scope_from_draft(dict(session["draft_report"]))
            if scope is None:
                await self._send(update, "UNKNOWN_COMMAND")
                return
            await self._handle_user_form_input_text(update, session, scope)
        elif step == Step.USER_FORM_REVIEW:
            scope = scope_from_draft(dict(session["draft_report"]))
            if scope is None:
                await self._send(update, "UNKNOWN_COMMAND")
                return
            await self._handle_user_form_review_text(update, session, scope)
        elif step in TEXT_STEPS:
            await self._handle_text(update, session, step)
        else:
            await self._send(update, "UNKNOWN_COMMAND")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.callback_query is not None:
            await update.callback_query.answer()

        if not await self._ensure_private(update):
            return

        session = await self._load_session_or_notify(update)
        if session is None:
            return

        data = update.callback_query.data if update.callback_query else ""
        step = Step(session["current_step"])

        if step == Step.CONFIRM_STORE and data == "confirm_store:yes":
            draft = dict(session["draft_report"])
            store_id = draft["proposed_store_id"]
            await self._select_store(update, session, store_id)
        elif step == Step.CONFIRM_STORE and data == "confirm_store:no":
            await self._show_manual_store_selection(update, session)
        elif step == Step.CHOOSE_STORE and data == "manual:stores":
            await self._show_manual_store_selection(update, session)
        elif step in {Step.CHOOSE_STORE, Step.MANUAL_STORE_SELECTION} and data.startswith("store:"):
            await self._select_store(update, session, data.removeprefix("store:"))
        elif step == Step.ASK_SALES_SOURCES and data.startswith("sales_source:"):
            await self._handle_sales_sources_callback(update, session, data)
        elif step == Step.EDIT_SALES_MENU and data.startswith("sales_edit:"):
            await self._handle_sales_edit_callback(update, session, data)
        elif step == Step.ASK_STOCK_ISSUE and data.startswith("stock_issue:"):
            await self._handle_stock_issue_callback(update, session, data)
        elif step == Step.REVIEW_SUMMARY and data == "summary:submit":
            await self._handle_submit(update, context, session)
        elif step == Step.REVIEW_SUMMARY and data == "summary:restart":
            await self.handle_start(update, context)
        elif step == Step.REVIEW_SUMMARY and data == "summary:cancel":
            await self._cancel(update)
        elif step == Step.CONFIRM_DUPLICATE and data == "duplicate:yes":
            await self._save_and_complete(update, context, session, "correction")
        elif step == Step.CONFIRM_DUPLICATE and data == "duplicate:cancel":
            await self._cancel(update)
        elif step == Step.ADMIN_MENU:
            await self._handle_admin_menu_callback(update, session, data)
        elif step == Step.SUPER_ADMIN_MENU:
            await self._handle_super_admin_menu_callback(update, session, data)
        elif step in MANAGEMENT_CALLBACK_STEPS and data.startswith(("users:", "admins:")):
            await self._handle_management_callback(update, session, data)
        else:
            await self._send(update, "UNKNOWN_COMMAND")

    async def _route_after_auth(self, update: Update, user: dict[str, Any]) -> None:
        role = normalize_role(user.get("role"))
        step = menu_step_for_role(role)
        if step is None:
            await self._start_report_flow(update, user)
            return

        await self._persist(update, step, {"user_name": user["name"]}, user_id=user["user_id"])
        await self._send_menu(update, step)

    async def _start_report_flow(self, update: Update, user: dict[str, Any]) -> None:
        await self._persist(
            update,
            Step.AWAITING_LOCATION,
            {"user_name": user["name"]},
            user_id=user["user_id"],
        )
        await self._send(
            update,
            "START",
            manual_store_button=await self._manual_store_button_label(),
            reply_markup=await self._start_location_keyboard(),
            progress_step=Step.AWAITING_LOCATION,
        )

    async def _handle_phone_contact(self, update: Update, session: dict[str, Any]) -> None:
        if update.message is None or update.message.contact is None:
            await self._send_activation_contact_prompt(update)
            return

        contact = update.message.contact
        if contact.user_id != update.effective_user.id:
            await self._send(
                update,
                "ACTIVATION_NOT_OWN_CONTACT",
                reply_markup=await self._activation_contact_keyboard(),
            )
            return

        active_users = await self._users.list_active(self._settings.active_status)
        matches = match_active_users_by_phone(active_users, contact.phone_number)
        result = decide_activation(update.effective_user.id, matches)

        if result.outcome == ActivationOutcome.ACTIVATED and result.user is not None:
            await self._users.bind_telegram(
                result.user["user_id"],
                update.effective_user.id,
                update.effective_chat.id,
            )
            await self._send(
                update,
                "ACTIVATION_SUCCESS",
                user_name=result.user["name"],
            )
            await self._route_after_auth(update, result.user)
            return

        if result.outcome == ActivationOutcome.ALREADY_LINKED and result.user is not None:
            await self._route_after_auth(update, result.user)
            return

        await self._send(
            update,
            "ACTIVATION_FAILED",
            reply_markup=await self._activation_contact_keyboard(),
        )

    async def _handle_location(
        self,
        update: Update,
        session: dict[str, Any],
        allow_manual_store_selection: bool = True,
    ) -> None:
        text = _message_text(update)
        if allow_manual_store_selection and text is not None and await self._is_manual_store_answer(text):
            await self._show_manual_store_selection(update, session)
            return

        if update.message is None or update.message.location is None:
            await self._send(
                update,
                "ASK_LOCATION",
                manual_store_button=await self._manual_store_button_label(),
                reply_markup=await self._start_location_keyboard(),
                progress_step=Step.AWAITING_LOCATION,
            )
            return

        location = update.message.location
        stores = await self._stores.list_active(self._settings.active_status)
        match = match_stores(
            location.latitude,
            location.longitude,
            stores,
            default_radius_meter=self._settings.default_radius_meter,
            active_status=self._settings.active_status,
        )
        draft = {
            "submitted_latitude": location.latitude,
            "submitted_longitude": location.longitude,
            "candidate_distances": _candidate_distances(match.candidates),
        }

        if match.match_type == MatchType.SINGLE:
            candidate = match.candidates[0]
            draft["proposed_store_id"] = candidate.store.store_id
            await self._persist(update, Step.CONFIRM_STORE, draft, user_id=session["user_id"])
            await self._send(
                update,
                "STORE_CONFIRMATION",
                store_label=await self._store_label(candidate.store),
                distance_meter=await self._distance_meter(candidate.distance_meter),
                reply_markup=await self._confirm_store_keyboard(),
                progress_step=Step.CONFIRM_STORE,
            )
            return

        if match.match_type == MatchType.MULTIPLE:
            await self._refresh_templates()
            await self._persist(update, Step.CHOOSE_STORE, draft, user_id=session["user_id"])
            await self._send(
                update,
                "MULTIPLE_STORES_FOUND",
                area_label=self._area_label(match.candidates),
                reply_markup=store_list_keyboard(
                    match.candidates,
                    await self._candidate_button_labels(match.candidates),
                    other_store_label=self._templates.render("BUTTON_OTHER_STORE"),
                ),
                progress_step=Step.CHOOSE_STORE,
            )
            return

        await self._persist(update, Step.MANUAL_STORE_SELECTION, draft, user_id=session["user_id"])
        reply_markup = manual_store_list_keyboard(
            [candidate.store for candidate in match.candidates],
            await self._store_labels([candidate.store for candidate in match.candidates]),
        )
        await self._send(
            update,
            "LOCATION_NOT_FOUND",
            reply_markup=reply_markup,
            progress_step=Step.MANUAL_STORE_SELECTION,
        )

    async def _handle_sales_sources_callback(self, update: Update, session: dict[str, Any], data: str) -> None:
        draft = dict(session["draft_report"])
        sources = await self._active_sales_sources()

        if data.startswith("sales_source:toggle:"):
            source_id = data.removeprefix("sales_source:toggle:")
            source_ids_by_order = [source.gmv_source_id for source in sources]
            if source_id not in source_ids_by_order:
                await self._send(update, "UNKNOWN_COMMAND")
                return

            selected_ids = set(draft.get("sales_source_ids", []))
            if source_id in selected_ids:
                selected_ids.remove(source_id)
            else:
                selected_ids.add(source_id)
            draft["sales_source_ids"] = [source_id for source_id in source_ids_by_order if source_id in selected_ids]
            draft["sales_no_sales"] = False
            await self._persist_sales_step(update, Step.ASK_SALES_SOURCES, session, draft)
            await self._edit_sales_sources_prompt(update, draft)
            return

        if data == "sales_source:no_sales":
            draft["sales_no_sales"] = True
            draft.pop("sales_source_ids", None)
            draft.pop("sales_data", None)
            draft.pop("sales_input_plan", None)
            draft.pop("sales_input_pos", None)
            draft.pop("sales_return_to_summary", None)
            await self._remove_callback_keyboard(update)
            await self._persist_sales_step(update, Step.ASK_STOCK_ISSUE, session, draft)
            await self._send_step_prompt(update, Step.ASK_STOCK_ISSUE)
            return

        if data == "sales_source:done":
            if not draft.get("sales_source_ids"):
                await self._edit_sales_sources_prompt(update, draft)
                return
            await self._start_sales_input(update, session, draft, sources)
            return

        await self._send(update, "UNKNOWN_COMMAND")

    async def _handle_sales_input(self, update: Update, session: dict[str, Any]) -> None:
        text = _message_text(update)
        if text is None:
            await self._send_sales_input_prompt(update, dict(session["draft_report"]))
            return

        text = text.strip()
        if await self._is_previous_answer(text):
            await self._handle_sales_input_previous(update, session)
            return
        if await self._is_cancel_answer(text):
            await self._cancel(update)
            return

        try:
            value = parse_int_lenient(text)
        except ValueError:
            await self._send_sales_input_prompt(update, dict(session["draft_report"]))
            return

        draft = dict(session["draft_report"])
        source_id, field = self._current_sales_input(draft)
        sales_data = dict(draft.get("sales_data", {}))
        current_source_data = dict(sales_data[source_id])
        current_source_data[field] = value
        sales_data[source_id] = current_source_data
        draft["sales_data"] = sales_data
        draft["sales_input_pos"] = int(draft.get("sales_input_pos", 0)) + 1

        if draft["sales_input_pos"] >= len(draft.get("sales_input_plan", [])):
            draft.pop("sales_input_plan", None)
            draft.pop("sales_input_pos", None)
            draft.pop("sales_return_to_summary", None)
            draft.pop("sales_input_back_step", None)
            await self._persist_sales_step(update, Step.REVIEW_SALES_SUMMARY, session, draft)
            await self._send_sales_summary(update, draft)
            return

        await self._persist_sales_step(update, Step.ASK_SALES_INPUT, session, draft)
        await self._send_sales_input_prompt(update, draft)

    async def _handle_sales_input_previous(self, update: Update, session: dict[str, Any]) -> None:
        draft = dict(session["draft_report"])
        pos = int(draft.get("sales_input_pos", 0))
        if pos > 0:
            draft["sales_input_pos"] = pos - 1
            await self._persist_sales_step(update, Step.ASK_SALES_INPUT, session, draft)
            await self._send_sales_input_prompt(update, draft)
            return

        back_step = draft.get("sales_input_back_step")
        draft.pop("sales_input_plan", None)
        draft.pop("sales_input_pos", None)
        draft.pop("sales_input_back_step", None)
        if back_step == Step.EDIT_SALES_MENU.value:
            await self._persist_sales_step(update, Step.EDIT_SALES_MENU, session, draft)
            await self._send_sales_edit_menu(update, draft)
            return

        await self._persist_sales_step(update, Step.ASK_SALES_SOURCES, session, draft)
        await self._send_sales_sources_prompt(update, draft)

    async def _handle_sales_summary_text(self, update: Update, session: dict[str, Any]) -> None:
        text = _message_text(update)
        if text is None:
            await self._send_sales_summary(update, dict(session["draft_report"]))
            return

        await self._refresh_templates()
        answer = text.strip().casefold()
        if answer == self._templates.render("BUTTON_SALES_CONTINUE").casefold():
            await self._persist_sales_step(
                update,
                Step.ASK_STOCK_ISSUE,
                session,
                dict(session["draft_report"]),
            )
            await self._send_step_prompt(update, Step.ASK_STOCK_ISSUE)
            return

        if answer == self._templates.render("BUTTON_SALES_EDIT").casefold():
            await self._persist_sales_step(
                update,
                Step.EDIT_SALES_MENU,
                session,
                dict(session["draft_report"]),
            )
            await self._send_sales_edit_menu(update, dict(session["draft_report"]))
            return

        if answer == self._templates.render("BUTTON_CANCEL").casefold():
            await self._cancel(update)
            return

        await self._send_sales_summary(update, dict(session["draft_report"]))

    async def _handle_sales_edit_callback(self, update: Update, session: dict[str, Any], data: str) -> None:
        draft = dict(session["draft_report"])
        sales_data = dict(draft.get("sales_data", {}))

        if data.startswith("sales_edit:source:"):
            source_id = data.removeprefix("sales_edit:source:")
            if source_id not in sales_data:
                await self._send(update, "UNKNOWN_COMMAND")
                return
            draft["sales_input_plan"] = [
                [source_id, field]
                for field in source_fields(bool(sales_data[source_id]["requires_traffic"]))
            ]
            draft["sales_input_pos"] = 0
            draft["sales_return_to_summary"] = True
            draft["sales_input_back_step"] = Step.EDIT_SALES_MENU.value
            await self._persist_sales_step(update, Step.ASK_SALES_INPUT, session, draft)
            await self._send_sales_input_prompt(update, draft)
            return

        if data == "sales_edit:sources":
            draft["sales_return_to_summary"] = True
            await self._persist_sales_step(update, Step.ASK_SALES_SOURCES, session, draft)
            await self._send_sales_sources_prompt(update, draft)
            return

        if data == "sales_edit:back":
            await self._persist_sales_step(update, Step.REVIEW_SALES_SUMMARY, session, draft)
            await self._send_sales_summary(update, draft)
            return

        await self._send(update, "UNKNOWN_COMMAND")

    async def _handle_text(self, update: Update, session: dict[str, Any], step: Step) -> None:
        text = _message_text(update)
        if text is None:
            await self._send_step_prompt(update, step)
            return

        draft = dict(session["draft_report"])
        draft[TEXT_STEPS[step]] = "-" if await self._is_none_answer(text) else normalize_text_dash(text)
        following_step = next_step(step)
        await self._persist(
            update,
            following_step,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )

        if following_step == Step.REVIEW_SUMMARY:
            await self._send_summary(update, draft, session["selected_store_id"])
        else:
            await self._send_step_prompt(update, following_step)

    async def _handle_stock_issue_text(self, update: Update, session: dict[str, Any]) -> None:
        text = _message_text(update)
        draft = dict(session["draft_report"])
        if text is None:
            if draft.get("stock_issue_detail_option_id"):
                await self._send_stock_issue_detail_prompt(update, draft)
                return
            await self._send_stock_issue_prompt(update, draft)
            return

        if draft.get("stock_issue_detail_option_id"):
            text = text.strip()
            if await self._is_previous_answer(text):
                await self._handle_stock_issue_detail_previous(update, session, draft)
                return
            if await self._is_cancel_answer(text):
                await self._cancel(update)
                return
            if text == "-" or await self._is_none_answer(text):
                await self._advance_stock_issue_detail(update, session, draft)
                return
            await self._append_stock_issue_skus(update, session, draft, text)
            return

        await self._send_stock_issue_prompt(update, draft)

    async def _handle_stock_issue_callback(self, update: Update, session: dict[str, Any], data: str) -> None:
        draft = dict(session["draft_report"])

        if data.startswith("stock_issue:toggle:"):
            option_id = data.removeprefix("stock_issue:toggle:")
            stock_issues = await self._active_stock_issues()
            issue_by_id = {issue.stock_issue_id: issue for issue in stock_issues}
            if option_id not in issue_by_id:
                await self._send(update, "UNKNOWN_COMMAND")
                return

            selected_ids = set(draft.get("stock_issue_ids", []))
            if option_id in selected_ids:
                selected_ids.remove(option_id)
            else:
                selected_ids.add(option_id)
            ordered_ids = [issue.stock_issue_id for issue in stock_issues if issue.stock_issue_id in selected_ids]
            labels = dict(draft.get("stock_issue_labels", {}))
            for issue in stock_issues:
                if issue.stock_issue_id in ordered_ids and issue.stock_issue_id not in labels:
                    labels[issue.stock_issue_id] = issue.label
            details = dict(draft.get("stock_issue_sku_details", {}))
            draft["stock_issue_ids"] = ordered_ids
            draft["stock_issue_labels"] = {issue_id: labels[issue_id] for issue_id in ordered_ids if issue_id in labels}
            draft["stock_issue_sku_details"] = {
                issue_id: details[issue_id] for issue_id in ordered_ids if issue_id in details
            }
            draft.pop("stock_issue_detail_option_id", None)
            draft.pop("stock_issue_detail_option_ids", None)
            await self._persist(
                update,
                Step.ASK_STOCK_ISSUE,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._edit_stock_issue_prompt(update, draft)
            return

        if data == "stock_issue:continue":
            if not draft.get("stock_issue_ids"):
                await self._edit_stock_issue_prompt(update, draft)
                return
            await self._start_stock_issue_details(update, session, draft, await self._active_stock_issues())
            return

        if data == "stock_issue:none":
            if draft.get("stock_issue_ids"):
                await self._edit_stock_issue_prompt(update, draft)
                return
            await self._remove_callback_keyboard(update)
            await self._save_stock_issue_and_continue(update, session, "-")
            return

        await self._send(update, "UNKNOWN_COMMAND")

    async def _save_stock_issue_and_continue(
        self,
        update: Update,
        session: dict[str, Any],
        stock_issue: str,
    ) -> None:
        draft = dict(session["draft_report"])
        draft["stock_issue"] = stock_issue
        draft.pop("stock_issue_ids", None)
        draft.pop("stock_issue_labels", None)
        draft.pop("stock_issue_detail_option_ids", None)
        draft.pop("stock_issue_detail_option_id", None)
        draft.pop("stock_issue_sku_details", None)
        await self._persist(
            update,
            Step.ASK_NOTE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_step_prompt(update, Step.ASK_NOTE)

    async def _start_stock_issue_details(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
        stock_issues: list[StockIssue],
    ) -> None:
        selected_ids = [
            issue.stock_issue_id
            for issue in stock_issues
            if issue.stock_issue_id in set(draft.get("stock_issue_ids", []))
        ]
        if not selected_ids:
            draft["stock_issue_ids"] = []
            await self._persist(
                update,
                Step.ASK_STOCK_ISSUE,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._edit_stock_issue_prompt(update, draft)
            return

        issue_by_id = {issue.stock_issue_id: issue for issue in stock_issues}
        existing_labels = dict(draft.get("stock_issue_labels", {}))
        existing_details = dict(draft.get("stock_issue_sku_details", {}))
        labels = {
            issue_id: existing_labels.get(issue_id) or issue_by_id[issue_id].label
            for issue_id in selected_ids
        }
        details = {
            issue_id: list(existing_details[issue_id])
            for issue_id in selected_ids
            if issue_id in existing_details
        }
        missing_ids = [issue_id for issue_id in selected_ids if issue_id not in details]

        draft["stock_issue_ids"] = selected_ids
        draft["stock_issue_labels"] = labels
        draft["stock_issue_sku_details"] = details
        draft["stock_issue_detail_option_ids"] = selected_ids

        if not missing_ids:
            await self._remove_callback_keyboard(update)
            await self._save_stock_issue_and_continue(update, session, await self._stock_issue_value(draft))
            return

        draft["stock_issue_detail_option_id"] = missing_ids[0]
        await self._remove_callback_keyboard(update)
        await self._persist(
            update,
            Step.ASK_STOCK_ISSUE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_stock_issue_detail_prompt(update, draft)

    async def _handle_stock_issue_detail_previous(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
    ) -> None:
        detail_option_ids = list(draft.get("stock_issue_detail_option_ids", []))
        current_option_id = draft.get("stock_issue_detail_option_id")
        if current_option_id not in detail_option_ids:
            await self._send_stock_issue_prompt(update, draft)
            return

        current_index = detail_option_ids.index(current_option_id)
        if current_index > 0:
            draft["stock_issue_detail_option_id"] = detail_option_ids[current_index - 1]
            await self._persist(
                update,
                Step.ASK_STOCK_ISSUE,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._send_stock_issue_detail_prompt(update, draft)
            return

        draft.pop("stock_issue_detail_option_id", None)
        draft.pop("stock_issue_detail_option_ids", None)
        await self._persist(
            update,
            Step.ASK_STOCK_ISSUE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_stock_issue_prompt(update, draft)

    async def _append_stock_issue_skus(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
        text: str,
    ) -> None:
        current_option_id = draft["stock_issue_detail_option_id"]
        sku_values = parse_sku_values(text)
        if not sku_values:
            await self._send_stock_issue_detail_prompt(update, draft)
            return

        details = dict(draft.get("stock_issue_sku_details", {}))
        details[current_option_id] = merge_sku_values(list(details.get(current_option_id, [])), sku_values)
        draft["stock_issue_sku_details"] = details
        await self._advance_stock_issue_detail(update, session, draft)

    async def _advance_stock_issue_detail(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
    ) -> None:
        detail_option_ids = list(draft.get("stock_issue_detail_option_ids", []))
        current_option_id = draft.get("stock_issue_detail_option_id")
        next_option_id = next_detail_option_id(detail_option_ids, current_option_id)

        if next_option_id is None:
            stock_issue = await self._stock_issue_value(draft)
            await self._remove_callback_keyboard(update)
            await self._save_stock_issue_and_continue(update, session, stock_issue)
            return

        draft["stock_issue_detail_option_id"] = next_option_id
        await self._persist(
            update,
            Step.ASK_STOCK_ISSUE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_stock_issue_detail_prompt(update, draft)

    async def _handle_submit(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: dict[str, Any],
    ) -> None:
        report_date = self._now().date()
        exists = await self._reports.exists_for_store_date(session["selected_store_id"], report_date)
        if exists:
            await self._persist(
                update,
                Step.CONFIRM_DUPLICATE,
                dict(session["draft_report"]),
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._send(
                update,
                "REPORT_ALREADY_EXISTS",
                reply_markup=await self._duplicate_keyboard(),
                progress_step=Step.CONFIRM_DUPLICATE,
            )
            return

        await self._save_and_complete(update, context, session, "submitted")

    async def _save_and_complete(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: dict[str, Any],
        submission_status: str,
    ) -> None:
        now = self._now()
        draft = dict(session["draft_report"])
        distance = draft.get("distance_from_store_meter")
        if distance is not None:
            distance = float(distance)
        effective_radius = draft.get("effective_radius_meter")
        if effective_radius is not None:
            effective_radius = int(effective_radius)
        report = {
            "report_id": await self._new_report_id(now),
            "report_date": now.date(),
            "store_id": session["selected_store_id"],
            "user_id": session["user_id"],
            "stock_issue": draft["stock_issue"],
            "submitted_latitude": draft.get("submitted_latitude"),
            "submitted_longitude": draft.get("submitted_longitude"),
            "distance_from_store_meter": distance,
            "note": draft["note"],
            "submission_status": submission_status,
            "location_status": location_status(distance, effective_radius),
            "created_at": now,
        }
        sales_rows = self._sales_rows_from_draft(report["report_id"], draft)
        await self._reports.create(report, sales_rows)
        await self._sessions.delete(update.effective_chat.id)
        await self._send(update, "SUBMIT_SUCCESS", reply_markup=ReplyKeyboardRemove())

        store = await self._stores.get_by_id(session["selected_store_id"])
        if store is not None:
            notification_key = "ADMIN_NOTIFICATION_CORRECTION"
            if submission_status != "correction":
                notification_key = "ADMIN_NOTIFICATION"
            summary_tokens = await self._summary_tokens(draft, await self._store_label(store))
            message = await self._render_trusted(
                notification_key,
                {"sales_breakdown"},
                user_name=draft["user_name"],
                report_date=report["report_date"],
                distance_meter=await self._distance_meter(report["distance_from_store_meter"]),
                location_status=await self._location_status_label(report["location_status"]),
                **summary_tokens,
            )
            await send_admin_notification(
                context.bot,
                self._settings.admin_chat_id,
                message,
            )

    async def _select_store(self, update: Update, session: dict[str, Any], store_id: str) -> None:
        store = await self._stores.get_by_id(store_id)
        if store is None or store.status != self._settings.active_status:
            await self._send(update, "UNKNOWN_COMMAND")
            return

        draft = dict(session["draft_report"])
        candidate = draft.get("candidate_distances", {}).get(store_id)
        has_submitted_location = "submitted_latitude" in draft and "submitted_longitude" in draft
        if candidate is None:
            if has_submitted_location:
                if store.latitude is None or store.longitude is None:
                    await self._send(update, "UNKNOWN_COMMAND")
                    return
                distance = haversine_meters(
                    draft["submitted_latitude"],
                    draft["submitted_longitude"],
                    store.latitude,
                    store.longitude,
                )
                effective_radius = store.allowed_radius_meter or self._settings.default_radius_meter
                if effective_radius <= 0:
                    effective_radius = self._settings.default_radius_meter
            else:
                distance = None
                effective_radius = None
        else:
            distance = float(candidate["distance_meter"])
            effective_radius = int(candidate["effective_radius_meter"])

        draft["distance_from_store_meter"] = distance
        draft["effective_radius_meter"] = effective_radius
        await self._persist(
            update,
            Step.ASK_SALES_SOURCES,
            draft,
            selected_store_id=store_id,
            user_id=session["user_id"],
        )
        await self._send_sales_sources_prompt(update, draft)

    async def _send_summary(self, update: Update, draft: dict[str, Any], selected_store_id: str) -> None:
        store = await self._stores.get_by_id(selected_store_id)
        if store is None:
            await self._send(update, "UNKNOWN_COMMAND")
            return
        tokens = await self._summary_tokens(draft, await self._store_label(store))
        await self._send_trusted(
            update,
            "REPORT_SUMMARY",
            {"sales_breakdown"},
            reply_markup=await self._summary_keyboard(),
            progress_step=Step.REVIEW_SUMMARY,
            **tokens,
        )

    async def _send_sales_sources_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        await self._send(
            update,
            "ASK_SALES_SOURCES",
            selected_sources=await self._sales_source_selected_text(draft),
            reply_markup=await self._sales_source_keyboard(draft),
            progress_step=Step.ASK_SALES_SOURCES,
        )

    async def _edit_sales_sources_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        if update.callback_query is None or update.callback_query.message is None:
            await self._send_sales_sources_prompt(update, draft)
            return
        try:
            await update.callback_query.edit_message_text(
                text=await self._render(
                    "ASK_SALES_SOURCES",
                    progress_step=Step.ASK_SALES_SOURCES,
                    selected_sources=await self._sales_source_selected_text(draft),
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=await self._sales_source_keyboard(draft),
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    async def _start_sales_input(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
        sources: list[GmvSource],
    ) -> None:
        source_by_id = {source.gmv_source_id: source for source in sources}
        selected_ids = [
            source.gmv_source_id
            for source in sources
            if source.gmv_source_id in set(draft.get("sales_source_ids", []))
        ]
        if not selected_ids:
            draft["sales_source_ids"] = []
            await self._persist_sales_step(update, Step.ASK_SALES_SOURCES, session, draft)
            await self._edit_sales_sources_prompt(update, draft)
            return

        existing_sales_data = dict(draft.get("sales_data", {}))
        sales_data: dict[str, dict[str, Any]] = {}
        for source_id in selected_ids:
            source = source_by_id[source_id]
            current = dict(existing_sales_data.get(source_id, {}))
            current.setdefault("label", source.label)
            current.setdefault("source_type", source.source_type)
            current.setdefault("requires_traffic", source.requires_traffic)
            current.setdefault("sort_order", source.sort_order)
            sales_data[source_id] = current

        specs = [(source_id, bool(sales_data[source_id]["requires_traffic"])) for source_id in selected_ids]
        plan = [
            [source_id, field]
            for source_id, field in input_plan(specs)
            if field not in sales_data[source_id]
        ]

        draft["sales_no_sales"] = False
        draft["sales_source_ids"] = selected_ids
        draft["sales_data"] = sales_data
        if not plan:
            draft.pop("sales_input_plan", None)
            draft.pop("sales_input_pos", None)
            draft.pop("sales_return_to_summary", None)
            draft.pop("sales_input_back_step", None)
            await self._persist_sales_step(update, Step.REVIEW_SALES_SUMMARY, session, draft)
            await self._send_sales_summary(update, draft)
            return

        draft["sales_input_plan"] = plan
        draft["sales_input_pos"] = 0
        draft["sales_return_to_summary"] = bool(draft.get("sales_return_to_summary", False))
        draft["sales_input_back_step"] = Step.ASK_SALES_SOURCES.value
        await self._persist_sales_step(update, Step.ASK_SALES_INPUT, session, draft)
        await self._send_sales_input_prompt(update, draft)

    async def _send_sales_input_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        source_id, field = self._current_sales_input(draft)
        source_data = dict(draft["sales_data"][source_id])
        source_ids = list(draft["sales_source_ids"])
        await self._refresh_templates()
        source_progress = contextual_step_progress(
            self._templates,
            "SALES_SOURCE_STEP_LABEL",
            source_input_position(source_ids, source_id),
            source_input_count(source_ids),
            source_data["label"],
        )
        await self._send(
            update,
            SALES_FIELD_TEMPLATE_KEYS[field],
            source=source_data["label"],
            source_progress=source_progress,
            reply_markup=await self._sales_input_navigation_keyboard(),
            progress_step=Step.ASK_SALES_INPUT,
        )

    async def _send_sales_summary(self, update: Update, draft: dict[str, Any]) -> None:
        await self._send_trusted(
            update,
            "SALES_SUMMARY",
            {"sales_breakdown"},
            reply_markup=await self._sales_summary_keyboard(),
            progress_step=Step.REVIEW_SALES_SUMMARY,
            **await self._sales_summary_tokens(draft),
        )

    async def _send_sales_edit_menu(self, update: Update, draft: dict[str, Any]) -> None:
        await self._send(
            update,
            "EDIT_SALES_MENU",
            reply_markup=await self._sales_edit_menu_keyboard(draft),
            progress_step=Step.EDIT_SALES_MENU,
        )

    async def _send_menu(self, update: Update, step: Step, edit: bool = False) -> None:
        if step == Step.ADMIN_MENU:
            if edit:
                await self._send_or_edit(update, "MENU_ADMIN", reply_markup=await self._admin_menu_keyboard())
            else:
                await self._send(update, "MENU_ADMIN", reply_markup=await self._admin_menu_keyboard())
            return
        if step == Step.SUPER_ADMIN_MENU:
            if edit:
                await self._send_or_edit(
                    update,
                    "MENU_SUPER_ADMIN",
                    reply_markup=await self._super_admin_menu_keyboard(),
                )
            else:
                await self._send(update, "MENU_SUPER_ADMIN", reply_markup=await self._super_admin_menu_keyboard())
            return
        await self._send(update, "UNKNOWN_COMMAND")

    async def _current_actor(self, update: Update) -> dict[str, Any] | None:
        users = await self._users.find_active_by_telegram_user_id(
            update.effective_user.id,
            self._settings.active_status,
        )
        if len(users) != 1:
            return None
        return users[0]

    async def _handle_admin_menu_callback(
        self,
        update: Update,
        session: dict[str, Any],
        data: str,
    ) -> None:
        actor = await self._current_actor(update)
        if actor is None:
            await self._send(update, "MENU_ACCESS_DENIED")
            return

        role = normalize_role(actor.get("role"))
        if data == "menu:report":
            await self._start_report_flow(update, actor)
            return
        if data == "menu:users":
            if not can_manage_users(role):
                await self._send(update, "MENU_ACCESS_DENIED")
                return
            await self._open_management_menu(update, actor, SCOPE_USERS)
            return
        if data == "menu:admins":
            await self._send(update, "MENU_ACCESS_DENIED")
            return

        await self._send(update, "UNKNOWN_COMMAND")

    async def _handle_super_admin_menu_callback(
        self,
        update: Update,
        session: dict[str, Any],
        data: str,
    ) -> None:
        actor = await self._current_actor(update)
        if actor is None:
            await self._send(update, "MENU_ACCESS_DENIED")
            return

        role = normalize_role(actor.get("role"))
        if data == "menu:report":
            await self._start_report_flow(update, actor)
            return
        if data == "menu:users":
            if not can_manage_users(role):
                await self._send(update, "MENU_ACCESS_DENIED")
                return
            await self._open_management_menu(update, actor, SCOPE_USERS)
            return
        if data == "menu:admins":
            if not can_manage_admins(role):
                await self._send(update, "MENU_ACCESS_DENIED")
                return
            await self._open_management_menu(update, actor, SCOPE_ADMINS)
            return
        if data == "menu:stores":
            if not can_manage_stores(role):
                await self._send(update, "MENU_ACCESS_DENIED")
                return
            await self._send(update, "MENU_PLACEHOLDER")
            return

        await self._send(update, "UNKNOWN_COMMAND")

    async def _authorize_management(self, update: Update, scope: ManagementScope) -> dict[str, Any] | None:
        actor = await self._current_actor(update)
        if actor is None or not scope.can_manage(normalize_role(actor.get("role"))):
            await self._send(update, "MENU_ACCESS_DENIED")
            return None
        return actor

    async def _load_management_target(
        self,
        update: Update,
        scope: ManagementScope,
        actor: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any] | None:
        target = await self._users.get_by_id(user_id)
        if (
            target is None
            or normalize_role(target.get("role")) != scope.managed_role
            or (scope.block_self and target["user_id"] == actor["user_id"])
        ):
            await self._send(update, "MENU_ACCESS_DENIED")
            return None
        return target

    async def _ensure_management_form_target_allowed(
        self,
        update: Update,
        scope: ManagementScope,
        actor: dict[str, Any],
        form: dict[str, Any],
    ) -> bool:
        if form.get("mode") != "edit":
            return True
        return await self._load_management_target(update, scope, actor, str(form.get("target_id", ""))) is not None

    async def _handle_management_callback(
        self,
        update: Update,
        session: dict[str, Any],
        data: str,
    ) -> None:
        scope = scope_from_callback(data)
        if scope is None:
            await self._send(update, "UNKNOWN_COMMAND")
            return

        actor = await self._authorize_management(update, scope)
        if actor is None:
            return

        if data == f"{scope.name}:add":
            await self._start_management_add_form(update, actor, scope)
            return
        if data == f"{scope.name}:list":
            await self._open_management_list(update, actor, scope)
            return
        if data.startswith(f"{scope.name}:view:"):
            await self._open_management_detail(update, actor, scope, data.removeprefix(f"{scope.name}:view:"))
            return
        if data.startswith(f"{scope.name}:edit:"):
            await self._open_management_edit_menu(update, actor, scope, data.removeprefix(f"{scope.name}:edit:"))
            return
        if data.startswith(f"{scope.name}:field:"):
            await self._start_management_field_input(
                update,
                actor,
                session,
                scope,
                data.removeprefix(f"{scope.name}:field:"),
            )
            return
        if data.startswith(f"{scope.name}:deactivate:"):
            await self._open_management_status_confirmation(
                update,
                actor,
                scope,
                data.removeprefix(f"{scope.name}:deactivate:"),
                "deactivate",
            )
            return
        if data.startswith(f"{scope.name}:reactivate:"):
            await self._open_management_status_confirmation(
                update,
                actor,
                scope,
                data.removeprefix(f"{scope.name}:reactivate:"),
                "reactivate",
            )
            return
        if data == f"{scope.name}:confirm_status":
            await self._confirm_management_status(update, actor, session, scope)
            return
        if data.startswith(f"{scope.name}:reset_link:"):
            await self._open_management_reset_link_confirmation(
                update,
                actor,
                scope,
                data.removeprefix(f"{scope.name}:reset_link:"),
            )
            return
        if data == f"{scope.name}:confirm_reset":
            await self._confirm_management_reset_link(update, actor, session, scope)
            return
        if data == f"{scope.name}:back:menu":
            if Step(session["current_step"]) == scope.root_step:
                await self._return_to_actor_menu(update, actor)
                return
            await self._open_management_menu(update, actor, scope)
            return
        if data == f"{scope.name}:back:list":
            await self._open_management_list(update, actor, scope)
            return
        if data == f"{scope.name}:back:detail":
            await self._handle_management_back_to_detail(update, actor, session, scope)
            return

        await self._send(update, "UNKNOWN_COMMAND")

    async def _open_management_menu(
        self,
        update: Update,
        actor: dict[str, Any],
        scope: ManagementScope,
        notice_key: str | None = None,
    ) -> None:
        await self._persist(
            update,
            scope.root_step,
            {"user_name": actor["name"], "mgmt_scope": scope.name},
            user_id=actor["user_id"],
        )
        await self._send_management_menu(update, scope, notice_key)

    async def _return_to_actor_menu(self, update: Update, actor: dict[str, Any]) -> None:
        step = menu_step_for_role(normalize_role(actor.get("role")))
        if step is None:
            await self._start_report_flow(update, actor)
            return
        await self._persist(update, step, {"user_name": actor["name"]}, user_id=actor["user_id"])
        await self._send_menu(update, step, edit=True)

    async def _open_management_list(
        self,
        update: Update,
        actor: dict[str, Any],
        scope: ManagementScope,
        notice_key: str | None = None,
    ) -> None:
        await self._persist(
            update,
            Step.USER_LIST,
            {"user_name": actor["name"], "mgmt_scope": scope.name},
            user_id=actor["user_id"],
        )
        await self._send_management_list(update, scope, notice_key)

    async def _open_management_detail(
        self,
        update: Update,
        actor: dict[str, Any],
        scope: ManagementScope,
        target_id: str,
        notice_key: str | None = None,
    ) -> None:
        target = await self._load_management_target(update, scope, actor, target_id)
        if target is None:
            return

        await self._persist(
            update,
            Step.USER_DETAIL,
            {"user_name": actor["name"], "mgmt_scope": scope.name, "user_target_id": target["user_id"]},
            user_id=actor["user_id"],
        )
        await self._send_management_detail(update, scope, target, notice_key)

    async def _start_management_add_form(
        self,
        update: Update,
        actor: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        form = {
            "mode": "add",
            "fields": {},
            "plan": list(USER_FORM_FIELDS),
            "pos": 0,
        }
        await self._remove_callback_keyboard(update)
        await self._persist(
            update,
            Step.USER_FORM_INPUT,
            {"user_name": actor["name"], "mgmt_scope": scope.name, "user_form": form},
            user_id=actor["user_id"],
        )
        await self._send_management_form_prompt(update, form, scope)

    async def _open_management_edit_menu(
        self,
        update: Update,
        actor: dict[str, Any],
        scope: ManagementScope,
        target_id: str,
        back_to_review: bool = False,
    ) -> None:
        target = await self._load_management_target(update, scope, actor, target_id)
        if target is None:
            return
        form = {
            "mode": "edit",
            "target_id": target["user_id"],
            "fields": {
                "name": target["name"],
                "phone": target["phone"],
                "email": target["email"],
                "notes": target["notes"],
            },
            "edit_menu_back": "review" if back_to_review else "detail",
        }
        await self._persist(
            update,
            Step.USER_EDIT_MENU,
            {
                "user_name": actor["name"],
                "mgmt_scope": scope.name,
                "user_target_id": target["user_id"],
                "user_form": form,
            },
            user_id=actor["user_id"],
        )
        await self._send_management_edit_menu(update, scope)

    async def _start_management_field_input(
        self,
        update: Update,
        actor: dict[str, Any],
        session: dict[str, Any],
        scope: ManagementScope,
        field: str,
    ) -> None:
        if field not in USER_FORM_FIELDS:
            await self._send(update, "UNKNOWN_COMMAND")
            return

        draft = dict(session["draft_report"])
        form = dict(draft.get("user_form", {}))
        if not form:
            await self._send(update, "UNKNOWN_COMMAND")
            return
        if not await self._ensure_management_form_target_allowed(update, scope, actor, form):
            return
        form["plan"] = [field]
        form["pos"] = 0
        form["return_to"] = "review"
        draft["mgmt_scope"] = scope.name
        draft["user_form"] = form
        await self._remove_callback_keyboard(update)
        await self._persist(
            update,
            Step.USER_FORM_INPUT,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_management_form_prompt(update, form, scope)

    async def _handle_user_form_input_text(
        self,
        update: Update,
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        actor = await self._authorize_management(update, scope)
        if actor is None:
            return

        text = _message_text(update)
        if text is None:
            await self._send_management_form_prompt(update, dict(session["draft_report"]).get("user_form", {}), scope)
            return

        text = text.strip()
        if await self._is_cancel_answer(text):
            await self._cancel(update)
            return
        if await self._is_previous_answer(text):
            await self._handle_management_form_previous(update, actor, session, scope)
            return

        draft = dict(session["draft_report"])
        form = dict(draft.get("user_form", {}))
        plan = list(form.get("plan", []))
        pos = int(form.get("pos", 0))
        if not plan or pos >= len(plan):
            await self._send(update, "UNKNOWN_COMMAND")
            return
        if not await self._ensure_management_form_target_allowed(update, scope, actor, form):
            return

        field = str(plan[pos])
        raw_value = "-" if field in OPTIONAL_FIELDS and await self._is_skip_answer(text) else text
        result = validate_field(field, raw_value)
        if not result.ok:
            await self._send_management_form_prompt(update, form, scope, result.error_key)
            return

        if field == "phone":
            exclude_user_id = str(form["target_id"]) if form.get("mode") == "edit" else None
            if is_duplicate_phone(await self._users.list_all(), str(result.value), exclude_user_id):
                await self._send_management_form_prompt(update, form, scope, "USER_ERROR_PHONE_DUPLICATE")
                return

        fields = dict(form.get("fields", {}))
        fields[field] = result.value
        form["fields"] = fields
        pos += 1
        if pos >= len(plan):
            form.pop("plan", None)
            form.pop("pos", None)
            draft["mgmt_scope"] = scope.name
            draft["user_form"] = form
            await self._persist(
                update,
                Step.USER_FORM_REVIEW,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._send_management_form_review(update, form, scope)
            return

        form["pos"] = pos
        draft["mgmt_scope"] = scope.name
        draft["user_form"] = form
        await self._persist(
            update,
            Step.USER_FORM_INPUT,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_management_form_prompt(update, form, scope)

    async def _handle_management_form_previous(
        self,
        update: Update,
        actor: dict[str, Any],
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        draft = dict(session["draft_report"])
        form = dict(draft.get("user_form", {}))
        pos = int(form.get("pos", 0))
        if pos > 0:
            form["pos"] = pos - 1
            draft["mgmt_scope"] = scope.name
            draft["user_form"] = form
            await self._persist(
                update,
                Step.USER_FORM_INPUT,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._send_management_form_prompt(update, form, scope)
            return

        if form.get("mode") == "edit":
            await self._open_management_detail(update, actor, scope, str(form["target_id"]))
            return
        await self._open_management_menu(update, actor, scope)

    async def _handle_user_form_review_text(
        self,
        update: Update,
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        actor = await self._authorize_management(update, scope)
        if actor is None:
            return

        text = _message_text(update)
        if text is None:
            await self._send_management_form_review(update, dict(session["draft_report"]).get("user_form", {}), scope)
            return

        answer = text.strip().casefold()
        await self._refresh_templates()
        if answer == self._templates.render("BUTTON_SAVE").casefold():
            await self._save_management_form(update, actor, session, scope)
            return
        if answer == self._templates.render("BUTTON_EDIT").casefold():
            await self._open_management_review_edit_menu(update, actor, session, scope)
            return
        if answer == self._templates.render("BUTTON_CANCEL").casefold():
            await self._cancel(update)
            return

        await self._send_management_form_review(update, dict(session["draft_report"]).get("user_form", {}), scope)

    async def _open_management_review_edit_menu(
        self,
        update: Update,
        actor: dict[str, Any],
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        draft = dict(session["draft_report"])
        form = dict(draft.get("user_form", {}))
        if not form:
            await self._send(update, "UNKNOWN_COMMAND")
            return
        if not await self._ensure_management_form_target_allowed(update, scope, actor, form):
            return
        form["edit_menu_back"] = "review"
        draft["mgmt_scope"] = scope.name
        draft["user_form"] = form
        await self._persist(
            update,
            Step.USER_EDIT_MENU,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_management_edit_menu(update, scope)

    async def _save_management_form(
        self,
        update: Update,
        actor: dict[str, Any],
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        form = dict(dict(session["draft_report"]).get("user_form", {}))
        fields = dict(form.get("fields", {}))
        validation_error = await self._validate_user_form_for_save(form, fields)
        if validation_error is not None:
            field, error_key = validation_error
            form["plan"] = [field]
            form["pos"] = 0
            draft = dict(session["draft_report"])
            draft["mgmt_scope"] = scope.name
            draft["user_form"] = form
            await self._persist(
                update,
                Step.USER_FORM_INPUT,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._send_management_form_prompt(update, form, scope, error_key)
            return

        if form.get("mode") == "edit":
            target = await self._load_management_target(update, scope, actor, str(form["target_id"]))
            if target is None:
                return
            await self._users.update_basic(
                str(form["target_id"]),
                str(fields["name"]),
                str(fields["phone"]),
                fields.get("email"),
                fields.get("notes"),
            )
            await self._open_management_detail(update, actor, scope, str(form["target_id"]), scope.key("UPDATED"))
            return

        await self._create_user_with_retry(fields, scope)
        await self._open_management_menu(update, actor, scope, scope.key("ADDED"))

    async def _validate_user_form_for_save(
        self,
        form: dict[str, Any],
        fields: dict[str, Any],
    ) -> tuple[str, str] | None:
        for field in USER_FORM_FIELDS:
            result = validate_field(field, fields.get(field))
            if not result.ok:
                return field, str(result.error_key)
            fields[field] = result.value

        exclude_user_id = str(form["target_id"]) if form.get("mode") == "edit" else None
        if is_duplicate_phone(await self._users.list_all(), str(fields["phone"]), exclude_user_id):
            return "phone", "USER_ERROR_PHONE_DUPLICATE"
        return None

    async def _create_user_with_retry(self, fields: dict[str, Any], scope: ManagementScope) -> str:
        for _ in range(10):
            user_id = generate_user_id(self._now())
            if await self._users.get_by_id(user_id) is not None:
                continue
            await self._users.create_user(
                user_id,
                scope.managed_role.value,
                str(fields["name"]),
                str(fields["phone"]),
                fields.get("email"),
                fields.get("notes"),
                self._settings.active_status,
            )
            return user_id
        raise RuntimeError("Unable to generate a unique user_id")

    async def _open_management_status_confirmation(
        self,
        update: Update,
        actor: dict[str, Any],
        scope: ManagementScope,
        target_id: str,
        intent: str,
    ) -> None:
        target = await self._load_management_target(update, scope, actor, target_id)
        if target is None:
            return

        draft = {
            "user_name": actor["name"],
            "mgmt_scope": scope.name,
            "user_target_id": target["user_id"],
            "user_status_intent": intent,
        }
        await self._persist(update, Step.USER_CONFIRM_STATUS, draft, user_id=actor["user_id"])
        key = scope.key("CONFIRM_DEACTIVATE") if intent == "deactivate" else scope.key("CONFIRM_REACTIVATE")
        await self._send_management_confirmation(update, scope, key, target, f"{scope.name}:confirm_status")

    async def _confirm_management_status(
        self,
        update: Update,
        actor: dict[str, Any],
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        draft = dict(session["draft_report"])
        target = await self._load_management_target(update, scope, actor, str(draft.get("user_target_id", "")))
        if target is None:
            return

        intent = draft.get("user_status_intent")
        if intent == "deactivate":
            status = self._settings.inactive_status
            notice_key = scope.key("DEACTIVATED")
        elif intent == "reactivate":
            status = self._settings.active_status
            notice_key = scope.key("REACTIVATED")
        else:
            await self._send(update, "UNKNOWN_COMMAND")
            return

        await self._users.set_status(target["user_id"], status)
        await self._open_management_detail(update, actor, scope, target["user_id"], notice_key)

    async def _open_management_reset_link_confirmation(
        self,
        update: Update,
        actor: dict[str, Any],
        scope: ManagementScope,
        target_id: str,
    ) -> None:
        target = await self._load_management_target(update, scope, actor, target_id)
        if target is None:
            return

        draft = {"user_name": actor["name"], "mgmt_scope": scope.name, "user_target_id": target["user_id"]}
        await self._persist(update, Step.USER_CONFIRM_RESET_LINK, draft, user_id=actor["user_id"])
        await self._send_management_confirmation(
            update,
            scope,
            scope.key("CONFIRM_RESET_LINK"),
            target,
            f"{scope.name}:confirm_reset",
        )

    async def _confirm_management_reset_link(
        self,
        update: Update,
        actor: dict[str, Any],
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        target = await self._load_management_target(
            update,
            scope,
            actor,
            str(dict(session["draft_report"]).get("user_target_id", "")),
        )
        if target is None:
            return

        await self._users.reset_telegram_link(target["user_id"])
        await self._open_management_detail(update, actor, scope, target["user_id"], scope.key("LINK_RESET"))

    async def _handle_management_back_to_detail(
        self,
        update: Update,
        actor: dict[str, Any],
        session: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        draft = dict(session["draft_report"])
        form = dict(draft.get("user_form", {}))
        if Step(session["current_step"]) == Step.USER_EDIT_MENU and form.get("edit_menu_back") == "review":
            draft["mgmt_scope"] = scope.name
            await self._persist(
                update,
                Step.USER_FORM_REVIEW,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._send_management_form_review(update, form, scope)
            return

        target_id = str(draft.get("user_target_id") or form.get("target_id") or "")
        if not target_id:
            await self._open_management_menu(update, actor, scope)
            return
        await self._open_management_detail(update, actor, scope, target_id)

    async def _send_management_menu(
        self,
        update: Update,
        scope: ManagementScope,
        notice_key: str | None = None,
    ) -> None:
        await self._send_or_edit(
            update,
            scope.menu_key,
            reply_markup=await self._management_menu_keyboard(scope),
            notice=await self._notice_text(notice_key),
        )

    async def _send_management_list(
        self,
        update: Update,
        scope: ManagementScope,
        notice_key: str | None = None,
    ) -> None:
        users = await self._users.list_by_role(scope.managed_role.value)
        key = scope.key("LIST") if users else scope.key("LIST_EMPTY")
        await self._send_or_edit(
            update,
            key,
            reply_markup=await self._management_list_keyboard(users, scope),
            notice=await self._notice_text(notice_key),
        )

    async def _send_management_detail(
        self,
        update: Update,
        scope: ManagementScope,
        target: dict[str, Any],
        notice_key: str | None = None,
    ) -> None:
        await self._refresh_templates()
        await self._send_or_edit(
            update,
            scope.key("DETAIL"),
            reply_markup=await self._management_detail_keyboard(target, scope),
            **user_detail_tokens(self._templates, target, await self._notice_text(notice_key)),
        )

    async def _send_management_edit_menu(self, update: Update, scope: ManagementScope) -> None:
        await self._send_or_edit(
            update,
            scope.key("EDIT_MENU"),
            reply_markup=await self._management_edit_menu_keyboard(scope),
        )

    async def _send_management_confirmation(
        self,
        update: Update,
        scope: ManagementScope,
        key: str,
        target: dict[str, Any],
        yes_data: str,
    ) -> None:
        await self._send_or_edit(
            update,
            key,
            reply_markup=await self._management_confirm_keyboard(yes_data, scope),
            user_name=target["name"],
        )

    async def _send_management_form_prompt(
        self,
        update: Update,
        form: dict[str, Any],
        scope: ManagementScope,
        error_key: str | None = None,
    ) -> None:
        plan = list(form.get("plan", []))
        pos = int(form.get("pos", 0))
        if not plan or pos >= len(plan):
            await self._send(update, "UNKNOWN_COMMAND")
            return
        field = str(plan[pos])
        await self._send_trusted(
            update,
            user_field_prompt_key(field, scope),
            {"error"},
            error=await self._notice_text(error_key),
            reply_markup=await self._user_form_navigation_keyboard(field),
        )

    async def _send_management_form_review(
        self,
        update: Update,
        form: dict[str, Any],
        scope: ManagementScope,
    ) -> None:
        await self._send(
            update,
            scope.key("FORM_REVIEW"),
            reply_markup=await self._user_form_review_keyboard(),
            **user_form_review_tokens(dict(form.get("fields", {}))),
        )

    async def _sales_source_selected_text(self, draft: dict[str, Any]) -> str:
        selected_ids = list(draft.get("sales_source_ids", []))
        active_sources = {source.gmv_source_id: source for source in await self._active_sales_sources()}
        sales_data = dict(draft.get("sales_data", {}))
        labels = []
        for source_id in selected_ids:
            label = None
            if source_id in sales_data:
                label = dict(sales_data[source_id]).get("label")
            if label is None and source_id in active_sources:
                label = active_sources[source_id].label
            if label is not None:
                labels.append(label)
        await self._refresh_templates()
        return selected_sources_text(self._templates, labels)

    async def _sales_source_next_label(self, draft: dict[str, Any]) -> str | None:
        selected_ids = list(draft.get("sales_source_ids", []))
        if not selected_ids:
            return None

        active_sources = {source.gmv_source_id: source for source in await self._active_sales_sources()}
        sales_data = dict(draft.get("sales_data", {}))
        source_id = selected_ids[0]
        label = dict(sales_data.get(source_id, {})).get("label")
        if label is None and source_id in active_sources:
            label = active_sources[source_id].label
        if label is None:
            return None

        await self._refresh_templates()
        return self._templates.render_plain("BUTTON_SALES_INPUT_NEXT", source=label)

    async def _sales_summary_tokens(self, draft: dict[str, Any]) -> dict[str, str | int]:
        await self._refresh_templates()
        return sales_summary_text(self._templates, self._ordered_sales_rows_from_draft(draft))

    async def _summary_tokens(self, draft: dict[str, Any], store_label: str) -> dict[str, Any]:
        return build_summary({**draft, **await self._sales_summary_tokens(draft)}, store_label)

    async def _active_sales_sources(self) -> list[GmvSource]:
        return await self._sales_sources.list_active(self._settings.active_status)

    def _current_sales_input(self, draft: dict[str, Any]) -> tuple[str, str]:
        plan = list(draft.get("sales_input_plan", []))
        source_id, field = plan[int(draft.get("sales_input_pos", 0))]
        return str(source_id), str(field)

    def _ordered_sales_rows_from_draft(self, draft: dict[str, Any]) -> list[dict[str, Any]]:
        if draft.get("sales_no_sales"):
            return []
        sales_data = dict(draft.get("sales_data", {}))
        return [
            {**dict(sales_data[source_id]), "gmv_source_id": source_id}
            for source_id in draft.get("sales_source_ids", [])
            if source_id in sales_data
        ]

    def _sales_rows_from_draft(self, report_id: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for source in self._ordered_sales_rows_from_draft(draft):
            rows.append(
                {
                    "report_id": report_id,
                    "gmv_source_id": source["gmv_source_id"],
                    "source_label": source.get("source_label") or source["label"],
                    "source_type": source["source_type"],
                    "requires_traffic": bool(source["requires_traffic"]),
                    "traffic": int(source["traffic"]) if bool(source["requires_traffic"]) else None,
                    "gmv": int(source["gmv"]),
                    "order_count": int(source["order_count"]),
                    "pieces_sold": int(source["pieces_sold"]),
                    "sort_order": int(source["sort_order"]),
                }
            )
        return rows

    async def _show_manual_store_selection(self, update: Update, session: dict[str, Any]) -> None:
        draft = dict(session["draft_report"])
        has_submitted_location = "submitted_latitude" in draft and "submitted_longitude" in draft
        await self._persist(
            update,
            Step.MANUAL_STORE_SELECTION,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        if has_submitted_location:
            candidates = await self._all_active_candidates_from_draft(draft)
            reply_markup = store_list_keyboard(candidates, await self._candidate_button_labels(candidates))
        else:
            stores = await self._stores.list_active(self._settings.active_status)
            reply_markup = manual_store_list_keyboard(stores, await self._store_labels(stores))
        await self._send(
            update,
            "MANUAL_STORE_SELECTION",
            reply_markup=reply_markup,
            progress_step=Step.MANUAL_STORE_SELECTION,
        )

    async def _all_active_candidates_from_draft(self, draft: dict[str, Any]) -> list[StoreCandidate]:
        candidates = []
        for store in await self._stores.list_active(self._settings.active_status):
            if store.latitude is None or store.longitude is None:
                continue
            effective_radius = store.allowed_radius_meter or self._settings.default_radius_meter
            if effective_radius <= 0:
                effective_radius = self._settings.default_radius_meter
            distance = haversine_meters(
                draft["submitted_latitude"],
                draft["submitted_longitude"],
                store.latitude,
                store.longitude,
            )
            candidates.append(
                StoreCandidate(
                    store=store,
                    distance_meter=distance,
                    effective_radius_meter=effective_radius,
                    in_range=distance <= effective_radius,
                )
            )
        candidates.sort(key=lambda candidate: candidate.distance_meter)
        return candidates

    async def _new_report_id(self, now: datetime) -> str:
        for _ in range(10):
            report_id = generate_report_id(now)
            if not await self._reports.report_id_exists(report_id):
                return report_id
        raise RuntimeError("Unable to generate a unique report_id")

    async def _load_session_or_notify(self, update: Update) -> dict[str, Any] | None:
        session = await self._sessions.get(update.effective_chat.id)
        if session is None:
            await self._send(update, "UNKNOWN_COMMAND")
            return None

        if self._now() > session["expires_at"]:
            await self._sessions.delete(update.effective_chat.id)
            await self._send(update, "SESSION_EXPIRED", reply_markup=ReplyKeyboardRemove())
            return None

        return session

    async def _cancel(self, update: Update) -> None:
        await self._sessions.delete(update.effective_chat.id)
        await self._send(update, "CANCELLED", reply_markup=await self._start_again_keyboard())

    async def _persist(
        self,
        update: Update,
        step: Step,
        draft: dict[str, Any],
        selected_store_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        now = self._now()
        await self._sessions.upsert(
            telegram_chat_id=update.effective_chat.id,
            telegram_user_id=update.effective_user.id,
            current_step=step,
            draft_report=draft,
            selected_store_id=selected_store_id,
            user_id=user_id,
            updated_at=now,
            expires_at=now + timedelta(minutes=self._settings.session_ttl_minutes),
        )

    async def _persist_sales_step(
        self,
        update: Update,
        step: Step,
        session: dict[str, Any],
        draft: dict[str, Any],
    ) -> None:
        await self._persist(
            update,
            step,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )

    async def _send(
        self,
        update: Update,
        key: str,
        reply_markup: Any = None,
        progress_step: Step | None = None,
        **tokens: Any,
    ) -> None:
        await self._refresh_templates()
        if progress_step is not None:
            tokens["progress"] = progress_for_step(self._templates, progress_step)
        await update.effective_chat.send_message(
            text=self._templates.render(key, **tokens),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    async def _send_trusted(
        self,
        update: Update,
        key: str,
        trusted_tokens: set[str],
        reply_markup: Any = None,
        progress_step: Step | None = None,
        **tokens: Any,
    ) -> None:
        await self._refresh_templates()
        if progress_step is not None:
            tokens["progress"] = progress_for_step(self._templates, progress_step)
        await update.effective_chat.send_message(
            text=self._templates.render_trusted(key, trusted_tokens, **tokens),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    async def _send_or_edit(
        self,
        update: Update,
        key: str,
        reply_markup: Any = None,
        trusted_tokens: set[str] | None = None,
        **tokens: Any,
    ) -> None:
        await self._refresh_templates()
        if trusted_tokens is None:
            text = self._templates.render(key, **tokens)
        else:
            text = self._templates.render_trusted(key, trusted_tokens, **tokens)

        callback_query = update.callback_query
        if (
            callback_query is not None
            and callback_query.message is not None
            and hasattr(callback_query, "edit_message_text")
        ):
            try:
                await callback_query.edit_message_text(
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                )
                return
            except BadRequest as exc:
                if "Message is not modified" in str(exc):
                    return
                raise

        await update.effective_chat.send_message(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    async def _notice_text(self, key: str | None) -> str:
        if key is None:
            return ""
        await self._refresh_templates()
        return self._templates.render(key)

    async def _send_step_prompt(self, update: Update, step: Step) -> None:
        if step == Step.ASK_STOCK_ISSUE:
            await self._send_stock_issue_prompt(update, {})
            return
        if step in TEXT_STEPS:
            await self._send(update, step.value, reply_markup=await self._none_reply_keyboard(), progress_step=step)
            return
        await self._send(update, step.value, reply_markup=ReplyKeyboardRemove(), progress_step=step)

    async def _send_stock_issue_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        await self._send(
            update,
            "ASK_STOCK_ISSUE",
            selected_issues=await self._stock_issue_selected_text(draft),
            reply_markup=await self._stock_issue_keyboard(draft),
            progress_step=Step.ASK_STOCK_ISSUE,
        )

    async def _edit_stock_issue_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        if update.callback_query is None or update.callback_query.message is None:
            await self._send_stock_issue_prompt(update, draft)
            return
        try:
            await update.callback_query.edit_message_text(
                text=await self._render(
                    "ASK_STOCK_ISSUE",
                    progress_step=Step.ASK_STOCK_ISSUE,
                    selected_issues=await self._stock_issue_selected_text(draft),
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=await self._stock_issue_keyboard(draft),
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    async def _send_stock_issue_detail_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        await self._send_trusted(
            update,
            "STOCK_ISSUE_DETAIL_PROMPT",
            {"instructions"},
            issue=await self._stock_issue_option_label(draft, draft["stock_issue_detail_option_id"]),
            detail_progress=await self._stock_issue_detail_progress(draft),
            sku_list=await self._stock_issue_sku_text(draft),
            instructions=await self._stock_issue_detail_instruction_text(),
            reply_markup=await self._sales_input_navigation_keyboard(),
            progress_step=Step.ASK_STOCK_ISSUE,
        )

    async def _render(self, key: str, progress_step: Step | None = None, **tokens: Any) -> str:
        await self._refresh_templates()
        if progress_step is not None:
            tokens["progress"] = progress_for_step(self._templates, progress_step)
        return self._templates.render(key, **tokens)

    async def _render_trusted(
        self,
        key: str,
        trusted_tokens: set[str],
        progress_step: Step | None = None,
        **tokens: Any,
    ) -> str:
        await self._refresh_templates()
        if progress_step is not None:
            tokens["progress"] = progress_for_step(self._templates, progress_step)
        return self._templates.render_trusted(key, trusted_tokens, **tokens)

    async def _refresh_templates(self) -> None:
        self._templates.update(await self._templates_repository.list_all())

    async def _store_label(self, store: StoreLocation) -> str:
        await self._refresh_templates()
        return self._templates.render_store_label(store)

    async def _store_labels(self, stores: list[StoreLocation]) -> dict[str, str]:
        await self._refresh_templates()
        return {store.store_id: self._templates.render_store_label(store) for store in stores}

    async def _candidate_button_labels(self, candidates: list[StoreCandidate]) -> dict[str, str]:
        await self._refresh_templates()
        return {
            candidate.store.store_id: self._templates.render_store_button_label(
                candidate.store,
                candidate.distance_meter,
            )
            for candidate in candidates
        }

    async def _distance_meter(self, distance: float | None) -> str:
        await self._refresh_templates()
        return self._templates.render_distance_meter(distance)

    async def _location_status_label(self, status: str) -> str:
        await self._refresh_templates()
        return self._templates.render_location_status(status)

    async def _manual_store_button_label(self) -> str:
        await self._refresh_templates()
        return self._templates.render("BUTTON_SELECT_STORE_MANUAL")

    async def _start_location_keyboard(self):
        await self._refresh_templates()
        return start_location_keyboard(
            self._templates.render("BUTTON_SHARE_LOCATION"),
            self._templates.render("BUTTON_SELECT_STORE_MANUAL"),
        )

    async def _retry_location_keyboard(self):
        await self._refresh_templates()
        return retry_location_keyboard(
            self._templates.render("BUTTON_SHARE_LOCATION"),
        )

    async def _activation_contact_keyboard(self):
        await self._refresh_templates()
        return activation_contact_keyboard(
            self._templates.render("BUTTON_SHARE_CONTACT"),
        )

    async def _admin_menu_keyboard(self):
        await self._refresh_templates()
        return admin_menu_keyboard(
            self._templates.render("BUTTON_MENU_INPUT_REPORT"),
            self._templates.render("BUTTON_MENU_MANAGE_USERS"),
        )

    async def _super_admin_menu_keyboard(self):
        await self._refresh_templates()
        return super_admin_menu_keyboard(
            self._templates.render("BUTTON_MENU_INPUT_REPORT"),
            self._templates.render("BUTTON_MENU_MANAGE_USERS"),
            self._templates.render("BUTTON_MENU_MANAGE_ADMINS"),
            self._templates.render("BUTTON_MENU_MANAGE_STORES"),
        )

    async def _management_menu_keyboard(self, scope: ManagementScope):
        await self._refresh_templates()
        return management_menu_keyboard(
            scope.name,
            self._templates.render(f"BUTTON_{scope.entity}_ADD"),
            self._templates.render(f"BUTTON_{scope.entity}_LIST"),
            self._templates.render("BUTTON_BACK"),
        )

    async def _management_list_keyboard(self, users: list[dict[str, Any]], scope: ManagementScope):
        await self._refresh_templates()
        return management_list_keyboard(
            scope.name,
            users,
            user_list_button_labels(self._templates, scope, users),
            self._templates.render("BUTTON_BACK"),
        )

    async def _management_detail_keyboard(self, user: dict[str, Any], scope: ManagementScope):
        await self._refresh_templates()
        return management_detail_keyboard(
            scope.name,
            str(user["user_id"]),
            user["status"] == self._settings.active_status,
            self._templates.render(f"BUTTON_{scope.entity}_EDIT"),
            self._templates.render(f"BUTTON_{scope.entity}_DEACTIVATE"),
            self._templates.render(f"BUTTON_{scope.entity}_REACTIVATE"),
            self._templates.render(f"BUTTON_{scope.entity}_RESET_LINK"),
            self._templates.render("BUTTON_BACK"),
        )

    async def _management_edit_menu_keyboard(self, scope: ManagementScope):
        await self._refresh_templates()
        return management_edit_menu_keyboard(
            scope.name,
            user_field_button_labels(self._templates, scope),
            self._templates.render("BUTTON_BACK"),
        )

    async def _management_confirm_keyboard(self, yes_data: str, scope: ManagementScope):
        await self._refresh_templates()
        return confirm_keyboard(
            self._templates.render("BUTTON_CONFIRM_YES"),
            self._templates.render("BUTTON_BACK"),
            yes_data,
            f"{scope.name}:back:detail",
        )

    async def _user_form_navigation_keyboard(self, field: str):
        await self._refresh_templates()
        return user_form_navigation_keyboard(
            self._templates.render("BUTTON_PREVIOUS"),
            self._templates.render("BUTTON_CANCEL"),
            self._templates.render("BUTTON_SKIP") if field in OPTIONAL_FIELDS else None,
        )

    async def _user_form_review_keyboard(self):
        await self._refresh_templates()
        return user_form_review_keyboard(
            self._templates.render("BUTTON_SAVE"),
            self._templates.render("BUTTON_EDIT"),
            self._templates.render("BUTTON_CANCEL"),
        )

    async def _send_activation_contact_prompt(self, update: Update) -> None:
        await self._send(
            update,
            "ACTIVATION_ASK_CONTACT",
            share_contact_button=self._templates.render("BUTTON_SHARE_CONTACT"),
            reply_markup=await self._activation_contact_keyboard(),
        )

    async def _start_again_keyboard(self):
        await self._refresh_templates()
        return start_again_keyboard(self._templates.render("BUTTON_START"))

    async def _confirm_store_keyboard(self):
        await self._refresh_templates()
        return confirm_store_keyboard(
            self._templates.render("BUTTON_CONFIRM_YES"),
            self._templates.render("BUTTON_OTHER_STORE"),
        )

    async def _summary_keyboard(self):
        await self._refresh_templates()
        return summary_keyboard(
            self._templates.render("BUTTON_SUBMIT"),
            self._templates.render("BUTTON_RESTART"),
            self._templates.render("BUTTON_CANCEL"),
        )

    async def _duplicate_keyboard(self):
        await self._refresh_templates()
        return duplicate_keyboard(
            self._templates.render("BUTTON_DUPLICATE_CONFIRM"),
            self._templates.render("BUTTON_DUPLICATE_CANCEL"),
        )

    async def _none_reply_keyboard(self):
        await self._refresh_templates()
        return none_reply_keyboard(self._templates.render("BUTTON_NONE"))

    async def _sales_source_keyboard(self, draft: dict[str, Any]):
        await self._refresh_templates()
        options = [(source.gmv_source_id, source.label) for source in await self._active_sales_sources()]
        return sales_source_keyboard(
            options,
            set(draft.get("sales_source_ids", [])),
            self._templates.render("SELECTED_PREFIX"),
            self._templates.render("BUTTON_NO_SALES"),
            await self._sales_source_next_label(draft),
        )

    async def _sales_input_navigation_keyboard(self):
        await self._refresh_templates()
        return sales_input_navigation_keyboard(
            self._templates.render("BUTTON_PREVIOUS"),
            self._templates.render("BUTTON_CANCEL"),
        )

    async def _sales_summary_keyboard(self):
        await self._refresh_templates()
        return sales_summary_keyboard(
            self._templates.render("BUTTON_SALES_CONTINUE"),
            self._templates.render("BUTTON_SALES_EDIT"),
            self._templates.render("BUTTON_CANCEL"),
        )

    async def _sales_edit_menu_keyboard(self, draft: dict[str, Any]):
        await self._refresh_templates()
        sources = [
            (row["gmv_source_id"], row.get("source_label") or row["label"])
            for row in self._ordered_sales_rows_from_draft(draft)
        ]
        return sales_edit_menu_keyboard(
            sources,
            self._templates.render("BUTTON_EDIT_SOURCES"),
            self._templates.render("BUTTON_BACK_TO_SUMMARY"),
        )

    async def _stock_issue_keyboard(self, draft: dict[str, Any]):
        await self._refresh_templates()
        options = [(issue.stock_issue_id, issue.label) for issue in await self._active_stock_issues()]
        return stock_issue_keyboard(
            options,
            set(draft.get("stock_issue_ids", [])),
            self._templates.render("SELECTED_PREFIX"),
            self._templates.render("BUTTON_NONE"),
            await self._stock_issue_next_label(draft),
        )

    async def _stock_issue_selected_text(self, draft: dict[str, Any]) -> str:
        selected_ids = list(draft.get("stock_issue_ids", []))
        active_issues = {issue.stock_issue_id: issue for issue in await self._active_stock_issues()}
        labels_by_id = dict(draft.get("stock_issue_labels", {}))
        labels = []
        for issue_id in selected_ids:
            label = labels_by_id.get(issue_id)
            if label is None and issue_id in active_issues:
                label = active_issues[issue_id].label
            if label is not None:
                labels.append(label)
        await self._refresh_templates()
        return selected_issue_text(self._templates, labels)

    async def _stock_issue_next_label(self, draft: dict[str, Any]) -> str | None:
        selected_ids = list(draft.get("stock_issue_ids", []))
        if not selected_ids:
            return None

        active_issues = {issue.stock_issue_id: issue for issue in await self._active_stock_issues()}
        labels_by_id = dict(draft.get("stock_issue_labels", {}))
        issue_id = selected_ids[0]
        label = labels_by_id.get(issue_id)
        if label is None and issue_id in active_issues:
            label = active_issues[issue_id].label
        if label is None:
            return None

        await self._refresh_templates()
        return self._templates.render_plain("BUTTON_STOCK_ISSUE_NEXT", issue=label)

    async def _stock_issue_value(self, draft: dict[str, Any]) -> str:
        await self._refresh_templates()
        lines = []
        details = dict(draft.get("stock_issue_sku_details", {}))
        empty_value = self._templates.render("STOCK_ISSUE_DETAIL_EMPTY_VALUE")

        for option_id in draft.get("stock_issue_detail_option_ids", []):
            sku_values = list(details.get(option_id, []))
            lines.append(
                self._templates.render(
                    "STOCK_ISSUE_DETAIL_LINE",
                    issue=await self._stock_issue_option_label(draft, option_id),
                    sku_list=", ".join(sku_values) if sku_values else empty_value,
                )
            )

        if not lines:
            return "-"
        return "\n".join(lines)

    async def _stock_issue_sku_text(self, draft: dict[str, Any]) -> str:
        current_option_id = draft["stock_issue_detail_option_id"]
        await self._refresh_templates()
        return sku_list_text(self._templates, current_sku_values(draft, current_option_id))

    async def _stock_issue_option_label(self, draft: dict[str, Any], option_id: str) -> str:
        return str(dict(draft.get("stock_issue_labels", {})).get(option_id, option_id))

    async def _stock_issue_detail_title(self, draft: dict[str, Any], option_id: str) -> str:
        return str(dict(draft.get("stock_issue_labels", {})).get(option_id, option_id))

    async def _stock_issue_detail_progress(self, draft: dict[str, Any]) -> str:
        detail_option_ids = list(draft.get("stock_issue_detail_option_ids", []))
        current_option_id = draft["stock_issue_detail_option_id"]
        await self._refresh_templates()
        return contextual_step_progress(
            self._templates,
            "STOCK_ISSUE_DETAIL_STEP_LABEL",
            current_detail_position(detail_option_ids, current_option_id),
            len(detail_option_ids),
            await self._stock_issue_detail_title(draft, current_option_id),
        )

    async def _stock_issue_detail_instruction_text(self) -> str:
        await self._refresh_templates()
        return detail_instruction_text(self._templates)

    async def _active_stock_issues(self) -> list[StockIssue]:
        return await self._stock_issues.list_active(self._settings.active_status)

    async def _remove_callback_keyboard(self, update: Update) -> None:
        if update.callback_query is None or update.callback_query.message is None:
            return
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    async def _is_none_answer(self, text: str) -> bool:
        await self._refresh_templates()
        return text.strip().casefold() == self._templates.render("BUTTON_NONE").casefold()

    async def _is_previous_answer(self, text: str) -> bool:
        await self._refresh_templates()
        return text.strip().casefold() == self._templates.render("BUTTON_PREVIOUS").casefold()

    async def _is_cancel_answer(self, text: str) -> bool:
        await self._refresh_templates()
        return text.strip().casefold() == self._templates.render("BUTTON_CANCEL").casefold()

    async def _is_skip_answer(self, text: str) -> bool:
        await self._refresh_templates()
        return text.strip().casefold() == self._templates.render("BUTTON_SKIP").casefold()

    async def _is_start_answer(self, text: str) -> bool:
        await self._refresh_templates()
        return text.strip().casefold() == self._templates.render("BUTTON_START").casefold()

    async def _is_manual_store_answer(self, text: str) -> bool:
        await self._refresh_templates()
        return text.strip().casefold() == self._templates.render("BUTTON_SELECT_STORE_MANUAL").casefold()

    async def _ensure_private(self, update: Update) -> bool:
        if update.effective_chat.type == ChatType.PRIVATE:
            return True
        await self._send(update, "PRIVATE_CHAT_ONLY")
        return False

    def _area_label(self, candidates: list[StoreCandidate]) -> str:
        if not candidates:
            return self._templates.render("AREA_NEAREST_FALLBACK")
        first = candidates[0].store
        area = self._templates.render_area_label(first)
        if all(
            candidate.store.department_store == first.department_store
            and candidate.store.branch == first.branch
            and candidate.store.city == first.city
            for candidate in candidates
        ):
            return area
        return self._templates.render("AREA_MULTIPLE_NEAREST", store_count=len(candidates))

    def _now(self) -> datetime:
        return datetime.now(self._settings.timezone)


def _candidate_distances(candidates: list[StoreCandidate]) -> dict[str, dict[str, Any]]:
    return {
        candidate.store.store_id: {
            "distance_meter": candidate.distance_meter,
            "effective_radius_meter": candidate.effective_radius_meter,
            "in_range": candidate.in_range,
        }
        for candidate in candidates
    }

def _message_text(update: Update) -> str | None:
    if update.message is None or update.message.text is None:
        return None
    return update.message.text


def _message_has_location(update: Update) -> bool:
    return update.message is not None and update.message.location is not None

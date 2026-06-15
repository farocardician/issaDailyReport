from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from app.bot.keyboards import (
    confirm_store_keyboard,
    duplicate_keyboard,
    none_reply_keyboard,
    share_location_keyboard,
    stock_issue_detail_keyboard,
    stock_issue_keyboard,
    store_list_keyboard,
    summary_keyboard,
)
from app.bot.notifications import send_admin_notification
from app.config import Settings
from app.domain.geo import haversine_meters
from app.domain.report import build_summary, generate_report_id, location_status
from app.domain.session_state import NUMERIC_STEP_FIELDS, Step, apply_numeric_answer, next_step
from app.domain.store_matching import MatchType, StoreCandidate, StoreLocation, match_stores
from app.domain.validation import normalize_text_dash, parse_int_lenient
from app.repositories.reports import ReportsRepository
from app.repositories.sessions import SessionsRepository
from app.repositories.stores import StoresRepository
from app.repositories.templates import TemplatesRepository
from app.repositories.users import UsersRepository
from app.templates import MessageTemplates, distance_meter, store_label


TEXT_STEPS: dict[Step, str] = {
    Step.ASK_NOTE: "note",
}

NUMERIC_NONE_STEPS = {
    Step.ASK_TRAFFIC,
    Step.ASK_GMV,
    Step.ASK_ONLINE_GMV,
    Step.ASK_ORDER,
    Step.ASK_PIECES,
}

STOCK_ISSUE_OPTIONS = (
    ("size_empty", "STOCK_ISSUE_OPTION_SIZE_EMPTY"),
    ("color_empty", "STOCK_ISSUE_OPTION_COLOR_EMPTY"),
    ("not_arrived", "STOCK_ISSUE_OPTION_NOT_ARRIVED"),
    ("stock_empty", "STOCK_ISSUE_OPTION_STOCK_EMPTY"),
)


class ReportFlow:
    def __init__(
        self,
        settings: Settings,
        templates: MessageTemplates,
        templates_repository: TemplatesRepository,
        stores: StoresRepository,
        users: UsersRepository,
        reports: ReportsRepository,
        sessions: SessionsRepository,
    ) -> None:
        self._settings = settings
        self._templates = templates
        self._templates_repository = templates_repository
        self._stores = stores
        self._users = users
        self._reports = reports
        self._sessions = sessions

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private(update):
            return
        await self._sessions.delete(update.effective_chat.id)
        await self._persist(update, Step.AWAITING_LOCATION, {})
        await self._send(update, "START", reply_markup=await self._share_location_keyboard())

    async def handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private(update):
            return
        await self._cancel(update)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_private(update):
            return

        session = await self._load_session_or_notify(update)
        if session is None:
            return

        step = Step(session["current_step"])
        if step == Step.AWAITING_LOCATION:
            await self._handle_location(update, session)
        elif step == Step.AWAITING_PIN:
            await self._handle_pin(update, session)
        elif step in NUMERIC_STEP_FIELDS:
            await self._handle_numeric(update, session, step)
        elif step == Step.ASK_STOCK_ISSUE:
            await self._handle_stock_issue_text(update, session)
        elif step == Step.ASK_NO_BUY_REASON:
            await self._skip_no_buy_reason(update, session)
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
        else:
            await self._send(update, "UNKNOWN_COMMAND")

    async def _handle_location(self, update: Update, session: dict[str, Any]) -> None:
        if update.message is None or update.message.location is None:
            await self._send(update, "ASK_LOCATION", reply_markup=await self._share_location_keyboard())
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
            await self._persist(update, Step.CONFIRM_STORE, draft)
            await self._send(
                update,
                "STORE_CONFIRMATION",
                store_label=store_label(candidate.store),
                distance_meter=distance_meter(candidate.distance_meter),
                reply_markup=await self._confirm_store_keyboard(),
            )
            return

        if match.match_type == MatchType.MULTIPLE:
            await self._refresh_templates()
            await self._persist(update, Step.CHOOSE_STORE, draft)
            await self._send(
                update,
                "MULTIPLE_STORES_FOUND",
                area_label=self._area_label(match.candidates),
                reply_markup=store_list_keyboard(
                    match.candidates,
                    other_store_label=self._templates.render("BUTTON_OTHER_STORE"),
                ),
            )
            return

        await self._persist(update, Step.MANUAL_STORE_SELECTION, draft)
        await self._send(
            update,
            "LOCATION_NOT_FOUND",
            reply_markup=store_list_keyboard(match.candidates),
        )

    async def _handle_pin(self, update: Update, session: dict[str, Any]) -> None:
        text = _message_text(update)
        if text is None:
            await self._send(update, "ASK_PIN")
            return

        users = await self._users.find_active_by_pin(text.strip(), self._settings.active_status)
        if len(users) != 1:
            await self._send(update, "PIN_INVALID")
            return

        user = users[0]
        await self._users.bind_telegram(user["user_id"], update.effective_user.id, update.effective_chat.id)
        draft = dict(session["draft_report"])
        draft["user_name"] = user["name"]
        await self._persist(
            update,
            Step.ASK_TRAFFIC,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=user["user_id"],
        )
        await self._send_step_prompt(update, Step.ASK_TRAFFIC)

    async def _handle_numeric(self, update: Update, session: dict[str, Any], step: Step) -> None:
        text = _message_text(update)
        if text is None:
            await self._send_step_prompt(update, step)
            return

        text = text.strip()
        try:
            value = 0 if await self._is_none_answer(text) and step in NUMERIC_NONE_STEPS else parse_int_lenient(text)
        except ValueError:
            await self._send_step_prompt(update, step)
            return

        following_step, draft = apply_numeric_answer(step, session["draft_report"], value)
        await self._persist(
            update,
            following_step,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_step_prompt(update, following_step)

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

    async def _skip_no_buy_reason(self, update: Update, session: dict[str, Any]) -> None:
        draft = dict(session["draft_report"])
        draft["no_buy_reason"] = "-"
        await self._persist(
            update,
            Step.ASK_STOCK_ISSUE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_step_prompt(update, Step.ASK_STOCK_ISSUE)

    async def _handle_stock_issue_text(self, update: Update, session: dict[str, Any]) -> None:
        text = _message_text(update)
        if text is None:
            await self._send_stock_issue_prompt(update, dict(session["draft_report"]))
            return

        draft = dict(session["draft_report"])
        if draft.get("stock_issue_detail_option_id"):
            if await self._is_none_answer(text):
                await self._advance_stock_issue_detail(update, session, draft)
                return
            await self._append_stock_issue_skus(update, session, draft, text)
            return

        if await self._is_none_answer(text):
            await self._save_stock_issue_and_continue(update, session, "-")
            return

        custom_issues = list(draft.get("stock_issue_custom", []))
        custom_issue = normalize_text_dash(text)
        if custom_issue != "-" and custom_issue not in custom_issues:
            custom_issues.append(custom_issue)
        draft["stock_issue_custom"] = custom_issues
        draft["stock_issue_waiting_custom"] = False
        await self._persist(
            update,
            Step.ASK_STOCK_ISSUE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_stock_issue_prompt(update, draft)

    async def _handle_stock_issue_callback(self, update: Update, session: dict[str, Any], data: str) -> None:
        draft = dict(session["draft_report"])

        if data == "stock_issue:detail_done":
            await self._advance_stock_issue_detail(update, session, draft)
            return

        if data == "stock_issue:detail_skip":
            current_option_id = draft.get("stock_issue_detail_option_id")
            if current_option_id:
                details = dict(draft.get("stock_issue_sku_details", {}))
                details[current_option_id] = []
                draft["stock_issue_sku_details"] = details
            await self._advance_stock_issue_detail(update, session, draft)
            return

        if data.startswith("stock_issue:toggle:"):
            option_id = data.removeprefix("stock_issue:toggle:")
            if option_id not in {option_id for option_id, _ in STOCK_ISSUE_OPTIONS}:
                await self._send(update, "UNKNOWN_COMMAND")
                return

            selected_ids = set(draft.get("stock_issue_option_ids", []))
            if option_id in selected_ids:
                selected_ids.remove(option_id)
            else:
                selected_ids.add(option_id)
            draft["stock_issue_option_ids"] = sorted(selected_ids)
            draft["stock_issue_waiting_custom"] = False
            await self._persist(
                update,
                Step.ASK_STOCK_ISSUE,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._edit_stock_issue_prompt(update, draft)
            return

        if data == "stock_issue:other":
            draft["stock_issue_waiting_custom"] = True
            await self._persist(
                update,
                Step.ASK_STOCK_ISSUE,
                draft,
                selected_store_id=session["selected_store_id"],
                user_id=session["user_id"],
            )
            await self._send(update, "STOCK_ISSUE_CUSTOM_PROMPT")
            return

        if data == "stock_issue:none":
            await self._remove_callback_keyboard(update)
            await self._save_stock_issue_and_continue(update, session, "-")
            return

        if data == "stock_issue:done":
            await self._remove_callback_keyboard(update)
            await self._start_stock_issue_details_or_save(update, session, draft)
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
        draft.pop("stock_issue_option_ids", None)
        draft.pop("stock_issue_custom", None)
        draft.pop("stock_issue_waiting_custom", None)
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

    async def _start_stock_issue_details_or_save(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
    ) -> None:
        detail_option_ids = self._ordered_selected_stock_issue_ids(draft)
        if not detail_option_ids:
            await self._save_stock_issue_and_continue(update, session, await self._stock_issue_value(draft))
            return

        draft["stock_issue_detail_option_ids"] = detail_option_ids
        draft["stock_issue_detail_option_id"] = detail_option_ids[0]
        draft["stock_issue_sku_details"] = dict(draft.get("stock_issue_sku_details", {}))
        await self._persist(
            update,
            Step.ASK_STOCK_ISSUE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_stock_issue_detail_prompt(update, draft)

    async def _append_stock_issue_skus(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
        text: str,
    ) -> None:
        current_option_id = draft["stock_issue_detail_option_id"]
        sku_values = _parse_sku_values(text)
        if not sku_values:
            await self._send_stock_issue_detail_prompt(update, draft)
            return

        details = dict(draft.get("stock_issue_sku_details", {}))
        current_values = list(details.get(current_option_id, []))
        for sku in sku_values:
            if sku not in current_values:
                current_values.append(sku)
        details[current_option_id] = current_values
        draft["stock_issue_sku_details"] = details
        await self._persist(
            update,
            Step.ASK_STOCK_ISSUE,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send_stock_issue_detail_prompt(update, draft)

    async def _advance_stock_issue_detail(
        self,
        update: Update,
        session: dict[str, Any],
        draft: dict[str, Any],
    ) -> None:
        detail_option_ids = list(draft.get("stock_issue_detail_option_ids", []))
        current_option_id = draft.get("stock_issue_detail_option_id")
        next_index = detail_option_ids.index(current_option_id) + 1 if current_option_id in detail_option_ids else 0

        if next_index >= len(detail_option_ids):
            stock_issue = await self._stock_issue_value(draft)
            await self._remove_callback_keyboard(update)
            await self._save_stock_issue_and_continue(update, session, stock_issue)
            return

        draft["stock_issue_detail_option_id"] = detail_option_ids[next_index]
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
            await self._send(update, "REPORT_ALREADY_EXISTS", reply_markup=await self._duplicate_keyboard())
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
        distance = float(draft["distance_from_store_meter"])
        effective_radius = int(draft["effective_radius_meter"])
        report = {
            "report_id": await self._new_report_id(now),
            "report_date": now.date(),
            "store_id": session["selected_store_id"],
            "user_id": session["user_id"],
            "traffic": draft["traffic"],
            "offline_gmv": draft["offline_gmv"],
            "online_gmv": draft["online_gmv"],
            "order_count": draft["order_count"],
            "pieces_sold": draft["pieces_sold"],
            "no_buy_reason": draft["no_buy_reason"],
            "stock_issue": draft["stock_issue"],
            "submitted_latitude": draft["submitted_latitude"],
            "submitted_longitude": draft["submitted_longitude"],
            "distance_from_store_meter": distance,
            "note": draft["note"],
            "submission_status": submission_status,
            "location_status": location_status(distance, effective_radius),
            "created_at": now,
        }
        await self._reports.create(report)
        await self._sessions.delete(update.effective_chat.id)
        await self._send(update, "SUBMIT_SUCCESS", reply_markup=ReplyKeyboardRemove())

        store = await self._stores.get_by_id(session["selected_store_id"])
        if store is not None:
            notification_key = "ADMIN_NOTIFICATION_CORRECTION"
            if submission_status != "correction":
                notification_key = "ADMIN_NOTIFICATION"
            message = await self._render(
                notification_key,
                store_label=store_label(store),
                user_name=draft["user_name"],
                report_date=report["report_date"],
                traffic=report["traffic"],
                offline_gmv=report["offline_gmv"],
                online_gmv=report["online_gmv"],
                order_count=report["order_count"],
                pieces_sold=report["pieces_sold"],
                no_buy_reason=report["no_buy_reason"],
                stock_issue=report["stock_issue"],
                note=report["note"],
                distance_meter=distance_meter(float(report["distance_from_store_meter"])),
                location_status=report["location_status"],
            )
            await send_admin_notification(
                context.bot,
                self._settings.admin_chat_id,
                message,
            )

    async def _select_store(self, update: Update, session: dict[str, Any], store_id: str) -> None:
        store = await self._stores.get_by_id(store_id)
        if (
            store is None
            or store.status != self._settings.active_status
            or store.latitude is None
            or store.longitude is None
        ):
            await self._send(update, "UNKNOWN_COMMAND")
            return

        draft = dict(session["draft_report"])
        candidate = draft.get("candidate_distances", {}).get(store_id)
        if candidate is None:
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
            distance = float(candidate["distance_meter"])
            effective_radius = int(candidate["effective_radius_meter"])

        draft["distance_from_store_meter"] = distance
        draft["effective_radius_meter"] = effective_radius
        await self._persist(
            update,
            Step.AWAITING_PIN,
            draft,
            selected_store_id=store_id,
            user_id=session["user_id"],
        )
        await self._send(update, "ASK_PIN", reply_markup=ReplyKeyboardRemove())

    async def _send_summary(self, update: Update, draft: dict[str, Any], selected_store_id: str) -> None:
        store = await self._stores.get_by_id(selected_store_id)
        if store is None:
            await self._send(update, "UNKNOWN_COMMAND")
            return
        tokens = build_summary(draft, store_label(store))
        await self._send(update, "REPORT_SUMMARY", reply_markup=await self._summary_keyboard(), **tokens)

    async def _show_manual_store_selection(self, update: Update, session: dict[str, Any]) -> None:
        draft = dict(session["draft_report"])
        candidates = await self._all_active_candidates_from_draft(draft)
        await self._persist(update, Step.MANUAL_STORE_SELECTION, draft)
        await self._send(
            update,
            "MANUAL_STORE_SELECTION",
            reply_markup=store_list_keyboard(candidates),
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
        await self._send(update, "CANCELLED", reply_markup=ReplyKeyboardRemove())

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

    async def _send(self, update: Update, key: str, reply_markup: Any = None, **tokens: Any) -> None:
        await self._refresh_templates()
        await update.effective_chat.send_message(
            text=self._templates.render(key, **tokens),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    async def _send_step_prompt(self, update: Update, step: Step) -> None:
        if step == Step.ASK_STOCK_ISSUE:
            await self._send_stock_issue_prompt(update, {})
            return
        if step in NUMERIC_NONE_STEPS or step in TEXT_STEPS:
            await self._send(update, step.value, reply_markup=await self._none_reply_keyboard())
            return
        await self._send(update, step.value, reply_markup=ReplyKeyboardRemove())

    async def _send_stock_issue_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        await self._send(
            update,
            "ASK_STOCK_ISSUE",
            selected_issues=await self._stock_issue_selected_text(draft),
            reply_markup=await self._stock_issue_keyboard(draft),
        )

    async def _edit_stock_issue_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        if update.callback_query is None or update.callback_query.message is None:
            await self._send_stock_issue_prompt(update, draft)
            return
        try:
            await update.callback_query.edit_message_text(
                text=await self._render("ASK_STOCK_ISSUE", selected_issues=await self._stock_issue_selected_text(draft)),
                parse_mode=ParseMode.HTML,
                reply_markup=await self._stock_issue_keyboard(draft),
            )
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise

    async def _send_stock_issue_detail_prompt(self, update: Update, draft: dict[str, Any]) -> None:
        await self._send(
            update,
            "STOCK_ISSUE_DETAIL_PROMPT",
            issue=await self._stock_issue_option_label(draft["stock_issue_detail_option_id"]),
            sku_list=await self._stock_issue_sku_text(draft),
            reply_markup=await self._stock_issue_detail_keyboard(),
        )

    async def _render(self, key: str, **tokens: Any) -> str:
        await self._refresh_templates()
        return self._templates.render(key, **tokens)

    async def _refresh_templates(self) -> None:
        self._templates.update(await self._templates_repository.list_all())

    async def _share_location_keyboard(self):
        await self._refresh_templates()
        return share_location_keyboard(self._templates.render("BUTTON_SHARE_LOCATION"))

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

    async def _stock_issue_keyboard(self, draft: dict[str, Any]):
        await self._refresh_templates()
        selected_ids = set(draft.get("stock_issue_option_ids", []))
        options = [(option_id, self._templates.render(template_key)) for option_id, template_key in STOCK_ISSUE_OPTIONS]
        return stock_issue_keyboard(
            options,
            selected_ids,
            self._templates.render("SELECTED_PREFIX"),
            self._templates.render("BUTTON_NONE"),
            self._templates.render("BUTTON_STOCK_ISSUE_OTHER"),
            self._templates.render("BUTTON_DONE"),
        )

    async def _stock_issue_detail_keyboard(self):
        await self._refresh_templates()
        return stock_issue_detail_keyboard(
            self._templates.render("BUTTON_DONE"),
            self._templates.render("BUTTON_SKIP"),
        )

    async def _stock_issue_selected_text(self, draft: dict[str, Any]) -> str:
        selected = await self._stock_issue_category_values(draft)
        if not selected:
            return await self._render("STOCK_ISSUE_SELECTED_EMPTY")
        await self._refresh_templates()
        selected_lines = [self._templates.render("STOCK_ISSUE_SELECTED_HEADER")]
        selected_prefix = self._templates.render("SELECTED_PREFIX")
        for issue in selected:
            selected_lines.append(f"{selected_prefix} {issue}")
        return "\n".join(selected_lines)

    async def _stock_issue_value(self, draft: dict[str, Any]) -> str:
        await self._refresh_templates()
        lines = []
        details = dict(draft.get("stock_issue_sku_details", {}))
        empty_value = self._templates.render("STOCK_ISSUE_DETAIL_EMPTY_VALUE")

        for option_id in self._ordered_selected_stock_issue_ids(draft):
            sku_values = list(details.get(option_id, []))
            lines.append(
                self._templates.render(
                    "STOCK_ISSUE_DETAIL_LINE",
                    issue=await self._stock_issue_option_label(option_id),
                    sku_list=", ".join(sku_values) if sku_values else empty_value,
                )
            )

        custom_issues = list(draft.get("stock_issue_custom", []))
        if custom_issues:
            lines.append(
                self._templates.render(
                    "STOCK_ISSUE_DETAIL_LINE",
                    issue=self._templates.render("STOCK_ISSUE_CUSTOM_LABEL"),
                    sku_list=", ".join(custom_issues),
                )
            )

        if not lines:
            return "-"
        return "\n".join(lines)

    async def _stock_issue_category_values(self, draft: dict[str, Any]) -> list[str]:
        await self._refresh_templates()
        selected_ids = set(draft.get("stock_issue_option_ids", []))
        values = [
            self._templates.render(template_key)
            for option_id, template_key in STOCK_ISSUE_OPTIONS
            if option_id in selected_ids
        ]
        values.extend(draft.get("stock_issue_custom", []))
        return values

    async def _stock_issue_sku_text(self, draft: dict[str, Any]) -> str:
        current_option_id = draft["stock_issue_detail_option_id"]
        sku_values = list(dict(draft.get("stock_issue_sku_details", {})).get(current_option_id, []))
        if not sku_values:
            return await self._render("STOCK_ISSUE_SKU_EMPTY")

        await self._refresh_templates()
        lines = [self._templates.render("STOCK_ISSUE_SKU_HEADER")]
        selected_prefix = self._templates.render("SELECTED_PREFIX")
        lines.extend(f"{selected_prefix} {sku}" for sku in sku_values)
        return "\n".join(lines)

    async def _stock_issue_option_label(self, option_id: str) -> str:
        await self._refresh_templates()
        option_templates = dict(STOCK_ISSUE_OPTIONS)
        return self._templates.render(option_templates[option_id])

    def _ordered_selected_stock_issue_ids(self, draft: dict[str, Any]) -> list[str]:
        selected_ids = set(draft.get("stock_issue_option_ids", []))
        return [option_id for option_id, _ in STOCK_ISSUE_OPTIONS if option_id in selected_ids]

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

    async def _ensure_private(self, update: Update) -> bool:
        if update.effective_chat.type == ChatType.PRIVATE:
            return True
        await self._send(update, "PRIVATE_CHAT_ONLY")
        return False

    def _area_label(self, candidates: list[StoreCandidate]) -> str:
        if not candidates:
            return self._templates.render("AREA_NEAREST_FALLBACK")
        first = candidates[0].store
        area = f"{first.department_store} {first.branch}, {first.city}"
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


def _parse_sku_values(text: str) -> list[str]:
    return [value.strip() for value in text.split(",") if value.strip()]

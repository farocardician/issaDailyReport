from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from app.bot.keyboards import (
    confirm_store_keyboard,
    duplicate_keyboard,
    share_location_keyboard,
    store_list_keyboard,
    summary_keyboard,
)
from app.bot.notifications import send_admin_notification
from app.config import Settings
from app.domain.geo import haversine_meters
from app.domain.report import build_summary, generate_report_id, location_status
from app.domain.session_state import Step, next_step
from app.domain.store_matching import MatchType, StoreCandidate, StoreLocation, match_stores
from app.domain.validation import normalize_text_dash, parse_int_lenient
from app.repositories.reports import ReportsRepository
from app.repositories.sessions import SessionsRepository
from app.repositories.stores import StoresRepository
from app.repositories.templates import TemplatesRepository
from app.repositories.users import UsersRepository
from app.templates import MessageTemplates, distance_meter, store_label


NUMERIC_STEPS: dict[Step, str] = {
    Step.ASK_TRAFFIC: "traffic",
    Step.ASK_GMV: "offline_gmv",
    Step.ASK_ONLINE_GMV: "online_gmv",
    Step.ASK_ORDER: "order_count",
    Step.ASK_PIECES: "pieces_sold",
}

TEXT_STEPS: dict[Step, str] = {
    Step.ASK_NO_BUY_REASON: "no_buy_reason",
    Step.ASK_STOCK_ISSUE: "stock_issue",
    Step.ASK_NOTE: "note",
}


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
        await self._send(update, "START", reply_markup=share_location_keyboard())

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
        elif step in NUMERIC_STEPS:
            await self._handle_numeric(update, session, step)
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
            await self._send(update, "ASK_LOCATION", reply_markup=share_location_keyboard())
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
                reply_markup=confirm_store_keyboard(),
            )
            return

        if match.match_type == MatchType.MULTIPLE:
            await self._persist(update, Step.CHOOSE_STORE, draft)
            await self._send(
                update,
                "MULTIPLE_STORES_FOUND",
                area_label=_area_label(match.candidates),
                reply_markup=store_list_keyboard(match.candidates, include_other_store=True),
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
        await self._send(update, "ASK_TRAFFIC")

    async def _handle_numeric(self, update: Update, session: dict[str, Any], step: Step) -> None:
        text = _message_text(update)
        if text is None:
            await self._send(update, step.value)
            return

        try:
            value = parse_int_lenient(text)
        except ValueError:
            await self._send(update, step.value)
            return

        draft = dict(session["draft_report"])
        draft[NUMERIC_STEPS[step]] = value
        following_step = next_step(step)
        await self._persist(
            update,
            following_step,
            draft,
            selected_store_id=session["selected_store_id"],
            user_id=session["user_id"],
        )
        await self._send(update, following_step.value)

    async def _handle_text(self, update: Update, session: dict[str, Any], step: Step) -> None:
        text = _message_text(update)
        if text is None:
            await self._send(update, step.value)
            return

        draft = dict(session["draft_report"])
        draft[TEXT_STEPS[step]] = normalize_text_dash(text)
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
            await self._send(update, following_step.value)

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
            await self._send(update, "REPORT_ALREADY_EXISTS", reply_markup=duplicate_keyboard())
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
            await send_admin_notification(
                context.bot,
                self._settings.admin_chat_id,
                report,
                store,
                draft["user_name"],
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
        await self._send(update, "REPORT_SUMMARY", reply_markup=summary_keyboard(), **tokens)

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
        self._templates.update(await self._templates_repository.list_all())
        await update.effective_chat.send_message(
            text=self._templates.render(key, **tokens),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    async def _ensure_private(self, update: Update) -> bool:
        if update.effective_chat.type == ChatType.PRIVATE:
            return True
        await self._send(update, "PRIVATE_CHAT_ONLY")
        return False

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


def _area_label(candidates: list[StoreCandidate]) -> str:
    if not candidates:
        return "toko terdekat"
    first = candidates[0].store
    area = f"{first.department_store} {first.branch}, {first.city}"
    if all(
        candidate.store.department_store == first.department_store
        and candidate.store.branch == first.branch
        and candidate.store.city == first.city
        for candidate in candidates
    ):
        return area
    return f"{len(candidates)} toko terdekat"


def _message_text(update: Update) -> str | None:
    if update.message is None or update.message.text is None:
        return None
    return update.message.text

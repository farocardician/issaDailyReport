# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Dockerized Python 3.12 Telegram bot for daily per-store SPG (Sales Promotion) reports. An SPG shares their location, confirms the store, enters a PIN, answers a guided sequence of sales questions, reviews a summary, and submits. Submitting notifies an admin chat. Stack: `python-telegram-bot` (async, v21), PostgreSQL 16 via `asyncpg`, DB-backed Bahasa Indonesia UI text, and a Cloudflare named tunnel for webhook delivery.

## Commands (Docker-first)

Everything runs inside Docker Compose — there is no local virtualenv workflow. The `bot` image sets `PYTHONPATH=/app/src`, so imports are `app.*`.

- `make up` — build and start the stack (`db`, `bot`, `cloudflared`).
- `make seed` — seed `stores`, `users`, `gmv_sources`, and `ui_translate` from `Reference/*.csv` (idempotent upserts; **overwrites** live edits to seeded tables/copy).
- `make test` — run the full pytest suite in a one-off container.
- `make set-webhook` — register `WEBHOOK_BASE_URL + WEBHOOK_PATH` with Telegram (the bot also does this on boot in webhook mode).
- `make repomix` — generate `repomix-output.xml` AI handoff bundle.
- Single test: `docker compose run --rm bot pytest tests/test_store_matching.py::test_match_single_store_in_radius`
- Local debug without a tunnel: set `BOT_MODE=polling` in `.env` and `make up` (the `cloudflared` service is unused in this mode).

Tests are pure unit tests (domain + bot helpers); they touch no database or Telegram and need no running stack.

## Architecture: strict layering

The codebase enforces a one-directional dependency flow. **Respect these boundaries** — they are the main invariant of the project.

- `src/app/domain/` — **pure business rules. No Telegram imports, no database imports.** Plain dataclasses/functions, fully unit-tested. Contains `geo` (haversine), `store_matching`, `session_state` (the state machine), `report`, `validation`.
- `src/app/repositories/` — **SQL access only** (asyncpg). One class per table: `sessions`, `users`, `stores`, `reports`, `templates`.
- `src/app/bot/flow.py` — the **orchestrator** (`ReportFlow`). It is the only place that wires Telegram updates → domain decisions → repositories → replies. Handlers (`handlers.py`) are thin and delegate to `flow` via `application.bot_data["flow"]`.
- `src/app/bot/` also holds presentation helpers: `keyboards`, `notifications`, `progress`, `stock_issue_text`, plus `application.py` (DI wiring in `post_init`).
- `src/app/templates.py` — `MessageTemplates` renderer (`{{token}}` substitution). `render()` HTML-escapes tokens; `render_plain()` does not; `render_trusted()` is only for internally generated HTML tokens such as `sales_breakdown`.
- `src/app/config.py` (`Settings` via pydantic-settings, from `.env`), `db.py` (pool + schema bootstrap), `main.py` (entrypoint: webhook or polling).

When adding behavior, decide which layer owns it: **state transitions belong in `domain/session_state.py`, not in `flow.py`.** Flow only reacts to the step the domain returns.

## Domain flow (the state machine)

`bot_sessions.current_step` stores a `Step` enum value (`domain/session_state.py`). Sessions are keyed by `telegram_chat_id`, carry a JSONB `draft_report`, and expire after `SESSION_TTL_MINUTES` (checked in `flow._load_session_or_notify`).

Happy path:
`START → AWAITING_LOCATION → (CONFIRM_STORE | CHOOSE_STORE | MANUAL_STORE_SELECTION) → AWAITING_PIN → ASK_SALES_SOURCES → ASK_SALES_INPUT → REVIEW_SALES_SUMMARY → ASK_STOCK_ISSUE → ASK_NOTE → REVIEW_SUMMARY → (CONFIRM_DUPLICATE?) → DONE`

The **sales sub-flow** (steps 3 of 5, "Sumber Penjualan") replaces the old fixed traffic/GMV numeric questions:
- `ASK_SALES_SOURCES` — inline multi-select of configurable sources from `gmv_sources`. When nothing is selected it shows `Tidak Ada Penjualan`; after a source is selected that button is hidden and the continue button becomes `Lanjut input {{source}}`.
- `ASK_SALES_INPUT` — one step that loops `(source, field)` per `domain.sales_sources.input_plan`. A source with `requires_traffic` asks traffic + GMV + order + pieces; others ask GMV + order + pieces. Position is tracked by `draft["sales_input_plan"]` / `sales_input_pos`; buttons are `Sebelumnya` and `Batal`.
- `REVIEW_SALES_SUMMARY` — reply-keyboard summary (Lanjutkan / Ubah / Batal). `Ubah` opens `EDIT_SALES_MENU`: edit one source's fields, or "Tambah / Hapus Sumber Penjualan" (re-opens the picker preselected, collecting input only for newly-added sources).

Per-source values live in `draft["sales_data"]` (`{source_id: {label, source_type, requires_traffic, sort_order, traffic?, gmv, order_count, pieces_sold}}`). On submit, each becomes a `daily_report_sales` row with the label/type/flags **snapshotted**; totals are always computed from rows via `domain.sales_sources.sales_totals` (no aggregate columns on `daily_reports`).

Store matching (`domain/store_matching.py`): haversine distance vs. an *effective radius* (`store.allowed_radius_meter` or `DEFAULT_RADIUS_METER`; a non-positive radius falls back to default). Result is `SINGLE` (1 in range → confirm), `MULTIPLE` (>1 → pick from list), or `NONE` (0 → returns all active stores sorted by distance for manual selection). `location_status` is `in_radius` / `out_of_radius` / `manual_store_selection` (the last when distance is unknown).

The **stock-issue sub-flow** is the most intricate part of `flow.py`: it stays on `ASK_STOCK_ISSUE` while toggling multi-select issue categories, collecting free-text "other" issues, then walking per-category SKU detail prompts. State for this lives entirely in `draft_report` keys (`stock_issue_option_ids`, `stock_issue_sku_details`, `stock_issue_detail_option_id`, …) and is stripped out by `_save_stock_issue_and_continue` before advancing.

Duplicate handling: re-submitting the same `store_id` + `report_date` routes to `CONFIRM_DUPLICATE`; confirming writes a **second** `daily_reports` row with `submission_status = 'correction'` (vs. `'submitted'`). Cancelled sessions show a `Mulai` button to restart. Report IDs are `RPT-YYYYMMDD-HHMMSS-NNNN`, regenerated up to 10× on collision.

## UI text: the `ui_translate` table

All user-facing strings — prompts, button labels, store/area/distance formats, stock-issue labels, location-status labels, admin notifications, progress indicators — are **DB rows in `ui_translate`**, not hardcoded. Code references stable `key`s; `flow` re-fetches templates on nearly every send (`_refresh_templates`) so admins can edit copy live in the DB.

- Seeded from `Reference/ui_translate.csv` (two columns: `key,message`; `\n` in the CSV becomes a real newline). `category` is auto-derived from the key prefix in `seed._template_category`.
- `message` supports Telegram HTML tags and `{{token}}` placeholders.
- **Do not rename a `key`** unless you also update every code reference. To add user-facing text, add a `ui_translate` key + a `Reference/ui_translate.csv` row — never inline a Bahasa Indonesia string in code.
- `make seed` restores CSV values, discarding live DB edits.

## Database / schema conventions

There is no migration tool. `sql/schema.sql` **is** the migration and must stay idempotent and re-runnable: it uses `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS` / `DROP COLUMN IF EXISTS`, and `DO $$ … $$` blocks (e.g. the `message_templates → ui_translate` rename). `db.bootstrap_schema` applies it on every bot startup and during seeding, then runs additional idempotent `ALTER`s (dropping NOT NULL on location columns, refreshing the `location_status` CHECK constraint). Any schema change must follow this idempotent, forward-only style.

Tables: `stores`, `users` (holds PINs), `daily_reports` (header only — sales lives in the child table), `daily_report_sales` (one row per sales source, with snapshot columns), `gmv_sources` (configurable sales-source list; `requires_traffic`, `sort_order`, `status`; seeded from `Reference/gmv_sources.csv`), `bot_sessions`, `ui_translate`. Postgres is exposed only on `127.0.0.1:${POSTGRES_HOST_PORT}` (default `55432`) for local DB tools.

## Testing approach

`pytest` in `tests/` covers the pure domain modules and stateless bot helpers (`progress`, `stock_issue_text`, `sales_text`, `keyboards`, `templates`) plus flow-level tests (`location_flow`, `sales_flow`). Domain/helper tests construct objects directly and assert on returned `Step`/`MatchType`/strings. Flow tests exercise the async `ReportFlow` via in-memory fakes (`_FakeSessions`, `_FakeSalesSources`, `_FakeChat`, fake `Update`/`CallbackQuery`) and `asyncio.run` — no Telegram, no DB. Keep new domain logic testable this way: free functions and frozen dataclasses, no I/O.

## Safe-change rules

- Run all implementation, test, and seed commands through Docker Compose.
- Keep `domain/` free of Telegram and DB imports; keep SQL only in `repositories/`; keep orchestration only in `flow.py`.
- Put step transitions in `domain/session_state.py`, not in `flow.py`.
- Add/adjust user-facing copy via `ui_translate` + `Reference/ui_translate.csv`, preserving the Bahasa Indonesia flow.
- `Reference/*.csv` are seed inputs the app never writes back to. `Reference/user_master.csv` contains PINs and is intentionally excluded from the repomix bundle — never add it to `repomix.config.json` includes.
- Never commit `.env`, Telegram tokens, the Cloudflare tunnel token, PIN changes, or database dumps.

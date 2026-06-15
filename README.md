# SPG Daily Store Reporting Telegram Bot

A Dockerized Telegram bot that lets in-store SPG (Sales Promotion) staff submit a daily sales report for their store in a few guided steps. The bot confirms the staff member's store by GPS location, verifies a PIN, walks them through a short set of questions, shows a summary to confirm, and notifies an admin chat once the report is submitted.

**Built with:** Python 3.12 · [python-telegram-bot](https://python-telegram-bot.org/) (async) · PostgreSQL 16 · Docker Compose · Cloudflare Tunnel

> Looking for architecture internals and contribution rules? See [`CLAUDE.md`](./CLAUDE.md).

---

## Table of Contents

1. [How it works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Quick start](#quick-start)
4. [Configuration](#configuration)
5. [Make commands](#make-commands)
6. [Cloudflare tunnel setup](#cloudflare-tunnel-setup)
7. [Editing the bot's text (`ui_translate`)](#editing-the-bots-text-ui_translate)
8. [Testing the bot in Telegram](#testing-the-bot-in-telegram)
9. [Running the test suite](#running-the-test-suite)
10. [Database access (DBeaver)](#database-access-dbeaver)
11. [Verification SQL](#verification-sql)
12. [Repomix handoff](#repomix-handoff)
13. [Project layout](#project-layout)

---

## How it works

From the SPG's point of view, submitting a report looks like this:

1. **Start** — DM the bot and send `/start`.
2. **Share location** — the bot matches GPS coordinates against active stores within an allowed radius.
   - One match → confirm the store.
   - Several matches → pick from a list.
   - No match → choose the store manually.
3. **Enter PIN** — identifies the staff member.
4. **Input sales by source** — choose sales sources such as Outlet, Whatsapp, Shopee, Tokopedia, Tiktok, or Website, then enter GMV, orders, pieces, and traffic where required.
5. **Stock issues & note** — pick any stock problems, type the affected SKUs for each selected issue, or tap **Tidak Ada**, then add an optional note. On a SKU prompt, type **Tidak Ada** or `-` when there is no specific SKU.
6. **Review & submit** — the bot shows a summary; the SPG confirms.
7. **Admin notified** — a formatted summary is sent to the admin chat.

Submitting a report for a store/date that already has one is allowed: it is saved as a **correction** rather than overwriting the original. If the SPG cancels, the bot shows a **Mulai** button to start again.

---

## Prerequisites

- **Docker** and **Docker Compose** (everything runs in containers — no local Python setup needed).
- A **Telegram bot token** from [@BotFather](https://t.me/BotFather).
- Your **admin chat ID** (the chat that receives report notifications).
- For production webhook delivery: a **Cloudflare Tunnel** (see [setup below](#cloudflare-tunnel-setup)). For local development you can skip this with polling mode.

---

## Quick start

```sh
# 1. Create your environment file
cp .env.example .env
# then edit .env and fill in the required values (see Configuration)

# 2. Build and start the stack (database + bot + tunnel)
make up

# 3. Seed stores, users, sales sources, and UI text
make seed
```

The bot is now running. To develop locally **without** a Cloudflare tunnel, set `BOT_MODE=polling` in `.env` before `make up`.

---

## Configuration

Copy `.env.example` to `.env` and fill in the values below.

### Required

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather. |
| `ADMIN_CHAT_ID` | Chat ID that receives report notifications. |
| `WEBHOOK_BASE_URL` | Public HTTPS URL of the bot (used in `webhook` mode). |
| `WEBHOOK_SECRET` | Random secret Telegram includes with each webhook call. |
| `CLOUDFLARE_TUNNEL_TOKEN` | Token for the Cloudflare named tunnel (`webhook` mode). |

### Optional / defaults

| Variable | Default | Description |
| --- | --- | --- |
| `BOT_MODE` | `webhook` | `webhook` for production, `polling` for tunnel-free local dev. |
| `DATABASE_URL` | `postgresql://spg:spg@db:5432/spg` | Postgres connection string. |
| `WEBHOOK_PATH` | `/telegram/webhook` | Path Telegram posts updates to. |
| `WEBHOOK_LISTEN_PORT` | `8080` | Internal port the bot listens on. |
| `DEFAULT_RADIUS_METER` | `100` | Allowed distance to a store when it has no radius set. |
| `ACTIVE_STATUS` | `Aktif` | Status value treated as "active" for stores and users. |
| `SESSION_TTL_MINUTES` | `30` | How long an in-progress report session stays valid. |
| `APP_TZ` | `Asia/Jakarta` | Timezone for report dates and timestamps. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `spg` | Database credentials. |
| `POSTGRES_HOST_PORT` | `55432` | Localhost port for connecting DB tools (see [Database access](#database-access-dbeaver)). |

---

## Make commands

| Command | What it does |
| --- | --- |
| `make up` | Build and start the full stack (`db`, `bot`, `cloudflared`). |
| `make seed` | Load stores, users, sales sources, and UI text from `Reference/*.csv`. **Overwrites** live edits to seeded copy/config. |
| `make test` | Run the test suite in a throwaway container. |
| `make set-webhook` | Register the webhook URL with Telegram (the bot also does this on boot in webhook mode). |
| `make repomix` | Generate the `repomix-output.xml` AI handoff bundle. |

Run a **single test**:

```sh
docker compose run --rm bot pytest tests/test_store_matching.py::test_match_single_store_in_radius
```

---

## Cloudflare tunnel setup

In `webhook` mode, Telegram needs a public HTTPS URL. A Cloudflare named tunnel provides one without exposing your server directly.

1. In **Cloudflare Zero Trust**, create a Cloudflared tunnel named `vizu-spg-bot`.
2. Copy the tunnel token into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
3. Add a **public hostname** to the tunnel:
   - **Hostname:** `bot.yourdomain.com`
   - **Service:** `HTTP`
   - **URL:** `bot:8080`
4. Set `WEBHOOK_BASE_URL=https://bot.yourdomain.com` in `.env`.
5. Run `make up`. The bot registers `WEBHOOK_BASE_URL + WEBHOOK_PATH` with Telegram on startup.
6. Verify the webhook is registered:

   ```sh
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   ```

---

## Editing the bot's text (`ui_translate`)

All fixed bot wording — prompts, button labels, store/area/distance formats, stock-issue prompts, location-status labels, and admin notifications — lives in the **`ui_translate`** database table (seeded from `Reference/ui_translate.csv`). Configurable list labels live in their own tables: sales sources in **`gmv_sources`** (`Reference/gmv_sources.csv`) and stock issues in **`stock_issues`** (`Reference/stock_issues.csv`).

After seeding, edit the text directly in the `ui_translate` table with any database client. Running `make seed` again restores the values from the CSV.

Column reference:

| Column | Notes |
| --- | --- |
| `key` | Stable code key. **Do not change** unless the code is updated too. |
| `category` | Grouping for filtering/admin screens. |
| `message` | The editable text. Supports Telegram HTML tags and `{{token}}` placeholders. |
| `description` | Optional admin note. |
| `updated_at` | Maintained automatically when a row changes. |

> The table is structured for a future admin CRUD page, so the `category` and `description` columns exist even though copy is edited directly in the DB for now.

---

## Testing the bot in Telegram

1. DM the bot and send `/start`.
2. Share your location.
3. Confirm or choose the store.
4. Enter PIN `123123` (the seeded test PIN).
5. Choose sales sources and fill in each requested value.
6. Pick any stock issues, type affected SKUs for each issue, or tap **Tidak Ada**. On a SKU prompt, type **Tidak Ada** or `-` if there is no specific SKU, then add a note.
7. Submit.

Submitting again for the **same store and date** creates a second report with `submission_status = correction`.

---

## Running the test suite

The tests are fast, pure unit tests — they don't need a running bot or database.

```sh
make test
```

They cover the business logic (location matching, the step state machine, validation, report building) and the stateless UI helpers.

---

## Database access (DBeaver)

Postgres is published only on `localhost`, so local tools can connect while the database stays private.

| Setting | Value |
| --- | --- |
| Driver | `PostgreSQL` |
| Host | `localhost` |
| Port | `POSTGRES_HOST_PORT` from `.env` (default `55432`) |
| Database | `POSTGRES_DB` |
| Username | `POSTGRES_USER` |
| Password | `POSTGRES_PASSWORD` |

To edit bot copy, open the `ui_translate` table and edit the `message` column. Keep `key` stable — the code references those keys.

---

## Verification SQL

Check submitted reports and any active sessions:

```sql
SELECT report_id, store_id, report_date, submission_status, location_status, distance_from_store_meter
FROM daily_reports
ORDER BY created_at DESC;

SELECT * FROM daily_report_sales
ORDER BY report_id, sort_order;

SELECT current_step FROM bot_sessions;
```

---

## Repomix handoff

Generate an AI-friendly bundle of the repository for bug fixing or feature work:

```sh
make repomix
```

This uses `repomix.config.json` and writes `repomix-output.xml` (ignored by git). `Reference/user_master.csv` is intentionally excluded because it can contain PINs and personal contact data.

---

## Project layout

| Path | Purpose |
| --- | --- |
| `src/app/domain/` | Pure business rules (location matching, step flow, validation) — no Telegram or database code. |
| `src/app/repositories/` | Database access, one class per table. |
| `src/app/bot/flow.py` | Wires Telegram updates, business decisions, the database, and replies together. |
| `src/app/bot/` | Telegram handlers, keyboards, progress indicators, and notifications. |
| `sql/schema.sql` | Database schema, applied idempotently on startup and during seeding. |
| `Reference/*.csv` | Seed inputs (stores, users, sales sources, stock issues, UI text). The app never writes back to these. |
| `tests/` | Unit tests for the domain logic and UI helpers. |

For the full architecture, the report state machine, and contribution rules, see [`CLAUDE.md`](./CLAUDE.md).

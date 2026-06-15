# SPG Daily Store Reporting Telegram Bot

Dockerized Python 3.12 Telegram bot for daily per-store SPG reports. The app uses `python-telegram-bot` in async mode, PostgreSQL 16 via `asyncpg`, DB-backed Bahasa Indonesia message templates, and a Cloudflare named tunnel for webhook access.

## Structure

- `src/app/domain/` contains pure business rules and unit tests.
- `src/app/repositories/` contains SQL access only.
- `src/app/bot/flow.py` wires Telegram updates, domain decisions, repositories, and replies.
- `Reference/*.csv` are the seed inputs and are not modified by the app.
- `sql/schema.sql` is applied idempotently on bot startup and by the seed script.
- Bot prompts, button labels, store/area/distance display formats, stock issue labels, location status labels, and admin notification text are stored in `ui_translate` and seeded from `Reference/ui_translate.csv`.

## Setup

1. Copy `.env.example` to `.env`.
2. Fill `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`, `WEBHOOK_BASE_URL`, `WEBHOOK_SECRET`, and `CLOUDFLARE_TUNNEL_TOKEN`.
3. Start the stack:

```sh
make up
```

4. Seed stores, users, and message templates:

```sh
make seed
```

After seeding, copy can be edited directly in the `ui_translate` table with a database client. Running `make seed` again restores values from `Reference/ui_translate.csv`.

The `ui_translate` table is designed for a future admin CRUD page:

- `key`: stable code key, do not edit unless the code is updated too.
- `category`: grouping for admin screens and DB filtering.
- `message`: editable text/template. Telegram HTML tags and `{{token}}` placeholders are supported.
- `description`: optional admin note.
- `updated_at`: maintained automatically when a row changes.

5. Run pure domain tests:

```sh
make test
```

For zero-tunnel debugging, set `BOT_MODE=polling` in `.env` and run the bot service without Cloudflare webhook routing.

## Cloudflare Named Tunnel

1. In Cloudflare Zero Trust, create a Cloudflared tunnel named `vizu-spg-bot`.
2. Copy the tunnel token into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
3. Add a public hostname on the tunnel:
   - Hostname: `bot.yourdomain.com`
   - Service: `HTTP`
   - URL: `bot:8080`
4. Set `WEBHOOK_BASE_URL=https://bot.yourdomain.com`.
5. Run `make up`; the bot registers `WEBHOOK_BASE_URL + WEBHOOK_PATH` with Telegram on boot.
6. Verify Telegram webhook info:

```sh
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

## Telegram Test Flow

DM the bot, send `/start`, share location, confirm or choose store, enter PIN `123123`, fill each report field, then submit. Re-submitting the same store/date creates a second report with `submission_status=correction`.

## Verification SQL

```sql
SELECT report_id, store_id, report_date, submission_status, location_status, distance_from_store_meter
FROM daily_reports
ORDER BY created_at DESC;

SELECT current_step FROM bot_sessions;
```

## DBeaver Database Access

The Postgres service is exposed only on localhost for local DB tools.

Use these DBeaver settings:

- Driver: `PostgreSQL`
- Host: `localhost`
- Port: value of `POSTGRES_HOST_PORT` from `.env`, default `55432`
- Database: value of `POSTGRES_DB`
- Username: value of `POSTGRES_USER`
- Password: value of `POSTGRES_PASSWORD`

For template editing, open table `ui_translate`. Edit the `message` column; keep `key` stable because the bot references those keys from code.

## Repomix Handoff

Generate an AI-friendly repository bundle for bug fixing or feature development:

```sh
make repomix
```

This uses `repomix.config.json` and writes `repomix-output.xml`. The output is ignored by git.
`Reference/user_master.csv` is intentionally excluded from the pack because it can contain PINs and personal contact data.

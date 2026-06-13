# SPG Daily Store Reporting — Telegram Bot

## Context

SPG (sales promotion) staff need a frictionless way to file a daily per-store sales report from their phone. The system must identify which store they're in from a shared GPS location, authenticate them by PIN, walk them through the report fields one at a time, persist everything to PostgreSQL, and notify an admin. Today there is no system — only reference CSVs (`Reference/*.csv`) describing the intended data shapes and the exact Bahasa Indonesia bot copy.

This plan builds that system as a **dockerized Python app** so it runs identically on the dev laptop and on a VPS, with business rules cleanly separated from Telegram handling and DB persistence. Local testing is exposed to Telegram via a **named Cloudflare Tunnel** (the same mechanism we'll reuse on the VPS).

**Decisions (confirmed with user):**
- Stack: **Python 3.12 + python-telegram-bot v21 (async) + asyncpg + PostgreSQL 16**.
- Connectivity: **webhook mode** behind a **named Cloudflare Tunnel** (cloudflared as a compose service). A `polling` fallback is included via env toggle for zero-tunnel debugging.
- Admin notification: a single **`ADMIN_CHAT_ID`** in `.env`.
- Bot language: **Bahasa Indonesia**, driven by `message_template.csv` (DB-backed, editable without redeploy).

---

## Tech stack & key libraries

- `python-telegram-bot==21.*` — Telegram client + built-in aiohttp webhook server (`Application.run_webhook`).
- `asyncpg` — fast async PostgreSQL driver; thin repository layer (no heavy ORM, keeps it readable).
- `pydantic-settings` — typed config from env.
- Schema applied from a plain `sql/schema.sql` (idempotent `CREATE TABLE IF NOT EXISTS`) run on startup — no Alembic, transparent and easy to maintain.
- `pytest` — unit tests for the pure domain layer.

---

## Project structure

```
DailyReport/
  docker-compose.yml          # db + bot + cloudflared
  Dockerfile                  # python:3.12-slim app image
  .env.example                # all config keys, documented
  .dockerignore
  requirements.txt
  README.md                   # setup + Cloudflare guide (mirrors this plan)
  Makefile                    # up / seed / test / set-webhook helpers
  Reference/                  # EXISTING seed CSVs (unchanged)
  sql/
    schema.sql                # all tables, indexes
  src/app/
    main.py                   # entrypoint: load config, run schema, build app, run webhook|polling
    config.py                 # pydantic-settings Settings
    logging_setup.py
    db.py                     # asyncpg pool + schema bootstrap
    templates.py              # load message_templates, render {{tokens}}
    domain/                   # PURE business rules (no telegram, no db) — unit-tested
      geo.py                  # haversine_meters()
      store_matching.py       # match_stores() -> SINGLE | MULTIPLE | NONE + candidates
      validation.py           # parse_int_lenient(), normalize_text_dash()
      report.py               # generate_report_id(), build_summary(), location_status()
      session_state.py        # Step enum + allowed transitions
    repositories/             # SQL only
      stores.py  users.py  reports.py  sessions.py  templates.py
    bot/
      application.py          # build PTB Application, register handlers, webhook/polling
      handlers.py             # update -> dispatch by session step
      keyboards.py            # share-location, confirm, store-list, summary, duplicate
      flow.py                 # orchestrates step transitions (calls domain + repos)
      notifications.py        # format + send admin notification
    scripts/
      seed.py                 # load Reference/*.csv -> stores, users, message_templates
  tests/
    test_geo.py  test_store_matching.py  test_validation.py  test_report.py
```

**Layering contract:** `domain/*` imports nothing from `bot/` or `repositories/` (pure functions, fully unit-testable). `bot/flow.py` is the only place that wires domain decisions to repository calls and Telegram replies.

---

## Database schema (`sql/schema.sql`)

Column names normalized to snake_case English; status values kept as-is from CSV (`Aktif`).

| Table | Key columns |
|---|---|
| `stores` | `store_id` PK text, `department_store`, `branch`, `city`, `brand`, `latitude` double precision, `longitude` double precision, `allowed_radius_meter` int, `status` text, `notes` text |
| `users` | `user_id` PK text, `role`, `name`, `phone`, `email`, `pin` text, `telegram_user_id` bigint, `telegram_chat_id` bigint, `status` text, `notes` text |
| `daily_reports` | `report_id` PK text, `report_date` date, `store_id` FK→stores, `user_id` FK→users, `traffic` int, `offline_gmv` numeric, `online_gmv` numeric, `order_count` int, `pieces_sold` int, `no_buy_reason` text, `stock_issue` text, `submitted_latitude` double precision, `submitted_longitude` double precision, `distance_from_store_meter` numeric, `note` text, `submission_status` text (`submitted`\|`correction`), `location_status` text (`in_radius`\|`out_of_radius`), `created_at` timestamptz default now() |
| `bot_sessions` | `telegram_chat_id` bigint PK, `telegram_user_id` bigint, `current_step` text, `selected_store_id` text, `user_id` text, `draft_report` jsonb, `updated_at` timestamptz, `expires_at` timestamptz |
| `message_templates` | `key` text PK, `message` text |

Indexes: `daily_reports(store_id, report_date)` (duplicate lookup), `daily_reports(report_date)`.
**No unique constraint** on `(store_id, report_date)` — corrections are additional rows, not overwrites (per business rule).

---

## Seeding (`scripts/seed.py`)

Idempotent `INSERT ... ON CONFLICT DO UPDATE` for all three masters from `Reference/`:
- `store_master.csv` → `stores` (map `Allowed_Radius_Meter`; coerce blank → null so the 100m default applies later).
- `user_master.csv` → `users` (blank Telegram IDs → null).
- `message_template.csv` → `message_templates`; **convert the literal `\n` in the CSV to real newlines** on load.

Run via `make seed` (`docker compose run --rm bot python -m app.scripts.seed`). `message_templates` is treated as config and re-seeded on every run; masters upsert without clobbering operator edits beyond the CSV columns.

---

## Domain layer (pure, unit-tested)

**`geo.haversine_meters(lat1, lon1, lat2, lon2)`** — standard Haversine, returns meters.

**`store_matching.match_stores(lat, lon, active_stores)`** →
1. effective radius per store = `allowed_radius_meter` or `DEFAULT_RADIUS_METER` (100) if null/≤0.
2. consider only active stores with valid (non-null) coordinates.
3. compute distance to each; `in_range` = distance ≤ effective radius.
4. **exactly 1 in range → `SINGLE`** (→ confirm). **>1 in range → `MULTIPLE`** (→ choose). **0 in range → `NONE`** (→ manual selection, list all active stores sorted by distance).
   - Returns the candidate list (with distances) so the bot can render buttons and store the chosen distance.
   - Note: the two seed stores share coordinates with 500m radius → real `MULTIPLE` path.

**`report.location_status(distance, effective_radius)`** → `in_radius` if `distance ≤ radius` else `out_of_radius`. Out-of-radius submissions are still allowed (flagged, never blocked).

**`validation.parse_int_lenient(text)`** — strip thousand separators (`.`, `,`, spaces), parse int; reject if anything non-digit remains or empty (so `500.000` → `500000`, friendly for Indonesian input). Used for traffic, offline GMV, online GMV, order count, pieces.

**`validation.normalize_text_dash(text)`** — text fields accept any string; a bare `-` is stored as the literal "no issue/no note" marker.

**`report.generate_report_id(now)`** → `RPT-YYYYMMDD-HHMMSS-<4 random digits>` (matches sample; PK-collision retry).

**`session_state.Step`** enum + `next_step()` map (see flow below).

Timestamps/`report_date` use `APP_TZ` (default `Asia/Jakarta`).

---

## Session state machine (`bot_sessions.current_step`)

One row per `telegram_chat_id`. Each inbound update loads the session, dispatches by `current_step`, mutates `draft_report`/step, bumps `updated_at` + `expires_at`.

```
START
  └─(/start)→ AWAITING_LOCATION  [send share-location keyboard]
AWAITING_LOCATION
  └─(location)→ match_stores →
        SINGLE   → CONFIRM_STORE
        MULTIPLE → CHOOSE_STORE
        NONE     → MANUAL_STORE_SELECTION
CONFIRM_STORE        (yes→AWAITING_PIN | no→MANUAL_STORE_SELECTION)
CHOOSE_STORE         (pick store_id → AWAITING_PIN)
MANUAL_STORE_SELECTION (pick store_id → AWAITING_PIN; compute distance to chosen)
AWAITING_PIN         (PIN matches exactly 1 active user → persist telegram_user_id/chat_id → ASK_TRAFFIC; else PIN_INVALID, re-ask)
ASK_TRAFFIC → ASK_GMV → ASK_ONLINE_GMV → ASK_ORDER → ASK_PIECES
  (numeric; invalid → re-ask same step)
ASK_NO_BUY_REASON → ASK_STOCK_ISSUE → ASK_NOTE
  (text; "-" allowed)
  → REVIEW_SUMMARY   [send summary + Submit/Cancel/Restart buttons]
REVIEW_SUMMARY
  ├ Submit → duplicate check (store_id + report_date):
  │     exists → CONFIRM_DUPLICATE  [Ya, koreksi / Batal]
  │     none   → save (submission_status=submitted) → DONE
  ├ Restart → reset → AWAITING_LOCATION
  └ Cancel  → cancel session
CONFIRM_DUPLICATE (Ya → save submission_status=correction → DONE | Batal → cancel)
DONE → reset session; send SUBMIT_SUCCESS to user; send admin notification
```

**Cross-cutting rules:**
- **Private chat only**: non-private chat → `PRIVATE_CHAT_ONLY`, no session work.
- **`/start`** always resets the session and restarts.
- **`/cancel`** (and Cancel buttons) cancel anytime → `CANCELLED`.
- **Expiry**: if `now > expires_at`, reset and tell user to `/start` (configurable `SESSION_TTL_MINUTES`, default 30).
- **No location re-prompt**: location is only consumed in `AWAITING_LOCATION`; once past it, a stray location is ignored gracefully — the flow never loops back to ask again.
- Unrecognized input in a given step → `UNKNOWN_COMMAND` hint, stay on step.

---

## Telegram bot layer

- **`templates.py`** — loads `message_templates` into memory; `render(key, **tokens)` replaces `{{token}}`; all sends use `parse_mode=HTML`. `store_label` = `"{brand} – {department_store} {branch}, {city}"`; `distance_meter` formatted like `"120 m"`.
- **`keyboards.py`** — share-location `ReplyKeyboardMarkup(KeyboardButton(request_location=True))`; inline yes/no for confirm; inline store list (callback `store:<id>`); inline `Submit/Restart/Cancel`; inline duplicate `Ya, koreksi / Batal`.
- **`handlers.py`** — one `MessageHandler` (text+location), one `CommandHandler` (`/start`,`/cancel`), one `CallbackQueryHandler`; all delegate to `flow.py`.
- **`notifications.py`** — on `DONE`, send to `ADMIN_CHAT_ID`: store label, user name, date, traffic, offline+online GMV, order, pieces, no-buy reason, stock issue, note, distance, **location status**, and a clear **`⚠️ KOREKSI`** banner when `submission_status=correction`.

---

## Config (`.env.example`)

```
TELEGRAM_BOT_TOKEN=
ADMIN_CHAT_ID=
DATABASE_URL=postgresql://spg:spg@db:5432/spg
BOT_MODE=webhook                 # webhook | polling
WEBHOOK_BASE_URL=https://bot.yourdomain.com   # your named-tunnel hostname
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=change-me-random  # validated as Telegram secret_token
WEBHOOK_LISTEN_PORT=8080
DEFAULT_RADIUS_METER=100
ACTIVE_STATUS=Aktif
SESSION_TTL_MINUTES=30
APP_TZ=Asia/Jakarta
CLOUDFLARE_TUNNEL_TOKEN=         # for the cloudflared compose service
```

---

## Docker

**`Dockerfile`** — `python:3.12-slim`, install `requirements.txt`, copy `src/`, `sql/`, `Reference/`; `CMD ["python","-m","app.main"]`.

**`docker-compose.yml`** — three services on one network:
- `db`: `postgres:16`, volume `pgdata`, healthcheck, `POSTGRES_*` from env.
- `bot`: builds Dockerfile, depends_on db healthy, env from `.env`, exposes `8080` internally (no host port needed in webhook mode), runs schema bootstrap then the app.
- `cloudflared`: `cloudflare/cloudflared:latest`, command `tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}`. The tunnel's public-hostname→service mapping (`bot.yourdomain.com` → `http://bot:8080`) is configured in the Cloudflare Zero Trust dashboard when the tunnel is created.

On startup `main.py`: bootstrap schema → if `BOT_MODE=webhook`, `run_webhook(listen=0.0.0.0, port=8080, url_path=WEBHOOK_PATH, webhook_url=WEBHOOK_BASE_URL+WEBHOOK_PATH, secret_token=WEBHOOK_SECRET)` (PTB registers the webhook with Telegram automatically); else `run_polling()`.

---

## Cloudflare named tunnel — step by step (local testing → VPS-ready)

> Prerequisite: a domain whose DNS is managed by Cloudflare (free plan is fine). If you don't have one yet, you can temporarily run a quick tunnel — `cloudflared tunnel --url http://localhost:8080` — and set `WEBHOOK_BASE_URL` to the printed `*.trycloudflare.com` URL with `BOT_MODE=webhook`; the steps below are the durable setup.

1. **Create the tunnel (dashboard, gives a token):** Cloudflare dashboard → **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**. Name it `vizu-spg-bot`. Copy the **tunnel token** → paste into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
2. **Add a public hostname** on that tunnel: **Hostname** = `bot.yourdomain.com`, **Service** = `HTTP` → `bot:8080` (the compose service name + internal port). Save. Cloudflare auto-creates the DNS record.
3. **Set `.env`:** `WEBHOOK_BASE_URL=https://bot.yourdomain.com`, fill `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID`, and a random `WEBHOOK_SECRET`.
4. **Start everything:** `make up` (`docker compose up -d --build`). The `cloudflared` container connects the tunnel; the `bot` container registers the webhook with Telegram on boot.
5. **Seed data:** `make seed`.
6. **Verify the tunnel** is "Healthy" in the dashboard, and check the webhook: `curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"` should show your URL with no errors.
7. **Test in Telegram:** DM the bot → `/start` → share location → confirm/choose store → enter PIN `123123` → fill fields → submit. Admin chat receives the notification.

**Moving to the VPS later:** copy the repo + `.env`, run `make up` + `make seed`. The same tunnel/hostname keeps working (or create a second tunnel for prod); no Telegram-side change needed beyond `WEBHOOK_BASE_URL`.

---

## Verification

1. **Unit tests (pure rules):** `make test` → `pytest`. Cover Haversine accuracy, `match_stores` SINGLE/MULTIPLE/NONE (incl. the identical-coords seed case), radius-default fallback, `parse_int_lenient` (`"500.000"`→500000, reject `"abc"`), `location_status`, `report_id` format.
2. **DB up + seed:** `docker compose up -d db`, `make seed`, then `psql` (or `docker compose exec db psql -U spg -d spg`) — confirm `stores` has 2 rows, `users` has the admin, `message_templates` populated with real newlines.
3. **End-to-end via Telegram** (steps 4–7 above): walk the full flow.
4. **Inspect persistence:**
   - `SELECT report_id, store_id, report_date, submission_status, location_status, distance_from_store_meter FROM daily_reports ORDER BY created_at DESC;`
   - Re-submit same store/date → confirm a **second** row with `submission_status=correction` (old row intact).
   - `SELECT current_step FROM bot_sessions;` → row reset/cleared after `DONE`.
5. **Out-of-radius check:** submit from coordinates >radius (or pick a store manually) → report saved with `location_status=out_of_radius`; admin notification shows the warning.
6. **Admin notification:** confirm `ADMIN_CHAT_ID` receives the formatted message, with the `⚠️ KOREKSI` banner on corrections.

---

## Deliverables checklist

- [ ] `sql/schema.sql`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `.dockerignore`, `Makefile`
- [ ] `src/app/`: `main.py`, `config.py`, `logging_setup.py`, `db.py`, `templates.py`
- [ ] `src/app/domain/`: `geo.py`, `store_matching.py`, `validation.py`, `report.py`, `session_state.py`
- [ ] `src/app/repositories/`: `stores.py`, `users.py`, `reports.py`, `sessions.py`, `templates.py`
- [ ] `src/app/bot/`: `application.py`, `handlers.py`, `keyboards.py`, `flow.py`, `notifications.py`
- [ ] `src/app/scripts/seed.py`
- [ ] `tests/`: domain unit tests
- [ ] `README.md` with the Cloudflare guide

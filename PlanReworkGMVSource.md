# Configurable Sales-Source Flow

## Context

Today, after PIN verification, the bot runs a fixed numeric flow — `ASK_TRAFFIC → ASK_GMV (offline) → ASK_ONLINE_GMV → ASK_ORDER → ASK_PIECES` — and writes those five numbers as NOT NULL columns on `daily_reports`. This hard-codes the sales model (one offline + one online bucket) and can't represent per-channel sales (Outlet, WhatsApp, Shopee, Tokopedia, Tiktok, Website).

We are replacing that step with a **configurable, source-by-source sales flow**. Sales sources become editable business data in a new `gmv_sources` table (admins add/rename/reorder/disable without code changes). Each report stores a per-source breakdown in a new `daily_report_sales` child table; all totals are computed from those rows. Because this is a pilot, we **drop** the old `traffic/offline_gmv/online_gmv/order_count/pieces_sold/no_buy_reason` columns rather than keep them for backward compatibility — `daily_reports` becomes a header table only.

Confirmed decisions (from the user):
- **Normalized storage**, no backward-compat with old columns.
- **Source labels live in `gmv_sources`** (single source of truth); `ui_translate` holds only fixed bot copy (prompts, buttons, headings). `daily_report_sales` carries **snapshots** of `source_label/source_type/requires_traffic/sort_order` (captured during the session, written at submit), so later config changes never rewrite history.
- **Removing a source is soft-disable only.** Admins disable a source by setting `gmv_sources.status = 'Nonaktif'`; the picker only lists active sources. Config rows are never hard-deleted — the `daily_report_sales → gmv_sources` FK plus the snapshot columns keep historical reports intact and readable. (This is distinct from the report-scoped "Hapus" in the edit menu below, which only changes the *current* report's selection.)
- **"Tidak Ada Penjualan"** is a fixed flow action, never a `gmv_sources` row; if chosen, no sales rows are written, a `sales_no_sales` flag is set, and the flow continues straight to Kendala/Catatan. The **final review and admin notification** still explicitly render "Tidak Ada Penjualan" with totals = 0 (the *mid-flow* sales summary screen is skipped, per the original requirement).
- **All sales numeric inputs** (traffic, GMV, order count, pieces) accept lenient thousand separators but must be **non-negative integers** — reused `parse_int_lenient` already rejects negative, empty, and non-numeric input.
- **"Ubah"** opens an edit menu: pick one source to re-enter just its fields, **or** "Tambah / Hapus Sumber Penjualan" to return to the picker with current selections preselected — keeping entered values for sources that stay selected, collecting input only for newly added sources, and dropping draft values for sources removed from the selection.

All architecture rules from `CLAUDE.md` hold: pure `domain/`, SQL only in `repositories/`, orchestration only in `flow.py`, transitions in the domain state machine, all copy DB-backed via `ui_translate`, idempotent schema, Docker-first.

---

## Data model & schema (`sql/schema.sql`, idempotent)

**New `gmv_sources` (config table):**
```sql
CREATE TABLE IF NOT EXISTS gmv_sources (
    gmv_source_id text PRIMARY KEY,
    label text NOT NULL,
    source_type text NOT NULL DEFAULT 'other',   -- outlet | marketplace | chat | website | other
    requires_traffic boolean NOT NULL DEFAULT false,
    sort_order integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'Aktif'
);
CREATE INDEX IF NOT EXISTS idx_gmv_sources_active_order ON gmv_sources(status, sort_order);
```

**New `daily_report_sales` (child table, full breakdown):**
```sql
CREATE TABLE IF NOT EXISTS daily_report_sales (
    report_id text NOT NULL REFERENCES daily_reports(report_id) ON DELETE CASCADE,
    gmv_source_id text NOT NULL REFERENCES gmv_sources(gmv_source_id),  -- FK blocks hard-deleting a referenced source
    source_label text NOT NULL,            -- snapshot, written at submit; stays stable if config changes later
    source_type text,                      -- snapshot
    requires_traffic boolean NOT NULL DEFAULT false,  -- snapshot
    traffic integer,                       -- nullable: only for requires_traffic sources
    gmv numeric NOT NULL,
    order_count integer NOT NULL,
    pieces_sold integer NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    PRIMARY KEY (report_id, gmv_source_id)
);
CREATE INDEX IF NOT EXISTS idx_daily_report_sales_report ON daily_report_sales(report_id);
```

**`daily_reports` becomes header-only.** Update the `CREATE TABLE IF NOT EXISTS` to drop the five numeric columns + `no_buy_reason` for fresh installs, and add an idempotent migration for existing DBs:
```sql
ALTER TABLE daily_reports
    DROP COLUMN IF EXISTS traffic,
    DROP COLUMN IF EXISTS offline_gmv,
    DROP COLUMN IF EXISTS online_gmv,
    DROP COLUMN IF EXISTS order_count,
    DROP COLUMN IF EXISTS pieces_sold,
    DROP COLUMN IF EXISTS no_buy_reason;
```
Header columns kept: `report_id, report_date, store_id, user_id, submitted_latitude, submitted_longitude, distance_from_store_meter, note, stock_issue, submission_status, location_status, created_at`. The existing `db.py` `bootstrap_schema` location-column ALTER block stays as-is.

---

## Domain layer (pure) — `src/app/domain/sales_sources.py` (new)

Mirror `store_matching.py` (frozen dataclasses) + `session_state` (pure transition helpers). No Telegram, no DB, no template/draft coupling.

```python
@dataclass(frozen=True)
class GmvSource:
    gmv_source_id: str
    label: str
    source_type: str
    requires_traffic: bool
    sort_order: int
    status: str

SALES_FIELDS = ("gmv", "order_count", "pieces_sold")

def source_fields(requires_traffic: bool) -> tuple[str, ...]:
    return ("traffic", *SALES_FIELDS) if requires_traffic else SALES_FIELDS

def input_plan(specs: list[tuple[str, bool]]) -> list[tuple[str, str]]:
    # specs = ordered [(source_id, requires_traffic)]; returns ordered [(source_id, field)]
    ...

def sales_totals(sales_data: Mapping[str, Mapping[str, int]]) -> dict[str, int]:
    # {"gmv": .., "order_count": .., "pieces_sold": ..} summed across sources (no traffic total)
    ...
```

`session_state.py` changes:
- `Step` enum: **remove** `ASK_TRAFFIC, ASK_GMV, ASK_ONLINE_GMV, ASK_ORDER, ASK_PIECES, ASK_NO_BUY_REASON`; **add** `ASK_SALES_SOURCES, ASK_SALES_INPUT, REVIEW_SALES_SUMMARY, EDIT_SALES_MENU`.
- Remove `NUMERIC_STEP_FIELDS` and `apply_numeric_answer` (their job moves to `sales_sources.input_plan` + the flow loop).
- `_NEXT_STEPS`: keep `ASK_STOCK_ISSUE → ASK_NOTE`, `ASK_NOTE → REVIEW_SUMMARY`; the PIN→sales and sales→stock transitions are set explicitly in flow.

`report.py` `build_summary` → return store label + `sales_breakdown` text + `total_gmv/total_order/total_pieces` + `stock_issue` + `note` (drop traffic/offline/online/no_buy_reason tokens). When there are no sales rows (no-sales report), `sales_breakdown` renders the `SALES_NO_SALES_LABEL` ("Tidak Ada Penjualan") and the three totals are `0`.

---

## Bot helper — `src/app/bot/sales_text.py` (new), mirrors `stock_issue_text.py`

Draft+template helpers (these may read the draft dict, like `stock_issue_text` does):
- `selected_sources_text(templates, labels)` — the "Dipilih: ✓ …" block for the picker (reuse `SELECTED_PREFIX`).
- `sales_summary_text(templates, ordered_sources)` — per-source lines via `SALES_SUMMARY_LINE` + totals; GMV formatted with Indonesian thousands dots (reuse the dot-format idea from `templates._format_integer_id`).
- `source_input_position(source_ids, current_source_id)` / count — for contextual progress "Sumber X/N · Outlet".
- `format_amount(value)` — thousands separator for GMV display.

---

## Repository layer

**New `src/app/repositories/sales_sources.py`** (mirror `stores.py`):
- `SalesSourcesRepository.list_active(active_status) -> list[GmvSource]` ordered by `sort_order`, mapping rows → `GmvSource`.

**`src/app/repositories/reports.py`** — `create` becomes transactional and takes child rows:
- `async def create(self, report: dict, sales_rows: list[dict]) -> None:` → `async with pool.acquire() as conn, conn.transaction():` insert header (header columns only), then insert each `daily_report_sales` row. Remove the dropped columns from the INSERT.

---

## Flow layer — `src/app/bot/flow.py` (orchestration only)

**Entry:** `_handle_pin` transitions to `Step.ASK_SALES_SOURCES` (instead of `ASK_TRAFFIC`) and calls `_send_sales_sources_prompt`.

**Source picker (`ASK_SALES_SOURCES`)** — inline multi-select, mirror the stock-issue picker:
- `_send_sales_sources_prompt` / `_edit_sales_sources_prompt` (edit-in-place on toggle, reusing the `BadRequest "not modified"` guard).
- New keyboard `sales_source_keyboard(options, selected_ids, selected_prefix, no_sales_label, done_label)` with callback_data `sales_source:toggle:<id>`, `sales_source:no_sales`, `sales_source:done`.
- `_handle_sales_sources_callback`:
  - `toggle` → flip id in `draft["sales_source_ids"]`, edit prompt.
  - `no_sales` → set `draft["sales_no_sales"]=True`, clear any `sales_data`, remove keyboard, go straight to `ASK_STOCK_ISSUE` (`_send_step_prompt`). The mid-flow sales summary is skipped; the no-sales state surfaces only in the final review + admin notification.
  - `done` → if zero selected, re-prompt; else `_start_sales_input` (build plan for sources lacking values, in config order).
- Typed text while on this step → re-send picker (ignore).

**Per-source input loop (`ASK_SALES_INPUT`)** — one step, current position tracked in draft:
- Draft keys: `sales_source_ids` (selected, config order), `sales_data` (`{source_id: {label, source_type, requires_traffic, traffic?, gmv, order_count, pieces_sold}}`), `sales_input_plan` (`[[source_id, field], …]` for the current pass), `sales_input_pos` (int), `sales_return_to_summary` (bool — true for single-source edit / add-source passes).
- `_handle_sales_input`: parse via existing `parse_int_lenient` — accepts lenient thousand separators, rejects negative/empty/non-numeric (re-prompt the same field on `ValueError`); "Tidak Ada" → 0 via `none_reply_keyboard` (numeric-none pattern). Store into `sales_data[current][field]`; advance `pos`; if plan exhausted → `_send_sales_summary` (or back to summary when `sales_return_to_summary`); else `_send_sales_input_prompt`.
- `_send_sales_input_prompt`: pick template by field (`ASK_SALES_TRAFFIC/GMV/ORDER/PIECES`), fill `{{source}}` (label) + `{{progress}}` (main) + `{{source_progress}}` (contextual "Sumber X/N · <label>" via existing `contextual_step_progress`).

**Sales summary (`REVIEW_SALES_SUMMARY`)** — reply keyboard:
- `_send_sales_summary` renders `SALES_SUMMARY` (breakdown + totals from `sales_text.sales_summary_text`) with reply keyboard `sales_summary_keyboard(continue, edit, cancel)` → labels `BUTTON_SALES_CONTINUE` ("Lanjutkan"), `BUTTON_SALES_EDIT` ("Ubah"), `BUTTON_CANCEL` ("Batal").
- `_handle_sales_summary_text`: match (casefold) against the three labels:
  - Lanjutkan → `ASK_STOCK_ISSUE`.
  - Ubah → `_send_sales_edit_menu` (`EDIT_SALES_MENU`).
  - Batal → existing `_cancel`.
  - anything else → re-send summary (requirement #13).

**Edit menu (`EDIT_SALES_MENU`)** — inline:
- `sales_edit_menu_keyboard`: one button per entered source (`sales_edit:source:<id>`), a `BUTTON_EDIT_SOURCES` ("Tambah / Hapus Sumber Penjualan") → `sales_edit:sources`, and `BUTTON_BACK_TO_SUMMARY` → `sales_edit:back`.
- `_handle_sales_edit_callback`:
  - `source:<id>` → build a single-source `sales_input_plan` for that id, set `sales_return_to_summary=True`, go to `ASK_SALES_INPUT`.
  - `sources` → go to `ASK_SALES_SOURCES` with current selections preselected (picker reuses `draft["sales_source_ids"]`). On `done`: keep values for still-selected sources, drop removed ones, build input plan **only for newly added** sources; if none new → straight to summary.
  - `back` → `_send_sales_summary`.

**Submit (`_save_and_complete`):** build header report dict (no numeric columns) + `sales_rows` from `sales_data` (with label/type/requires_traffic/sort_order snapshots; `traffic=None` when not required). For a no-sales report (`sales_no_sales`), `sales_rows` is empty. Call `reports.create(report, sales_rows)`. Admin notification + final `REPORT_SUMMARY` use `build_summary`'s breakdown/total tokens — which render `SALES_NO_SALES_LABEL` + zero totals when `sales_rows` is empty. Remove `no_buy_reason` usage throughout. Remove the now-dead `_skip_no_buy_reason` and `ASK_NO_BUY_REASON` branch.

**Routing:** in `handle_message` add `ASK_SALES_INPUT → _handle_sales_input` and `REVIEW_SALES_SUMMARY → _handle_sales_summary_text` (and `ASK_SALES_SOURCES` → re-send picker on stray text); in `handle_callback` add `ASK_SALES_SOURCES`/`sales_source:` and `EDIT_SALES_MENU`/`sales_edit:` branches.

---

## Progress (`src/app/bot/progress.py`)

Collapse the old 8-phase map (3 numeric phases removed) into **5 main phases**, sales as phase 3 "Sumber Penjualan":
1 Toko · 2 Verifikasi PIN · 3 **Sumber Penjualan** (`ASK_SALES_SOURCES`, `ASK_SALES_INPUT`, `REVIEW_SALES_SUMMARY`, `EDIT_SALES_MENU`) · 4 Kendala & Catatan (`ASK_STOCK_ISSUE`, `ASK_NOTE`) · 5 Review & Submit (`REVIEW_SUMMARY`, `CONFIRM_DUPLICATE`).
Within the input loop, show contextual sub-progress "Sumber X/N · <label>" using existing `contextual_step_progress` with a new `SALES_SOURCE_STEP_LABEL` key. (Honors the requested "Langkah · Sumber Penjualan"; total moves 8→5 because the per-channel inputs now live under one phase with sub-progress.)

---

## `ui_translate` keys (`Reference/ui_translate.csv` + seed)

**Add** (labels for sources are NOT here — they live in `gmv_sources`):
- Prompts: `ASK_SALES_SOURCES`, `ASK_SALES_TRAFFIC`, `ASK_SALES_GMV`, `ASK_SALES_ORDER`, `ASK_SALES_PIECES` (each with `{{progress}}`, `{{source}}`, `{{source_progress}}` where relevant).
- Buttons: `BUTTON_NO_SALES` ("Tidak Ada Penjualan"), `BUTTON_SALES_DONE` ("Selesai"), `BUTTON_SALES_CONTINUE` ("Lanjutkan"), `BUTTON_SALES_EDIT` ("Ubah"), `BUTTON_EDIT_SOURCES` ("Tambah / Hapus Sumber Penjualan"), `BUTTON_BACK_TO_SUMMARY` ("Kembali ke Ringkasan"). Reuse existing `BUTTON_CANCEL`, `SELECTED_PREFIX`.
- Summary/display: `SALES_SUMMARY`, `SALES_SUMMARY_LINE`, `SALES_SUMMARY_INVALID_HINT`, `SALES_NO_SALES_LABEL` ("Tidak Ada Penjualan" — shown in the final review + admin notification when no sales rows exist), `SALES_SOURCES_SELECTED_EMPTY`, `SALES_SOURCES_SELECTED_HEADER`, `EDIT_SALES_MENU`.
- Progress: `PROGRESS_PHASE_SALES` ("Sumber Penjualan"), `SALES_SOURCE_STEP_LABEL` ("Sumber").
- Rework `REPORT_SUMMARY`, `ADMIN_NOTIFICATION`, `ADMIN_NOTIFICATION_CORRECTION` to use `{{sales_breakdown}}`, `{{total_gmv}}`, `{{total_order}}`, `{{total_pieces}}` instead of traffic/offline/online tokens.

**Deprecate** (add to `seed.DEPRECATED_UI_TRANSLATE_KEYS`, remove CSV rows): `ASK_TRAFFIC`, `ASK_GMV`, `ASK_ONLINE_GMV`, `ASK_ORDER`, `ASK_PIECES`, `PROGRESS_PHASE_TRAFFIC`, `PROGRESS_PHASE_GMV_OFFLINE`, `PROGRESS_PHASE_GMV_ONLINE`, `PROGRESS_PHASE_ORDER_PIECES`.

`seed._template_category`: add `SALES_` → `"sales"` grouping.

---

## Seed (`src/app/scripts/seed.py` + `Reference/gmv_sources.csv` new)

- Add `seed_gmv_sources(pool)` (mirror `seed_stores`, `ON CONFLICT DO UPDATE`), called from `main()`. CSV columns (header row): `Gmv_Source_ID, Label, Source_Type, Requires_Traffic, Sort_Order, Status`. Add a `_bool(value)` helper for `Requires_Traffic`.
- Seed rows: outlet/Outlet/outlet/true/1, whatsapp/Whatsapp/chat/false/2, shopee/Shopee/marketplace/false/3, tokopedia/Tokopedia/marketplace/false/4, tiktok/Tiktok/marketplace/false/5, website/Website/website/false/6 (all `Aktif`).
- Wire `SalesSourcesRepository` into `application.build_application` `post_init` and pass it to `ReportFlow`.

---

## Tests (`tests/`, match existing style — inline fakes, `asyncio.run`, no DB/Telegram)

- **`test_sales_sources.py`** (new, domain): `source_fields` (traffic only when required), `input_plan` ordering (Outlet's 4 fields first, others' 3), `sales_totals` sums (no traffic total).
- **`test_sales_text.py`** (new, helper): `sales_summary_text` breakdown + totals + amount formatting; the **no-sales** branch rendering `SALES_NO_SALES_LABEL` + zero totals; the breakdown using the row's **snapshot label** (not a live config label, proving soft-disabled/renamed historical sources stay stable); `selected_sources_text`; `source_input_position`.
- **`test_validation.py`** (extend): reconfirm `parse_int_lenient` accepts lenient separators and rejects negative/empty/non-numeric — the contract the sales inputs rely on.
- **`test_keyboards.py`** (extend): `sales_source_keyboard` (toggle/`no_sales`/`done`, selected prefix), `sales_summary_keyboard` reply layout, `sales_edit_menu_keyboard` (per-source + add/remove + back).
- **`test_sales_flow.py`** (new, flow): reuse the `_Fake*` harness from `test_location_flow.py`; add `_FakeSalesSources` (filters by `status`), a `_FakeReports` capturing `create`, and a `_callback_update`/`_FakeCallbackQuery` (with `answer`, `data`, `message`, `edit_message_text`, `edit_message_reply_markup`). Cover:
  - **Inactive source not in picker** — a `Nonaktif` source is absent from the `ASK_SALES_SOURCES` keyboard.
  - "Tidak Ada Penjualan" → `ASK_STOCK_ISSUE`, no sales rows, `sales_no_sales` set; **final review + admin notification show "Tidak Ada Penjualan" + zero totals**.
  - multi-source selection → correct per-source field order (Outlet asks traffic first); completion → `REVIEW_SALES_SUMMARY` with totals.
  - **Invalid sales input** (negative/empty/non-numeric) → same field re-prompted, no advance.
  - invalid summary text → summary re-shown; Lanjutkan → `ASK_STOCK_ISSUE`; Batal → cancel.
  - Ubah → edit one source re-asks only its fields then returns to recalculated summary; Tambah/Hapus → picker preselected, add source collects only the new source, remove drops its draft values.
  - submit passes correct `sales_rows` (with snapshot fields; `traffic=None` for non-Outlet) to `reports.create`.
- Update **`test_session_state.py`** (drop `apply_numeric_answer` tests; assert new step set / removed steps), **`test_progress.py`** (5-phase map + sales phase), and **`test_report.py`**/**`test_templates.py`** if `build_summary` assertions reference old tokens.

---

## Files touched

New: `src/app/domain/sales_sources.py`, `src/app/bot/sales_text.py`, `src/app/repositories/sales_sources.py`, `Reference/gmv_sources.csv`, `tests/test_sales_sources.py`, `tests/test_sales_text.py`, `tests/test_sales_flow.py`.
Modified: `sql/schema.sql`, `src/app/domain/session_state.py`, `src/app/domain/report.py`, `src/app/repositories/reports.py`, `src/app/bot/flow.py`, `src/app/bot/keyboards.py`, `src/app/bot/progress.py`, `src/app/bot/application.py`, `src/app/scripts/seed.py`, `Reference/ui_translate.csv`, `tests/test_session_state.py`, `tests/test_progress.py`, `tests/test_report.py`, `tests/test_templates.py`.

---

## Verification

1. `make test` — full suite green (new domain/helper/keyboard/flow tests + updated ones).
2. `make up && make seed` — confirms schema is idempotent on an existing DB (old columns dropped, `gmv_sources` + `daily_report_sales` created) and `gmv_sources` is populated.
3. Manual Telegram run (`BOT_MODE=polling` for tunnel-free): `/start` → location → store → PIN `123123` →
   - **Tidak Ada Penjualan** → jumps straight to Kendala → Catatan → final review shows "Tidak Ada Penjualan" + totals 0, submit; verify a `daily_reports` row with **no** `daily_report_sales` rows, and the admin notification shows "Tidak Ada Penjualan".
   - **Inactive source** → set one `gmv_sources` row to `status='Nonaktif'`, restart, confirm it no longer appears in the picker while existing reports that referenced it still display its snapshot label.
   - Select Outlet + Shopee + Tokopedia → Outlet asks Traffic+GMV+Order+Pieces, others ask GMV+Order+Pieces, in that order → sales summary shows per-source breakdown + totals (no total traffic).
   - On summary type gibberish → summary repeats; **Ubah** → edit Shopee only → re-asks Shopee fields → returns to summary with new totals; **Tambah/Hapus** → picker preselected, add Tiktok → collects only Tiktok → back to summary; **Lanjutkan** → Kendala/Catatan → submit.
4. DB check: `SELECT * FROM daily_report_sales WHERE report_id = (SELECT report_id FROM daily_reports ORDER BY created_at DESC LIMIT 1);` — rows match entered values, `source_label` snapshot present, `traffic` NULL for non-Outlet sources; totals in the admin notification equal `SUM` over these rows.

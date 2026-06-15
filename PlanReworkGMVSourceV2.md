# Rework `ASK_STOCK_ISSUE` → DB-backed single-select + separate Note phase

## Context

Today `ASK_STOCK_ISSUE` is a **multi-select** screen: it shows four hardcoded issue buttons (Size/Warna/Barang Belum Datang/Stok), plus `Lainnya` (free-text), `Tidak Ada`, and `Selesai`, then walks a per-issue SKU loop. The option list is hardcoded in `flow.py` (`STOCK_ISSUE_OPTIONS`, `STOCK_ISSUE_DETAIL_TITLE_KEYS`) and the labels live in `ui_translate`. Progress lumps stock-issue and note into one phase ("Langkah 4/5 · Kendala & Catatan").

We are reworking it into a **single-select, DB-backed** step that mirrors the `gmv_sources` pattern we just shipped:
- Show only active options from a new `stock_issues` config table (seeded `Size Habis`, `Warna Habis`, `Stok Kosong`) **plus a fixed `Tidak Ada`** action.
- Selecting one option goes **straight into the existing SKU-detail mechanism**; finishing it saves the formatted `stock_issue` and moves to `ASK_NOTE`.
- `Tidak Ada` → `stock_issue = "-"` → `ASK_NOTE`.
- Remove multi-select, `Lainnya`/free-text, `Selesai`, and `Barang Belum Datang`.
- Split progress into its own **Kendala Stok** phase and a separate **Catatan** phase (total 5 → 6).

Layering is unchanged: option list is **business data in a table** (not hardcoded in `flow.py`), SQL only in repositories/schema, orchestration in `flow.py`, copy DB-backed in `ui_translate`, idempotent schema, Docker-first. This reuses the SKU-detail loop almost entirely (the loop already iterates a list of option ids — we just give it a single-element list).

Minor decisions (stated, easy to change): options render **one button per row** + `Tidak Ada` last; `Barang Belum Datang` is **not seeded** (the 3 active options only); the SKU-detail sub-progress stays as-is (shows "Kendala 1/1 · <label>").

---

## Data model & schema (`sql/schema.sql`, idempotent — mirror `gmv_sources`)

New standalone config table (the report still stores `stock_issue` as formatted text — **no FK**, no `daily_reports` change):
```sql
CREATE TABLE IF NOT EXISTS stock_issues (
    stock_issue_id text PRIMARY KEY,
    label text NOT NULL,
    sort_order integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'Aktif'
);
CREATE INDEX IF NOT EXISTS idx_stock_issues_active_order ON stock_issues(status, sort_order);
```
Place it right after the `gmv_sources` block.

`Reference/stock_issues.csv` (header row, like `gmv_sources.csv`):
```
Stock_Issue_ID,Label,Sort_Order,Status
size_empty,Size Habis,1,Aktif
color_empty,Warna Habis,2,Aktif
stock_empty,Stok Kosong,3,Aktif
```

---

## Domain + Repository (mirror `sales_sources`)

- **New `src/app/domain/stock_issues.py`**: frozen `StockIssue(stock_issue_id, label, sort_order, status)`. No logic (single-select needs no plan).
- **New `src/app/repositories/stock_issues.py`**: `StockIssuesRepository.list_active(active_status) -> list[StockIssue]` ordered by `sort_order, label` (mirror `repositories/sales_sources.py`).
- **`session_state.py`: no change** — `ASK_STOCK_ISSUE` and `ASK_NOTE` are already distinct steps; only the progress phase mapping conflated them.

---

## Keyboards (`src/app/bot/keyboards.py`)

Replace the multi-select `stock_issue_keyboard(options, selected_ids, selected_prefix, none_label, other_label, done_label)` with a single-select builder:
```python
def stock_issue_keyboard(options, none_label):  # options = [(id, label)]
    rows = [[InlineKeyboardButton(label, callback_data=f"stock_issue:select:{sid}")] for sid, label in options]
    rows.append([InlineKeyboardButton(none_label, callback_data="stock_issue:none")])
    return InlineKeyboardMarkup(rows)
```
`stock_issue_detail_keyboard(continue_label, skip_label)` is **unchanged** (callback `stock_issue:detail_continue` / `stock_issue:detail_skip`).

---

## Flow (`src/app/bot/flow.py`) — orchestration only

**Remove** the hardcoded `STOCK_ISSUE_OPTIONS` and `STOCK_ISSUE_DETAIL_TITLE_KEYS` constants and the multi-select-only methods: `_edit_stock_issue_prompt`, `_start_stock_issue_details_or_save`, `_stock_issue_category_values`, `_stock_issue_selected_text`, `_ordered_selected_stock_issue_ids`. Add `stock_issues: StockIssuesRepository` to `__init__` and a `_active_stock_issues()` helper.

**`_send_stock_issue_prompt`** → render `ASK_STOCK_ISSUE` (no `{{selected_issues}}`) with `stock_issue_keyboard([(s.stock_issue_id, s.label) for s in await self._active_stock_issues()], BUTTON_NONE)`.

**`_handle_stock_issue_callback`** (trim to single-select + detail):
- `stock_issue:select:<id>` → validate against active list; snapshot `draft["stock_issue_labels"] = {id: source.label}`; set `stock_issue_detail_option_ids=[id]`, `stock_issue_detail_option_id=id`, `stock_issue_sku_details={}`; `_remove_callback_keyboard`; persist `ASK_STOCK_ISSUE`; `_send_stock_issue_detail_prompt`.
- `stock_issue:none` → `_remove_callback_keyboard`; `_save_stock_issue_and_continue(update, session, "-")`.
- `stock_issue:detail_continue` / `stock_issue:detail_skip` → reuse existing `_advance_stock_issue_detail` (skip sets `sku_details[id]=[]` first). On the last (only) option, `next_detail_option_id` returns `None` → saves the formatted value and advances to `ASK_NOTE` (existing behavior).
- Drop `toggle` / `other` / `done` / `detail_done` branches.

**`_handle_stock_issue_text`** → keep only the SKU-detail path: if `draft.get("stock_issue_detail_option_id")`, treat `Tidak Ada` as skip and other text as SKU input (`_append_stock_issue_skus`); otherwise (selection screen) just re-send the picker (no free-text). Delete the custom-issue branch.

**`_stock_issue_value`** → build line(s) from `stock_issue_detail_option_ids` using the snapshot `stock_issue_labels` for `{{issue}}` and `STOCK_ISSUE_DETAIL_LINE` / `STOCK_ISSUE_DETAIL_EMPTY_VALUE` (reuse). **`_stock_issue_option_label`** and **`_stock_issue_detail_title`** read the snapshot label from `draft["stock_issue_labels"]` instead of the deleted constants. `_save_stock_issue_and_continue` also pops `stock_issue_labels`.

Unchanged & reused: `_advance_stock_issue_detail`, `_append_stock_issue_skus`, `_send_stock_issue_detail_prompt`, `_stock_issue_detail_progress`, `_stock_issue_detail_continue_label` (next is always `None` → "Lanjut ke Catatan"), `_stock_issue_detail_instruction_text`, `_stock_issue_sku_text`, and all `stock_issue_text.py` helpers except `selected_issue_text`.

**`src/app/bot/stock_issue_text.py`**: remove `selected_issue_text` (only the multi-select picker used it).

**`src/app/bot/application.py`**: construct `StockIssuesRepository(pool)` and pass `stock_issues=` to `ReportFlow` (place the param after `sales_sources`).

---

## Progress (`src/app/bot/progress.py`) — 5 → 6 phases

Split the combined phase; renumber to `/6`:
1 Toko · 2 Verifikasi PIN · 3 Sumber Penjualan (sales steps) · **4 Kendala Stok** (`ASK_STOCK_ISSUE` → `PROGRESS_PHASE_STOCK_ISSUE`) · **5 Catatan** (`ASK_NOTE` → `PROGRESS_PHASE_NOTE`) · 6 Review & Submit (`REVIEW_SUMMARY`, `CONFIRM_DUPLICATE`).

---

## `ui_translate` (`Reference/ui_translate.csv` + seed)

**Add:** `PROGRESS_PHASE_STOCK_ISSUE` ("Kendala Stok"), `PROGRESS_PHASE_NOTE` ("Catatan").
**Reword:** `ASK_STOCK_ISSUE` — drop `{{selected_issues}}` and the multi-select/`Lainnya` text, e.g. `"{{progress}}\n\nApakah ada kendala stok hari ini?\n\nPilih salah satu kendala di bawah, atau tekan <b>Tidak Ada</b>."`
**Deprecate** (add to `seed.DEPRECATED_UI_TRANSLATE_KEYS` + remove CSV rows): `STOCK_ISSUE_OPTION_SIZE_EMPTY/COLOR_EMPTY/NOT_ARRIVED/STOCK_EMPTY`, `STOCK_ISSUE_DETAIL_TITLE_SIZE_EMPTY/COLOR_EMPTY/NOT_ARRIVED/STOCK_EMPTY` (labels now in `stock_issues`), `STOCK_ISSUE_SELECTED_EMPTY`, `STOCK_ISSUE_SELECTED_HEADER`, `STOCK_ISSUE_CUSTOM_PROMPT`, `STOCK_ISSUE_CUSTOM_LABEL`, `BUTTON_STOCK_ISSUE_OTHER`, `BUTTON_DONE`, `PROGRESS_PHASE_ISSUE_NOTE`.
**Keep:** `BUTTON_NONE` ("Tidak Ada"), all `STOCK_ISSUE_DETAIL_*` (PROMPT/INPUT_INSTRUCTION/SKIP_INSTRUCTION/SKU_EMPTY/SKU_HEADER/EMPTY_VALUE/LINE), `STOCK_ISSUE_DETAIL_STEP_LABEL`, `NEXT_PHASE_NOTE_LABEL`, `BUTTON_CONTINUE_TO_NEXT_PHASE`, `SELECTED_PREFIX`. (`BUTTON_CONTINUE_TO_NEXT_ISSUE` stays — `continue_button_label` still references it defensively though single-select never hits that branch.)

**Seed (`src/app/scripts/seed.py`):** add `seed_stock_issues(pool)` (mirror `seed_gmv_sources`, `ON CONFLICT DO UPDATE` from `Reference/stock_issues.csv`), called from `main()`. `_template_category` already maps `STOCK_ISSUE_`→`stock_issue` and `PROGRESS_`→`progress`.

---

## Tests

- **New `tests/test_stock_issue_flow.py`** (mirror the `test_sales_flow.py` fake harness; add `_FakeStockIssues.list_active` filtering by `status` and ordered): picker shows only active DB options + `Tidak Ada` (no `Selesai`/`Lainnya`/`Barang Belum Datang`); an inactive option is hidden and order follows `sort_order`; `stock_issue:select:<id>` → `STOCK_ISSUE_DETAIL_PROMPT` sent + detail draft keys set; SKU entry then `detail_continue` → `stock_issue` formatted value + step `ASK_NOTE`; `stock_issue:none` → `stock_issue == "-"` + step `ASK_NOTE`; stray text on the picker re-prompts (no free-text).
- **`tests/test_keyboards.py`**: replace/extend with the new `stock_issue_keyboard(options, none_label)` shape (`select:` callbacks + `none`); detail-keyboard tests unchanged.
- **`tests/test_stock_issue_text.py`**: drop the `selected_issue_text` import + its two tests; keep the rest.
- **`tests/test_progress.py`**: 6-phase map — `ASK_STOCK_ISSUE` = "Tahap 4/6 · Kendala Stok", `ASK_NOTE` = "5/6 · Catatan", `REVIEW_SUMMARY` = "6/6"; update the `_templates` dict keys.
- **`tests/test_sales_flow.py`** + **`tests/test_location_flow.py`**: add the new `stock_issues` arg to the `ReportFlow(...)` construction (a `_FakeStockIssues` for sales-flow since its no-sales path renders the stock-issue picker; `SimpleNamespace()` is enough for location-flow).

---

## Files touched

New: `sql` block in `sql/schema.sql`, `Reference/stock_issues.csv`, `src/app/domain/stock_issues.py`, `src/app/repositories/stock_issues.py`, `tests/test_stock_issue_flow.py`.
Modified: `src/app/bot/flow.py`, `src/app/bot/keyboards.py`, `src/app/bot/stock_issue_text.py`, `src/app/bot/progress.py`, `src/app/bot/application.py`, `src/app/scripts/seed.py`, `Reference/ui_translate.csv`, `tests/test_keyboards.py`, `tests/test_stock_issue_text.py`, `tests/test_progress.py`, `tests/test_sales_flow.py`, `tests/test_location_flow.py`.

---

## Verification

1. `make test` — full suite green (new flow test + updated keyboard/progress/text/harness tests).
2. `make seed` — idempotent on the existing DB; `SELECT * FROM stock_issues ORDER BY sort_order;` returns the 3 active rows; deprecated `ui_translate` keys gone, `PROGRESS_PHASE_STOCK_ISSUE`/`PROGRESS_PHASE_NOTE` present.
3. Manual (`BOT_MODE=polling`): reach Kendala — screen shows exactly **Size Habis / Warna Habis / Stok Kosong / Tidak Ada** (no Selesai/Lainnya/Barang Belum Datang, no free-text). Tap an option → SKU prompt → enter SKUs → "Lanjut ke Catatan" → Catatan; verify saved `stock_issue` text. Separately tap `Tidak Ada` → goes straight to Catatan with `stock_issue = "-"`. Progress reads "Langkah 4/6 · Kendala Stok" then "5/6 · Catatan". Disable one row (`UPDATE stock_issues SET status='Nonaktif'`) and confirm it disappears from the picker.

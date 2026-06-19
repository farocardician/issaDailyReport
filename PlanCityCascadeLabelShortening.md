# Plan: Province → City cascade + compact short-code store labels

## Context

Two related improvements to the store data/UX:

1. **Province → City cascade in the store form.** Today `city` is free-text typed. Replace it with a tap-only **province picker → city picker** (city filtered by the chosen province) — mirroring the brand/outlet picker pattern plus the report-flow brand→store cascade, reusing existing pagination. Adds a `province` field to stores. Data source: `Reference/regions.csv` (`Province,City`, 38 provinces, 514 official `Kota`/`Kabupaten` rows).

2. **Compact store labels via short codes.** Store labels/buttons are long (`VIVI ZUBEDI – Sogo Pondok Indah Mall, Jakarta`). Brand and outlet already have short codes (`VZ`, `SOG`); give **city** a short code too (`JKT`, `BDG`, …) and render the label **dot-separated with short codes**: `VZ · SOG · Pondok Indah Mall · JKT` (branch stays full as the most identifying part). Admin store **detail** keeps full names.

## Decisions (confirmed)

- **Cascade UX:** paginated **2-column** button pickers (≈10/page), tap-only (typed text re-prompts); no type-to-filter. Cascade keeps each city list to one province (4–38 cities).
- **City naming:** official `regions.csv` names (`Kota Bandung`, `Jakarta Selatan`, `Kabupaten Tangerang`, …).
- **Existing data:** normalize all 37 stores now (province + official city) per the table below.
- **Label:** dot-separated short codes `{{brand}} · {{outlet}} · {{branch}} · {{city}}` where brand/outlet/city are **short codes with fallback to the full name**.
- **Short-code source:** stores query **LEFT JOINs** the master tables by label to fetch short codes (always current, works for existing rows) — no denormalized columns on `stores`.

## Normalization mapping (apply to `Reference/store_master.csv`)

Add a `Province` column and rewrite `City` to the official name:

| Current city / Jakarta branch | Province | Official City |
|---|---|---|
| Banda Aceh | Aceh | Kota Banda Aceh |
| Bandar Lampung | Lampung | Kota Bandar Lampung |
| Bandung (×2) | Jawa Barat | Kota Bandung |
| Banjarbaru | Kalimantan Selatan | Kota Banjarbaru |
| Banjarmasin | Kalimantan Selatan | Kota Banjarmasin |
| Bukittinggi | Sumatera Barat | Kota Bukittinggi |
| Jambi | Jambi | Kota Jambi |
| Makassar | Sulawesi Selatan | Kota Makassar |
| Medan | Sumatera Utara | Kota Medan |
| Padang | Sumatera Barat | Kota Padang |
| Pekanbaru | Riau | Kota Pekanbaru |
| Samarinda | Kalimantan Timur | Kota Samarinda |
| Surabaya (×6) | Jawa Timur | Kota Surabaya |
| Yogyakarta | DI Yogyakarta | Kota Yogyakarta |
| Pondok Indah Mall / Kota Kasablanka / GL (Galeries Lafayette) | DKI Jakarta | Jakarta Selatan |
| Plaza Senayan / Seibu / Central | DKI Jakarta | Jakarta Pusat |
| Karawaci (×2) | Banten | Kabupaten Tangerang |

Verify each official name exists verbatim in `regions.csv` while editing.

## City short codes (seed into `regions.short_code` for cities in use; blank elsewhere → label falls back to full city)

`Jakarta Pusat/Selatan/Barat/Utara/Timur → JKT`, `Kota Bandung → BDG`, `Kota Surabaya → SBY`, `Kota Medan → MDN`, `Kota Makassar → MKS`, `Kota Yogyakarta → JOG`, `Kota Banda Aceh → BNA`, `Kota Bandar Lampung → BDL`, `Kota Banjarbaru → BJB`, `Kota Banjarmasin → BJM`, `Kota Bukittinggi → BKT`, `Kota Jambi → JMB`, `Kota Padang → PDG`, `Kota Pekanbaru → PKU`, `Kota Samarinda → SMD`, `Kabupaten Tangerang → TNG`.

## 1. DB + seed

- **`sql/schema.sql`:**
  - `CREATE TABLE IF NOT EXISTS regions (province text NOT NULL, city text NOT NULL, short_code text NOT NULL DEFAULT '', status text NOT NULL DEFAULT 'Aktif', PRIMARY KEY (province, city));` + `CREATE INDEX IF NOT EXISTS idx_regions_active ON regions(status, province, city);`
  - `stores` base DDL: add `province text` (nullable) + idempotent `ALTER TABLE stores ADD COLUMN IF NOT EXISTS province text;`.
- **`Reference/regions.csv`:** add a `Short_Code` column (mostly blank; fill the ~16 used cities above).
- **`Reference/store_master.csv`:** add `Province` column; rewrite `City` per the mapping.
- **`src/app/scripts/seed.py`:** add `seed_regions(pool)` (reads `Province,City,Short_Code`; upsert `ON CONFLICT (province, city) DO UPDATE`); call it in `main()`. Update `seed_stores` to read `row["Province"]` and write the `province` column (INSERT + `ON CONFLICT DO UPDATE`).

## 2. Repository + domain

- **`src/app/repositories/regions.py`** (new): `RegionsRepository.list_provinces(active_status) -> list[str]` (distinct, ordered) and `list_cities(province, active_status) -> list[str]` (ordered). Wire `regions=RegionsRepository(pool)` into `application.py` + `ReportFlow.__init__`.
- **`src/app/domain/store_matching.py`:** add to `StoreLocation`, **as defaulted trailing fields** (so existing constructions/tests don't break): `province: str | None = None`, `brand_short: str | None = None`, `outlet_short: str | None = None`, `city_short: str | None = None`.
- **`src/app/repositories/stores.py`:** add `province` to writes; change the read queries (`list_active`, `list_all`, `get_by_id`) to:
  ```sql
  SELECT s.store_id, s.outlet, s.branch, s.city, s.province, s.brand,
         s.latitude, s.longitude, s.allowed_radius_meter, s.status, s.notes,
         b.short_code AS brand_short, o.short_code AS outlet_short, r.short_code AS city_short
  FROM stores s
  LEFT JOIN brands  b ON b.label = s.brand
  LEFT JOIN outlet  o ON o.label = s.outlet
  LEFT JOIN regions r ON r.province = s.province AND r.city = s.city
  ```
  `_to_store` maps the three `*_short` (treat empty string as `None`).
- Province→city filtering is plain SQL; pagination reuses `domain/pagination.paginate`. No new domain module.

## 3. Store form cascade (`src/app/bot/flow.py`, `src/app/domain/store_management.py`)

- **`STORE_FORM_FIELDS`**: insert `"province"` before `"city"`.
- **`validate_store_field`**: add `province` to the required set (`_field_error_suffix` yields `PROVINCE`/`CITY`).
- **`_send_store_form_prompt`**: add `field == "province"` (all provinces) and `field == "city"` (cities of `form["fields"]["province"]`) picker branches, mirroring `brand`/`outlet`; page from `form` draft (`prov_page`/`city_page`).
- **`_handle_store_form_input_text`**: add `province`, `city` to the buttons-only set (typed text re-prompts).
- **`_handle_store_form_callback`**: add `stores:setprov:{i}` / `stores:setcity:{i}` (recompute the sorted list, pick `[i]`, validate plan position, `_remove_callback_keyboard`, save label, advance) and `stores:provpage:{n}` / `stores:citypage:{n}` (store page, re-render). Index references the deterministically re-sorted list (no big draft storage). Add `:noop` to the early-return.
- **Helpers:** `_active_provinces()`, `_active_cities(province)`, `_store_form_province_keyboard(page)`, `_store_form_city_keyboard(province, page)`.
- **Edit-mode cascade:** in `_start_store_field_input`, editing `province` → plan `["province","city"]` (re-pick city so it can't be left stale); editing `city` → plan `["city"]` for the store's current province. `_store_fields_from_location` includes `province`.

## 4. Keyboard (`src/app/bot/keyboards.py`)

Add `paginated_option_keyboard(option_ids, button_labels, set_callback, page_callback, page, prev_label, next_label, indicator_label, previous_label, previous_cb, cancel_label, cancel_cb, columns=2)`: slice via `paginate(..., PICKER_PAGE_SIZE≈10)`, lay buttons **2 per row**, append `pagination_nav_row(...)` when `total_pages > 1`, then the `Sebelumnya`/`Batal` row. Reuses `paginate` + `pagination_nav_row`. (Keep `option_picker_keyboard` for the short brand/outlet lists.)

## 5. UI text + presentation

- **`Reference/ui_translate.csv`:**
  - `STORE_LABEL_FORMAT` → `{{brand}} · {{outlet}} · {{branch}} · {{city}}`; `AREA_LABEL_FORMAT` → `{{outlet}} · {{branch}} · {{city}}` (tokens carry short-or-full).
  - Add `ASK_STORE_PROVINCE`, `BUTTON_STORE_FIELD_PROVINCE` ("Provinsi"), `STORE_ERROR_PROVINCE_REQUIRED`. Update `ASK_STORE_CITY` → "…Pilih kota."; `STORE_ERROR_CITY_REQUIRED` → "Kota wajib dipilih.".
  - Add a `{{province}}` line to `STORE_DETAIL` and `STORE_FORM_REVIEW` (these keep **full** names).
- **`src/app/templates.py`:** `render_store_label` / `render_area_label` pass short-or-full: `brand = store.brand_short or store.brand`, `outlet = store.outlet_short or store.outlet`, `city = store.city_short or store.city` (handle `StoreLocation` and `Mapping`).
- **`src/app/bot/store_text.py`:** `FIELD_KEY_SUFFIXES` add `"province":"PROVINCE"`; add `province` token to `store_detail_tokens`, `store_form_review_tokens`, `store_list_button_labels` (detail/review show full names).

## 6. Tests

- **New:** `tests/test_regions.py` (repo/sorting via fake); `tests/test_keyboards.py` case for `paginated_option_keyboard` (2-col, nav hidden at ends, no empty-text buttons); a `templates` test that `render_store_label` uses short codes and falls back to full when a short is missing.
- **Flow:** add `_FakeRegions`; cascade tests — province picker paginates; choosing a province shows only its cities; choosing a city advances; `Sebelumnya` from city returns to province; typed text re-prompts on both steps.
- **Update:** `StoreLocation(...)` constructions gain the new defaulted fields (most need no change); label/detail assertions updated for dot-separated short labels + province. Representative files: `tests/test_store_management_flow.py`, `tests/test_store_management.py`, `tests/test_templates.py`, `tests/test_store_matching.py`, `tests/test_location_flow.py`.

## Verification

- `make test` green.
- `make seed` (twice, idempotent): `regions` has 514 rows (short codes on the ~16 used cities); `stores.province` populated. Spot-check `SELECT brand, outlet, branch, province, city FROM stores` — Pondok Indah Mall → `DKI Jakarta / Jakarta Selatan`, Karawaci → `Banten / Kabupaten Tangerang`, Bandung → `Jawa Barat / Kota Bandung`.
- **Rebuild + restart** (`make up`) so the running bot loads new code (no hot-reload — this caused the earlier "stuck buttons").
- Live (`BOT_MODE=polling`): SPG manual store list / "nearest store" now shows compact `VZ · SOG · Pondok Indah Mall · JKT`. As superadmin: **Add store** → after Branch, a **Provinsi** picker (2-col, paginated) → pick `Jawa Barat` → only its cities → pick `Kota Bandung` → advances to Latitude; `Sebelumnya` from city returns to province. **Edit → Provinsi** re-runs province→city; **Edit → Kota** lists the current province's cities. Store **detail** shows full Province + City.

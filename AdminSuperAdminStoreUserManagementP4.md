# Phase 4 — Full Store Management (`Kelola Store`)

> Phases 1–3 are complete and approved (role routing + menus; shared `Kelola User`; `Kelola Admin`
> via the parameterized person-scoped engine). This plan covers **Phase 4 only**.

## Context

`Kelola Store` is CRUD over **store records**, reachable **only by SUPER_ADMIN** from the Super
Admin Menu (the current `menu:stores` → `MENU_PLACEHOLDER`). It must: Add Store / List Stores / View
detail / Edit fields / Deactivate-reactivate. New stores are immediately usable by the existing
report location/store-matching flow; deactivated stores must disappear from active matching; store
identity (brand + department store/partner + branch + city) must be unique among **active** stores
(rejected on add, on editing an active store, and on reactivation); status changes must never delete
or modify historical `daily_reports`; no hard delete; stores have **no** Telegram reset-link action.

**Approach: a separate `stores:` management flow (not the person-scoped engine).** Stores are a
different entity (different fields, numeric coordinate/radius validation, identity-based duplicates,
no Telegram), so forcing them into the `ManagementScope` engine would complicate the now-stable
users/admins code. Instead, build a parallel store flow that **reuses the entity-agnostic pieces**:
the generic reply keyboards (`user_form_navigation_keyboard`, `user_form_review_keyboard`) and
`confirm_keyboard`, the generic inline `management_menu_keyboard`/`management_edit_menu_keyboard`
(both take a `prefix` and reference no id field — pass `"stores"`), the `FieldResult` dataclass +
optional-field/skip mechanics, and the draft `plan`/`pos` form-loop shape. Only store-specific inline
list/detail keyboards, validators, identity logic, copy, and repo methods are new. **No changes to
the report flow, the person engine, or the daily-report tests.**

The report flow is unaffected: it reads stores only via `self._stores.list_active(active_status)`
(matching/manual selection) and `self._stores.get_by_id(...)`; deactivated stores are already
excluded both by `list_active`'s `status` filter and by `match_stores`' `status != active_status`
guard (`domain/store_matching.py`). The `stores:` callback prefix is disjoint from the report's
`store:` / `manual:stores` callbacks (different prefix, gated by different steps).

## Steps — `src/app/domain/session_state.py`

Add: `MANAGE_STORES_MENU` (distinct submenu root, like `MANAGE_ADMINS_MENU`), `STORE_LIST`,
`STORE_DETAIL`, `STORE_FORM_INPUT`, `STORE_EDIT_MENU`, `STORE_FORM_REVIEW`, `STORE_CONFIRM_STATUS`.
(No reset-link step.)

## Domain — new `src/app/domain/store_management.py` (pure)

Reuse the `FieldResult` shape and `parse_int_lenient` (`domain/validation.py`). Add:

- `STORE_FORM_FIELDS = ("brand", "department_store", "branch", "city", "latitude", "longitude",
  "allowed_radius", "notes")`, `OPTIONAL_FIELDS = {"notes"}`.
- `validate_store_field(field, raw) -> FieldResult`: the four text fields required/non-empty;
  `latitude`/`longitude` parsed as float (accept a comma decimal by normalizing `,`→`.` when no `.`
  present), range-checked (lat −90..90, lon −180..180) → `STORE_ERROR_LATITUDE_INVALID` /
  `STORE_ERROR_LONGITUDE_INVALID`; `allowed_radius` via `parse_int_lenient` and `> 0` →
  `STORE_ERROR_RADIUS_INVALID`; `notes` optional. Returns typed values (float/int) for coords/radius.
- `store_identity(brand, department_store, branch, city) -> tuple[str, ...]` — normalized
  (`" ".join(s.split()).casefold()`) for comparison.
- `is_duplicate_identity(active_stores, brand, department_store, branch, city, exclude_store_id)
  -> bool` — compares the candidate identity against the supplied **active** `StoreLocation`s,
  excluding `exclude_store_id`. (Identity uniqueness is enforced only among active stores.)
- `generate_store_id(now) -> str` — mirror `generate_user_id`, e.g. `STR-%Y%m%d-%H%M%S-NNNN`.

## Repository — extend `src/app/repositories/stores.py`

`StoreLocation` already carries every column (incl. `status`, `notes`), and `get_by_id` returns any
status — **reuse both** for detail/edit/status loads and `list_active` for the identity check. Add:

- `list_all() -> list[StoreLocation]` (all statuses, ordered by brand/branch/city) for the list.
- `create_store(store_id, brand, department_store, branch, city, latitude, longitude,
  allowed_radius_meter, notes, status)`.
- `update_store(store_id, brand, department_store, branch, city, latitude, longitude,
  allowed_radius_meter, notes)` — fields only, never `status`.
- `set_status(store_id, status)` — status-only (historical `daily_reports` reference `store_id` and
  are untouched).

## Flow — `src/app/bot/flow.py`

Menu entry: in `_handle_super_admin_menu_callback`, replace the `menu:stores` → `MENU_PLACEHOLDER`
branch (after the existing `can_manage_stores` check) with `_open_store_menu(update, actor)` →
persists `MANAGE_STORES_MENU`. (The Admin-menu handler has no `menu:stores`; ADMIN/USER are denied.)

Routing: add `elif step in STORE_CALLBACK_STEPS and data.startswith("stores:") →
_handle_store_callback(update, session, data)` in `handle_callback`; route `STORE_FORM_INPUT` /
`STORE_FORM_REVIEW` text in `handle_message`. `STORE_CALLBACK_STEPS` = `{MANAGE_STORES_MENU,
STORE_LIST, STORE_DETAIL, STORE_EDIT_MENU, STORE_CONFIRM_STATUS}`.

Store-flow handlers mirror the person flow's structure but call store domain/repo and carry no
scope (single entity): `stores:add` (8-field form loop), `stores:list`, `stores:view:{id}`,
`stores:edit:{id}` (prefill from `get_by_id`), `stores:field:{field}`, `stores:deactivate:{id}` /
`stores:reactivate:{id}` → `STORE_CONFIRM_STATUS`, `stores:confirm_status`, and
`stores:back:menu|list|detail`. Form-loop reuses the same `plan`/`pos`, `Sebelumnya`/`Batal`/`Lewati`
mechanics and the `STORE_FORM_REVIEW` (Simpan/Ubah/Batal) review-before-save.

Guards (server-side, re-checked every callback/text): `_authorize_stores(update)` →
`_current_actor` + `can_manage_stores(role)` else `MENU_ACCESS_DENIED`; `_load_store_target(update,
id)` → `get_by_id`, deny if missing. Add always creates `status = active_status`; edit never writes
status; deactivate/reactivate are status-only; no DELETE.

Identity uniqueness (validated at **save**, since identity spans four fields):
- Add save → `is_duplicate_identity(list_active, …, exclude=None)`; on dup re-show review with
  `STORE_ERROR_DUPLICATE_IDENTITY` in the notice slot (no write).
- Edit save → if the target is currently active, `is_duplicate_identity(list_active, …,
  exclude=target_id)`; on dup re-show review with the error (editing an inactive store skips this,
  matching the "active record" rule).
- Reactivate confirm → before flipping to active, `is_duplicate_identity(list_active, …,
  exclude=target_id)`; on dup deny with `STORE_ERROR_DUPLICATE_IDENTITY` and return to detail
  (the reactivation guard).
Field-level validation errors at save jump back to that field's input (as in the person flow).

## Keyboards — `src/app/bot/keyboards.py`

Reuse `management_menu_keyboard("stores", …)` and `management_edit_menu_keyboard("stores", …)`
(prefix-driven, no id field). Reuse `confirm_keyboard` (Ya/Kembali) and the generic reply keyboards.
Add two store-specific inline builders because store records key on `store_id` (not `user_id`) and
the detail has **no** reset-link button: `store_list_keyboard(stores, labels, back_label)`
(`stores:view:{store_id}` + `stores:back:menu`) and `store_detail_keyboard(store_id, is_active,
edit_label, deactivate_label, reactivate_label, back_label)` (`stores:edit/deactivate|reactivate` +
`stores:back:list` — Edit, status toggle, Back only).

## Presentation — new `src/app/bot/store_text.py`

Mirror `user_admin_text.py`: `store_list_button_labels(templates, stores)`,
`store_detail_tokens(templates, store)` (brand/department_store/branch/city/latitude/longitude/
allowed_radius/notes/status + notice), `store_form_review_tokens(fields, notice)`,
`store_field_button_labels(templates)`, `store_field_prompt_key(field)`; reuse the `_value` None→"-"
helper pattern. Detail/review render user-supplied fields through the escaping `render()`.

## UI copy — `Reference/ui_translate.csv`

Add `MANAGE_STORES_MENU`; `STORE_LIST`, `STORE_LIST_EMPTY`, `STORE_LIST_BUTTON`, `STORE_DETAIL`;
`ASK_STORE_BRAND/DEPARTMENT/BRANCH/CITY/LATITUDE/LONGITUDE/RADIUS/NOTES`; `STORE_FORM_REVIEW`,
`STORE_EDIT_MENU`; `STORE_CONFIRM_DEACTIVATE/REACTIVATE`;
`STORE_ADDED/UPDATED/DEACTIVATED/REACTIVATED`; errors
`STORE_ERROR_{BRAND,DEPARTMENT,BRANCH,CITY}_REQUIRED`, `STORE_ERROR_LATITUDE_INVALID`,
`STORE_ERROR_LONGITUDE_INVALID`, `STORE_ERROR_RADIUS_INVALID`, `STORE_ERROR_DUPLICATE_IDENTITY`;
buttons `BUTTON_STORE_ADD/LIST/EDIT/DEACTIVATE/REACTIVATE` and
`BUTTON_STORE_FIELD_{BRAND,DEPARTMENT,BRANCH,CITY,LATITUDE,LONGITUDE,RADIUS,NOTES}`. Reuse generic
`BUTTON_BACK/SAVE/EDIT/CONFIRM_YES/CANCEL/PREVIOUS/SKIP`. No `seed.py` change (prefixes route
categories; bare `STORE_*` → `store_display` category is cosmetic only). `MENU_PLACEHOLDER` is no
longer sent by any handler after this phase — leave the CSV row in place (harmless) and note it.

## Safety invariants

- Only SUPER_ADMIN reaches `Kelola Store`; every `stores:*` callback re-checks `can_manage_stores`.
- No hard delete; deactivate/reactivate is status-only; edit never changes status.
- Historical `daily_reports` are never touched (only the store's own row is updated).
- Deactivated stores vanish from active matching/selection (already enforced via `list_active` +
  `match_stores`); a newly added active store is immediately matchable.
- At most one **active** store per identity: enforced on add, on editing an active store, and on
  reactivation.

## Tests

New `tests/test_store_management.py` (domain): `validate_store_field` (required text; lat/lon range
incl. comma-decimal; radius positive/zero/negative); `store_identity` normalization (case/space);
`is_duplicate_identity` (active-only, exclude-self, normalized match); `generate_store_id` format.

New `tests/test_store_management_flow.py` (fakes, mirroring `test_admin_management_flow.py`):
`menu:stores` persists `MANAGE_STORES_MENU` with `["stores:add","stores:list","stores:back:menu"]`;
add happy path (8 fields) creates an `Aktif` store only after Simpan; list/detail render;
edit updates fields without changing status; deactivate & reactivate require confirmation and change
only status; **duplicate identity rejected on add and on editing an active store**; **reactivation
blocked when another active store shares the identity** (and allowed otherwise);
coordinate/radius validation errors re-prompt; ADMIN and USER denied `menu:stores` and any `stores:*`
callback. Plus a **matching-exclusion** test reusing the report location path (a fake `StoresRepository`
whose `list_active` filters by status): after deactivation the store is absent from the offered
manual-selection keyboard, and a still-active store remains — and historical-report intactness is
implied by `set_status` touching only the store row (assert no report writes).

Update `tests/test_role_menu_flow.py`: `menu:stores` no longer a placeholder — remove the now-empty
`test_management_menu_callbacks_send_placeholder` (no placeholders remain) and add a `menu:stores` →
`MANAGE_STORES_MENU` (SUPER_ADMIN) case plus ADMIN/USER-denied coverage; add `MANAGE_STORES_MENU` +
needed `STORE_*` stubs to that file's `_templates()`. All Phase 2/3 tests pass **unchanged**.

## Verification

1. `docker compose run --rm bot pytest -q` — full suite green (new store domain+flow tests; Phase
   1–3 and daily-report tests unchanged except the role-menu placeholder edit).
2. `make seed` — loads new `STORE_*` copy; spot-check keys exist.
3. `make up` (or `BOT_MODE=polling`); smoke as **SUPER_ADMIN**: Super Admin Menu → `Kelola Store` →
   add a store (valid coords/radius) / list / detail / edit / deactivate / reactivate; confirm
   duplicate-identity rejection on add and reactivation. As **ADMIN/USER**: no `Kelola Store` and a
   crafted `menu:stores`/`stores:*` is denied.
4. End-to-end: add a store via the bot, then run the report flow (`/start` as a USER, share a
   location near it) and confirm the new store is matched/selectable; deactivate it and confirm it
   no longer appears; confirm previously submitted reports are unaffected.

## Risks / follow-ups

- Store identity is validated at save (it spans four fields), not per-field — intentional; the
  reactivation guard re-checks at flip time.
- `store_list_keyboard` has no pagination (same caveat as the user/admin lists).
- Coordinate input accepts dot or single-comma decimals; exotic formats are rejected with a clear
  error — acceptable, flag if field usage shows otherwise.
- After this phase `MENU_PLACEHOLDER` is unused in code (CSV row kept to avoid churn); the
  person-scoped engine and report flow remain untouched.

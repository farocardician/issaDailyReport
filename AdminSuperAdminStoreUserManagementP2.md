# Phase 2 — Full User Management (`Kelola User`)

## Context

Phase 1 added role normalization and post-auth routing: `USER`/`SPG` → daily report,
`ADMIN` → Admin Menu, `SUPER_ADMIN` → Super Admin Menu. The management buttons
(`menu:users`, `menu:admins`, `menu:stores`) are currently wired to a `MENU_PLACEHOLDER`
reply.

Phase 2 replaces the `menu:users` placeholder with a full **User management CRUD sub-flow**,
shared by both `ADMIN` and `SUPER_ADMIN`. It must let an authorized actor add a user, list
users, view detail, edit basic data, deactivate/reactivate, and reset a user's Telegram link —
all server-side permission-checked, all non-destructive (no hard delete), and never able to
create or escalate an Admin/Super Admin. The daily report flow and all existing tests must stay
unchanged/green. `menu:admins` and `menu:stores` remain placeholders (Phases 3–4).

This is an extension of the existing bot using established patterns; no new architecture.
The sub-flow mirrors the existing multi-step input pattern (sales input loop + review at
`ASK_SALES_INPUT`/`REVIEW_SALES_SUMMARY`, edit menu at `EDIT_SALES_MENU`) and the Phase 1 menu
callback handlers.

## Scope / Non-goals

- In scope: CRUD for `role = USER` records only, reachable from both Admin and Super Admin menus.
- Out of scope (later phases): `Kelola Admin` (Phase 3), `Kelola Store` (Phase 4). Keep them as
  placeholders. Do **not** generalize the code to admins yet, but keep a clean seam (a target-role
  guard) so Phase 3 can reuse the same machinery.
- No schema changes needed — the `users` table already has every required column and a unique
  partial index on `telegram_user_id`.

## New `Step` values — `src/app/domain/session_state.py`

Add to the `Step` enum (no `_NEXT_STEPS` entries needed; transitions are decided in flow):

- `MANAGE_USERS_MENU` — Kelola User submenu (Tambah User / Daftar User / Kembali)
- `USER_LIST` — list of `USER` records as buttons (+ Kembali)
- `USER_DETAIL` — detail view + action buttons
- `USER_FORM_INPUT` — guided field input loop (used by both Add and single-field Edit)
- `USER_EDIT_MENU` — field picker reached from review "Ubah" (mirrors `EDIT_SALES_MENU`)
- `USER_FORM_REVIEW` — review-before-save (Simpan / Ubah / Batal)
- `USER_CONFIRM_STATUS` — confirm deactivate/reactivate (Ya / Kembali)
- `USER_CONFIRM_RESET_LINK` — confirm Telegram link reset (Ya / Kembali)

## Domain layer — new `src/app/domain/user_management.py` (pure, no Telegram/DB)

Reuse `normalize_phone` from `domain/activation.py` and `normalize_text_dash` from
`domain/validation.py`. Add:

- `USER_FORM_FIELDS = ("name", "phone", "email", "notes")` and an `OPTIONAL_FIELDS = {"email","notes"}` set.
- `validate_field(field, raw) -> FieldResult` (frozen dataclass: `ok: bool`, `value: str | None`,
  `error_key: str | None`): name required/non-empty; phone required → normalized via
  `normalize_phone` (reject empty/non-numeric); email optional but must match a simple email regex
  when present; notes optional. Optional fields blank ("-"/skip) → `value=None`.
- `is_duplicate_phone(all_users, phone, exclude_user_id) -> bool` — normalized comparison against
  **all** supplied users (any role, any status). Excludes only the current target (`exclude_user_id`)
  during edit; otherwise returns `True` if any other user already uses that normalized phone.
- `generate_user_id(now) -> str` — mirror `domain/report.py:generate_report_id`, e.g.
  `USR-%Y%m%d-%H%M%S-NNNN` with a random 4-digit suffix (flow retries on PK collision).
- `next_form_step(plan, pos)` style helper if useful, otherwise track position inline in flow like
  the sales loop does.

Unit-test this module directly (`tests/test_user_management.py`).

## Repository layer — extend `src/app/repositories/users.py`

Add methods (SQL only; the existing `find_active_by_telegram_user_id` / `list_active` /
`bind_telegram` stay untouched). All select the same column set already used.

- `get_by_id(user_id) -> dict | None`
- `list_by_role(role) -> list[dict]` — **all statuses** (needed so inactive users are visible for
  reactivation), ordered by name.
- `list_all() -> list[dict]` — every user across **all roles and all statuses**; feeds the
  normalized-phone uniqueness check (normalization stays in the domain helper, not SQL).
- `create_user(user_id, role, name, phone, email, notes, status)` — INSERT with
  `telegram_user_id`/`telegram_chat_id` NULL.
- `update_basic(user_id, name, phone, email, notes)` — updates only basic fields; never touches
  `role`, `status`, or telegram columns.
- `set_status(user_id, status)` — status-only.
- `reset_telegram_link(user_id)` — `SET telegram_user_id = NULL, telegram_chat_id = NULL`.

Duplicate-phone detection uses `list_all()` (every user, **all roles and all statuses**) passed into
the domain helper. This is intentionally stricter than the spec's "another active record" wording (a
superset of it): because phone is the activation identity (`decide_activation` requires exactly one
active phone match), rejecting duplicates globally makes a two-records-one-phone state unreachable,
which removes the need for a separate reactivation duplicate guard. The existing
`list_active(active_status)` stays only on the unchanged activation path.

## Config — `src/app/config.py`

Add `inactive_status: str = "Nonaktif"` to `Settings` (deactivate target). "Nonaktif" is the
established inactive value (used in existing tests).

## Flow orchestration — `src/app/bot/flow.py`

Callback data is namespaced `users:` (distinct from Phase 1 `menu:`). Every protected handler
re-checks permission server-side using the existing `_current_actor(update)` +
`can_manage_users(role)` pattern (already used by the menu handlers), and additionally guards the
**target**: load target via `get_by_id` and deny unless `normalize_role(target["role"]) == Role.USER`
(blocks managing/escalating admins via crafted callbacks).

Entry point change: in both `_handle_admin_menu_callback` and `_handle_super_admin_menu_callback`,
replace the `menu:users` → `MENU_PLACEHOLDER` branch with `await self._open_manage_users_menu(update)`
(after the `can_manage_users` check). `menu:admins` / `menu:stores` stay on `MENU_PLACEHOLDER`.

Add callback routing in `handle_callback` for the new steps (dispatch when
`data.startswith("users:")` and `step` is one of the new steps) and text routing in `handle_message`
for `USER_FORM_INPUT` (field text) and `USER_FORM_REVIEW` (Simpan/Ubah/Batal). Reuse the existing
answer helpers `_is_previous_answer` (Sebelumnya), `_is_cancel_answer` (Batal); add label matching
for Simpan/Ubah and Lewati (skip) via `_refresh_templates` + button-label compare, same style as
the sales summary text handler (`_handle_sales_summary_text`).

Callback/navigation map:

- `users:add` → seed draft `user_form = {mode:"add", fields:{}, plan:list(USER_FORM_FIELDS), pos:0}`,
  go to `USER_FORM_INPUT`, prompt first field.
- `users:list` → `USER_LIST` (buttons from `list_by_role("USER")`, label = name + status; + Kembali).
- `users:view:{id}` → `USER_DETAIL` (guard target role). Detail shows name/phone/email/notes/status
  + whether Telegram is linked; action buttons: Ubah Data, Nonaktifkan **or** Aktifkan Kembali
  (depending on current status), Reset Link Telegram, Kembali.
- `users:edit:{id}` → load target into draft `user_form` (mode:"edit", target_id, fields prefilled),
  open `USER_EDIT_MENU` (field picker). Selecting `users:field:{name}` sets `plan=[name]`,
  `return_to=review`, goes to `USER_FORM_INPUT` for that one field, then back to `USER_FORM_REVIEW`.
- `USER_FORM_INPUT` text: validate via domain `validate_field`; on error re-prompt with error copy
  (no advance); on success store value, advance `pos`; when plan exhausted → `USER_FORM_REVIEW`.
  Phone field additionally runs the duplicate check (`list_all` + `is_duplicate_phone`,
  `exclude_user_id` = edit target or None — i.e. **place 1 (Add input)** and **place 2 (Edit input)**)
  and re-prompts on duplicate. `Sebelumnya` steps back a
  field (add) or returns to menu/detail at pos 0; `Batal` → `_cancel`.
- `USER_FORM_REVIEW` (reply keyboard Simpan/Ubah/Batal): **Simpan** re-validates all fields +
  re-runs the `list_all` duplicate check defensively (**place 3 (save-time revalidation)**), then
  add → `generate_user_id` (+ collision retry) + `create_user(role="USER",
  status=active_status)`; edit → `update_basic`; send success copy and return to `USER_DETAIL`
  (edit) or `MANAGE_USERS_MENU` (add). **Ubah** → `USER_EDIT_MENU`. **Batal** → `_cancel`.
- `users:deactivate:{id}` / `users:reactivate:{id}` → `USER_CONFIRM_STATUS` (store pending target +
  intent in draft). `users:confirm_status` → re-check permission + target role, `set_status`, success
  copy, back to `USER_DETAIL`. `users:back` (Kembali) → `USER_DETAIL` without changes.
- `users:reset_link:{id}` → `USER_CONFIRM_RESET_LINK`; `users:confirm_reset` → `reset_telegram_link`,
  success copy, back to `USER_DETAIL`.
- `users:back:menu` / `users:back:list` / `users:back:detail` → Kembali navigation (persist the
  target step, no session clear), per the spec's navigation model.

Add small `_send_*` helpers and keyboard wiring methods following the existing `_send_menu` /
`_admin_menu_keyboard` style (each does `_refresh_templates()` then renders labels). Presentation
formatting (user-detail body, list button labels, review summary text) goes in a new
`src/app/bot/user_admin_text.py` helper module — mirroring `sales_text.py` / `stock_issue_text.py`
— to keep flow.py orchestration-only.

## Keyboards — `src/app/bot/keyboards.py`

Add builders (label strings passed in from flow, callback data fixed):
`manage_users_menu_keyboard`, `user_list_keyboard(users, labels, back_label)`,
`user_detail_keyboard(user_id, is_active, labels...)`, `user_edit_menu_keyboard(field_labels, back_label)`,
`confirm_keyboard(yes_label, back_label, yes_data, back_data)` (Ya/Kembali). Reuse
`sales_input_navigation_keyboard` for the field-input reply keyboard (Sebelumnya/Batal; add a
Lewati variant for optional fields) and a small reply keyboard for the review screen (Simpan/Ubah/Batal).

## UI copy — `ui_translate` + `Reference/ui_translate.csv` (no hardcoded strings)

Reuse existing buttons where possible: `BUTTON_CONFIRM_YES` (Ya), `BUTTON_CANCEL` (Batal),
`BUTTON_PREVIOUS` (Sebelumnya), `BUTTON_SKIP` (Lewati). Add new keys (Bahasa Indonesia), e.g.:

- Menus/labels: `MANAGE_USERS_MENU`, `BUTTON_USER_ADD`, `BUTTON_USER_LIST`, `BUTTON_BACK` (Kembali).
- List/detail: `USER_LIST`, `USER_LIST_EMPTY`, `USER_LIST_BUTTON` (name + status format),
  `USER_DETAIL` (multi-token body), `BUTTON_USER_EDIT`, `BUTTON_USER_DEACTIVATE`,
  `BUTTON_USER_REACTIVATE`, `BUTTON_USER_RESET_LINK`.
- Prompts: `ASK_USER_NAME`, `ASK_USER_PHONE`, `ASK_USER_EMAIL`, `ASK_USER_NOTES`.
- Errors: `USER_ERROR_NAME_REQUIRED`, `USER_ERROR_PHONE_REQUIRED`, `USER_ERROR_PHONE_INVALID`,
  `USER_ERROR_PHONE_DUPLICATE`, `USER_ERROR_EMAIL_INVALID`.
- Review/edit: `USER_FORM_REVIEW` (body), `BUTTON_SAVE` (Simpan), `BUTTON_EDIT` (Ubah),
  `USER_EDIT_MENU`, field-button labels (`BUTTON_USER_FIELD_NAME` …).
- Confirmations + success: `USER_CONFIRM_DEACTIVATE`, `USER_CONFIRM_REACTIVATE`,
  `USER_CONFIRM_RESET_LINK`, `USER_ADDED`, `USER_UPDATED`, `USER_DEACTIVATED`, `USER_REACTIVATED`,
  `USER_LINK_RESET`.

`seed._template_category` auto-derives category from prefix (`BUTTON_`→button, `ASK_`→prompt, others
→message) — no seed code change required. These are management screens, so they must **not** use the
daily-report `{{progress}}` token.

## Security / safety invariants (must hold)

- Every `users:*` callback re-checks `_current_actor` + `can_manage_users` (deactivated/role-changed
  actor mid-session → `MENU_ACCESS_DENIED`).
- Every target-specific action additionally verifies the target exists and is `role == USER`.
- Add always forces `role=USER`, `status=active_status`, telegram fields NULL; edit never writes
  role/status/telegram; reset clears only the two telegram columns; deactivate/reactivate is
  status-only. No DELETE statements anywhere.
- Normalized phone is unique across **all** users (any role, any status). Rejected in three places:
  Add phone input, Edit phone input, and save-time revalidation before `create_user`/`update_basic`.
  Because of this global rule, no separate reactivation duplicate-phone guard is needed — reactivation
  cannot introduce a phone clash.
- The target-role guard is independent and unchanged: `Kelola User` may only manage records whose
  normalized role is `USER`, even though the duplicate check inspects records of all roles.
- New active user is immediately self-activatable (already true: `list_active` includes them);
  deactivated user excluded from activation/start (already true via `active_status` filters) — no
  change to the activation path.

## Testing

New `tests/test_user_management.py` (pure domain): field validation (each field, required/optional,
email format), `is_duplicate_phone` — incl. exclude-self on edit, **rejection when the conflicting
record is inactive**, and **rejection when the conflicting record is a different role
(ADMIN/SUPER_ADMIN)** — and `generate_user_id` format.

New `tests/test_user_management_flow.py` (in-memory fakes, mirroring `tests/test_role_menu_flow.py`):
extend the `_FakeUsers` fake with `get_by_id`/`list_by_role`/`list_all`/`create_user`/`update_basic`/
`set_status`/`reset_telegram_link`. Cover, for **both** an `ADMIN` and a `SUPER_ADMIN` actor:
`menu:users` opens `MANAGE_USERS_MENU`; add happy path persists only after Simpan and creates a
`USER`/`Aktif`/no-telegram record; duplicate phone rejected — including a case where the conflicting
record is **inactive**; email-invalid re-prompt; list/detail
render; edit updates basic fields without touching role/status; deactivate & reactivate require
confirmation and only change status; reset link requires confirmation and clears only telegram
fields; a `USER`-role actor (and unlinked/deactivated actor) hitting any `users:*` callback gets
`MENU_ACCESS_DENIED`; target-role guard blocks `users:view:{admin_id}`; a newly created user can
then activate and enter the report flow.

Update existing `tests/test_role_menu_flow.py`: the `test_management_menu_callbacks_send_placeholder`
parametrization must drop the two `menu:users` cases (now opens the user menu) and keep
`menu:admins` / `menu:stores` as placeholder assertions. Add/confirm a case that `menu:users` now
routes to `MANAGE_USERS_MENU`.

## Verification

1. `make test` — full suite green (new domain + flow tests, existing daily-report and role-menu
   tests unchanged except the placeholder update).
2. `make seed` then `make up` (or `BOT_MODE=polling`) — smoke `/start` as `USER` (→ report flow
   unchanged), `ADMIN` (→ Admin Menu → Kelola User → add/list/detail/edit/deactivate/reactivate/
   reset), and `SUPER_ADMIN` (same Kelola User via Super Admin Menu; `menu:admins`/`menu:stores`
   still placeholders).
3. Confirm `Input Laporan Harian` from both menus still enters the existing report flow and a
   full report can be submitted.
4. Add a user via the bot, then self-activate as that user by sharing their phone contact and reach
   the report flow; deactivate the user and confirm they can no longer start/activate.

## Risks / follow-ups

- `user_list_keyboard` has no pagination; fine at current scale but a large `USER` set could exceed
  Telegram's inline-keyboard limits — flag as a follow-up if user counts grow.
- Bot-created users get generated IDs not present in `Reference/user_master.csv`, so `make seed`
  won't overwrite or remove them (seed is keyed on `user_id`) — expected, but document it.
- Phase 3 (`Kelola Admin`) should reuse this domain/repo/keyboard machinery with `role=ADMIN` and a
  self-deactivation guard; keep the target-role guard parameterizable to ease that.

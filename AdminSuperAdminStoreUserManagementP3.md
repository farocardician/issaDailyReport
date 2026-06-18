# Phase 3 — Full Admin Management (`Kelola Admin`)

> Phases 1 & 2 are complete and approved. Phase 1 = role routing + menus. Phase 2 = full
> `Kelola User` CRUD (shared by ADMIN & SUPER_ADMIN). This plan covers **Phase 3 only**.

## Context

`Kelola Admin` is the same CRUD as `Kelola User` but scoped to **ADMIN records** and reachable
**only by SUPER_ADMIN**. Add Admin / List Admins / View detail / Edit basic data / Deactivate-
reactivate / Reset Telegram link. New Admin = role `ADMIN`, status `Aktif`, empty Telegram fields.
It must never create or escalate a SUPER_ADMIN; ADMIN and USER are denied; a SUPER_ADMIN must not
deactivate themself. `menu:admins` is currently a `MENU_PLACEHOLDER`; this replaces it.

**Chosen approach (user-selected): parameterize into a shared role-scoped engine.** Generalize the
Phase 2 user-management flow so one set of handlers serves both `users` and `admins`, driven by a
small `ManagementScope` context. The Phase 2 `users` path must stay behaviorally identical and all
existing tests must remain green unchanged (except the one placeholder-test edit below). The domain
(`validate_field`, `is_duplicate_phone`, `generate_user_id`) and repository (`create_user(role=…)`,
`list_by_role`, `list_all`, `set_status`, `reset_telegram_link`, `get_by_id`) are already
role-agnostic and reused as-is — **no domain or repository changes needed**.

## The `ManagementScope` context — new `src/app/bot/management_scope.py`

A frozen dataclass capturing everything role-specific, plus two constants and resolvers:

- `name` — `"users"` | `"admins"` (also the callback prefix and draft discriminator)
- `root_step` — `Step.MANAGE_USERS_MENU` | `Step.MANAGE_ADMINS_MENU` (the persisted submenu step)
- `managed_role` — `Role.USER` | `Role.ADMIN` (target-role guard + `create_user` role)
- `can_manage` — `can_manage_users` | `can_manage_admins` (from `domain/roles.py`)
- `block_self` — `False` | `True` (deny acting on own record; defense-in-depth for SUPER_ADMIN)
- `entity` / `entity_plural` — `"USER"/"USERS"` | `"ADMIN"/"ADMINS"` for copy-key derivation
- `key(suffix)` → role-specific copy key, e.g. `key("DETAIL")` = `USER_DETAIL`/`ADMIN_DETAIL`;
  `menu_key` = `MANAGE_USERS_MENU`/`MANAGE_ADMINS_MENU`.

`SCOPE_USERS`, `SCOPE_ADMINS` constants. `scope_from_callback(data)` (first segment of
`data.split(":",1)[0]`) and `scope_from_draft(draft)` (reads `draft["mgmt_scope"]`). For users
scope every derived key/prefix is identical to Phase 2's hardcoded values — that invariant is what
keeps Phase 2 tests green.

Shared (NOT scoped, reused by both): the validation error keys `USER_ERROR_*` (returned by the
role-agnostic domain `validate_field`), the Telegram-link status keys `USER_TELEGRAM_LINKED_YES/NO`,
and generic buttons `BUTTON_BACK/SAVE/EDIT/CONFIRM_YES/CANCEL/PREVIOUS/SKIP`.

## Steps — `src/app/domain/session_state.py` (add one step)

**Add a distinct `MANAGE_ADMINS_MENU` step** so each scope's submenu root is its own, self-
documenting, testable state — the Admin submenu must NOT persist `MANAGE_USERS_MENU`. The top-level
submenu step is therefore distinct per scope (`users` → `MANAGE_USERS_MENU`, `admins` →
`MANAGE_ADMINS_MENU`, resolved via `scope.root_step`).

The inner states — `USER_LIST`, `USER_DETAIL`, `USER_FORM_INPUT`, `USER_EDIT_MENU`,
`USER_FORM_REVIEW`, `USER_CONFIRM_STATUS`, `USER_CONFIRM_RESET_LINK` — stay **shared** across both
scopes (they are always entered via a scoped `users:`/`admins:` callback and every management draft
carries `"mgmt_scope"`, so they are unambiguous). Their `USER_*` names are historical; renaming them
to `MANAGEMENT_*` is deferred to avoid churning Phase 2 tests. Only the submenu root gets a distinct
name now.

## Flow — `src/app/bot/flow.py` (generalize Phase 2 handlers + new admin entry)

Generalize the Phase 2 private methods to take a `scope` parameter and replace hardcoded bits:
`Role.USER → scope.managed_role`, `can_manage_users → scope.can_manage`, `"users:…" →
f"{scope.name}:…"`, copy keys → `scope.key(...)`. Representative renames (signatures gain `scope`):
`_handle_user_management_callback → _handle_management_callback` (resolves scope via
`scope_from_callback`), `_open_manage_users_menu → _open_management_menu`, `_open_user_list/detail
→ _open_management_list/detail`, `_authorize_user_management → _authorize_management`,
`_load_user_target → _load_management_target`, plus the `_send_*`/`_*_keyboard` helpers. The Phase 2
tests call only the public `handle_callback`/`handle_message`, so private renames are safe; behavior
for the users scope is unchanged because the scope resolves to identical keys/prefix.

Routing changes:
- `handle_callback`: `elif step in MANAGEMENT_CALLBACK_STEPS and data.startswith(("users:",
  "admins:")) → _handle_management_callback(update, session, data)` (replaces the `users:`-only
  branch). `MANAGEMENT_CALLBACK_STEPS` now contains **both** root steps (`MANAGE_USERS_MENU`,
  `MANAGE_ADMINS_MENU`) plus the shared inner steps. Scope = `scope_from_callback(data)`.
- `handle_message`: `USER_FORM_INPUT` / `USER_FORM_REVIEW` resolve scope via `scope_from_draft` and
  delegate to the generic input/review handlers.
- `_open_management_menu(update, actor, scope, notice_key=None)` persists **`scope.root_step`** and
  renders `scope.menu_key` with the scoped keyboard. The `*:back:menu` handler compares the current
  step against `scope.root_step` (root → `_return_to_actor_menu`, otherwise → re-open the submenu).
- Menu entries: in `_handle_super_admin_menu_callback`, replace the `menu:admins` →
  `MENU_PLACEHOLDER` branch (after the existing `can_manage_admins` check) with
  `_open_management_menu(update, actor, SCOPE_ADMINS)` → persists `MANAGE_ADMINS_MENU`. `menu:users`
  (both menus) → `_open_management_menu(update, actor, SCOPE_USERS)` → persists `MANAGE_USERS_MENU`.
  `_handle_admin_menu_callback` has no `menu:admins` and `can_manage_admins(ADMIN)` is false, so
  ADMIN actors cannot reach Admin management.

Guards (server-side, re-checked every callback/text — same pattern as Phase 2):
- `_authorize_management(update, scope)` → `_current_actor` + `scope.can_manage(role)` else
  `MENU_ACCESS_DENIED`.
- `_load_management_target(update, scope, actor, target_id)` denies unless target exists AND
  `normalize_role(target) == scope.managed_role`. For admins this blocks managing USERs, other
  SUPER_ADMINs, and (since the actor is SUPER_ADMIN) the actor's own record. Additionally, when
  `scope.block_self and target_id == actor["user_id"]` → deny (explicit self-action guard; satisfies
  "self-deactivation blocked" directly and is a no-op for the users scope).

Add forces `role = scope.managed_role`, `status = active_status`, Telegram NULL; edit writes only
basic fields; reset clears only the two Telegram columns; status changes are status-only; duplicate
phone uses `list_all()` (all roles/all statuses) in all three places (Add input, Edit input,
save-time revalidation). No DELETE anywhere. (`last active super admin` rule is N/A — Phase 3 never
manages SUPER_ADMIN records.)

## Keyboards — `src/app/bot/keyboards.py`

Parameterize the management keyboard builders with a `prefix` argument and build callback data from
it (`f"{prefix}:add"`, `f"{prefix}:view:{id}"`, …). Rename `manage_users_menu_keyboard →
management_menu_keyboard`, `user_list_keyboard → management_list_keyboard`, `user_detail_keyboard →
management_detail_keyboard`, `user_edit_menu_keyboard → management_edit_menu_keyboard`. `confirm_keyboard`
and the reply keyboards (`user_form_navigation_keyboard`, `user_form_review_keyboard`) are already
scope-agnostic — reuse, passing `f"{prefix}:confirm_status"` / `f"{prefix}:back:detail"`. With
`prefix="users"` the emitted callback data is byte-identical to Phase 2.

## Presentation helpers — `src/app/bot/user_admin_text.py`

Generalize the field-key derivation to be scope-aware: build `ASK_{scope.entity}_{FIELD}` and
`BUTTON_{scope.entity}_FIELD_{FIELD}` from a per-field suffix map (token `USER` reproduces today's
exact keys). `user_detail_tokens` / `user_form_review_tokens` already build plain token dicts and
stay as-is; `_telegram_link_status` keeps the shared `USER_TELEGRAM_LINKED_*` keys.

## UI copy — `Reference/ui_translate.csv`

Add the `ADMIN_*` parallel of every role-specific Phase 2 `USER_*` row, with admin wording/labels:
`MANAGE_ADMINS_MENU`, `ADMIN_LIST`, `ADMIN_LIST_EMPTY`, `ADMIN_LIST_BUTTON`, `ADMIN_DETAIL`,
`ASK_ADMIN_NAME/PHONE/EMAIL/NOTES`, `ADMIN_FORM_REVIEW`, `ADMIN_EDIT_MENU`,
`ADMIN_CONFIRM_DEACTIVATE/REACTIVATE/RESET_LINK`,
`ADMIN_ADDED/UPDATED/DEACTIVATED/REACTIVATED/LINK_RESET`,
`BUTTON_ADMIN_ADD/LIST/EDIT/DEACTIVATE/REACTIVATE/RESET_LINK`,
`BUTTON_ADMIN_FIELD_NAME/PHONE/EMAIL/NOTES` (labels "Tambah Admin", "Daftar Admin", "Kelola Admin",
etc.). Reuse the shared keys above (no new error/telegram/generic-button rows). No `seed.py` change:
prefixes route categories automatically (`BUTTON_`→button, `ASK_`→prompt; bare `ADMIN_*` →
`admin_notification`, which is a cosmetic category-column value only and does not affect rendering).

## Tests

New `tests/test_admin_management_flow.py` mirroring `tests/test_user_management_flow.py` but
scope=admins, with its own `_templates()` including the `ADMIN_*`, `MANAGE_ADMINS_MENU`, and shared
(`USER_ERROR_*`, `USER_TELEGRAM_LINKED_*`) stubs. Cover (SUPER_ADMIN actor unless noted):
`menu:admins` **persists `Step.MANAGE_ADMINS_MENU`** and opens it with
`["admins:add","admins:list","admins:back:menu"]`;
add happy path persists only after Simpan and creates a `ADMIN`/`Aktif`/no-Telegram record; list /
detail render; edit updates basic fields only (role/status/Telegram untouched); deactivate &
reactivate require confirmation and change only status; reset link requires confirmation, clears
only Telegram; duplicate phone rejected — including against an existing USER and a SUPER_ADMIN
record (global rule); target-role guard blocks `admins:view:{user_id}` (a USER) and
`admins:view:{super_admin_id}`; **self-deactivation blocked** (`admins:deactivate:{own_id}` denied);
ADMIN and USER actors hitting `menu:admins` or any `admins:*` callback get `MENU_ACCESS_DENIED`; a
newly created Admin can activate (share phone) and land on the Admin Menu.

Update `tests/test_role_menu_flow.py`: drop the `menu:admins` row from
`test_management_menu_callbacks_send_placeholder`'s parametrize (leaving only `menu:stores`); add a
case asserting `menu:admins` **persists `Step.MANAGE_ADMINS_MENU`** and renders `MANAGE_ADMINS_MENU`
with `["admins:add","admins:list","admins:back:menu"]` (mirroring the existing
`test_menu_users_callback_opens_manage_users_menu`, which keeps asserting `menu:users` persists
`Step.MANAGE_USERS_MENU`); add `MANAGE_ADMINS_MENU` + needed `ADMIN_*` stubs to that file's
`_templates()`. The existing `test_super_admin_menu_admin_actor_cannot_manage_admins` (ADMIN denied)
stays valid unchanged. All Phase 2 tests (`test_user_management_flow.py`, `test_user_management.py`)
must pass **unchanged** — `menu:users` still persists `Step.MANAGE_USERS_MENU`.

## Verification

1. `docker compose run --rm bot pytest -q` — full suite green (new admin tests + all Phase 2/role
   tests unchanged except the placeholder edit).
2. `make seed` — loads the new `ADMIN_*` copy; spot-check the new keys/categories exist.
3. `make up` (or `BOT_MODE=polling`); smoke `/start` as **SUPER_ADMIN** → Super Admin Menu →
   `Kelola Admin` → add / list / detail / edit / deactivate / reactivate / reset; confirm
   self-deactivation is blocked. As **ADMIN** → no `Kelola Admin` (and a crafted `menu:admins` is
   denied). Confirm `Kelola User` (users scope) and the daily report flow are unchanged.
4. Add an Admin via the bot, self-activate by sharing that phone, and confirm landing on the Admin
   Menu; deactivate the Admin and confirm they can no longer start/activate.

## Risks / follow-ups

- Submenu roots are now distinct (`MANAGE_USERS_MENU` / `MANAGE_ADMINS_MENU`). The shared inner
  steps keep historical `USER_*` names though generic — they always carry `mgmt_scope`; a rename to
  `MANAGEMENT_*` is deferred to avoid churning Phase 2 tests.
- Bare `ADMIN_*` copy keys land in the `admin_notification` seed category (cosmetic only).
- The parameterization touches approved Phase 2 flow code; the comprehensive Phase 2 test suite
  (run unchanged) is the regression guard.
- Phase 4 (`Kelola Store`) is a different entity (no Telegram, different identity/validation) and
  will not reuse this person-scoped engine directly.

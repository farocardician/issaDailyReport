# Phase 1 — Role Foundation, Menus, and Daily Report Entry

## Context

`AdminSuperAdminStoreUserManagement.md` adds role-based management (`USER` / `ADMIN` /
`SUPER_ADMIN`) on top of the existing SPG daily-report bot, in 4 independently-testable
phases. **Phase 1 only** introduces role normalization, post-auth routing, and the two base
menus — management actions are placeholders. The daily report flow must stay byte-for-byte
unchanged and every existing test must stay green.

Today the bot has no concept of roles in its routing: `flow.handle_start` and
`flow._handle_phone_contact` both call `_start_report_flow(update, user)` for *any* role.
The `users.role` column already exists (free text; seed currently has one row `USR-0001`
with role `Admin`, and tests use legacy `SPG`). Phase 1 inserts a routing decision between
"who is this authenticated user" and "where do they go".

Per the user's decision, `USR-0001` becomes the default `SUPER_ADMIN` (seeded), so a Super
Admin exists on every deploy including the future VPS.

## Design principles (from spec + repo)

- **Domain owns the decision; flow only reacts.** Role normalization, permission predicates,
  and role→menu-step mapping live in a new pure `domain/roles.py`. `flow.py` just routes to
  the `Step` the domain returns (mirrors how `session_state.next_step` is used today).
- **No new architecture.** Reuse `_persist`, `_send`, `_refresh_templates`, the inline-keyboard
  pattern (`sales_source_keyboard` etc.), and the `find_active_by_telegram_user_id` re-check
  that `handle_start` already performs.
- **Server-side permission on every protected callback** — re-fetch the active user by
  `telegram_user_id` at action time and re-derive role; never trust the persisted menu step or
  callback data alone.
- **All user-facing copy via `ui_translate` + `Reference/ui_translate.csv`.** No hardcoded
  strings. Menus carry **no** daily-report progress text.

## Changes

### 1. New domain module — `src/app/domain/roles.py` (pure, unit-tested)

```python
class Role(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

def normalize_role(raw: str | None) -> Role:
    # strip + casefold/upper; "ADMIN"->ADMIN; "SUPER_ADMIN"/"SUPERADMIN"->SUPER_ADMIN;
    # "SPG", "USER", "", None, anything unknown -> Role.USER  (safe fallback)

def menu_step_for_role(role: Role) -> Step | None:
    # ADMIN -> Step.ADMIN_MENU ; SUPER_ADMIN -> Step.SUPER_ADMIN_MENU ; else None (report flow)

def can_manage_users(role: Role) -> bool   # ADMIN or SUPER_ADMIN
def can_manage_admins(role: Role) -> bool  # SUPER_ADMIN only
def can_manage_stores(role: Role) -> bool  # SUPER_ADMIN only
```

Imports `Step` from `domain/session_state.py` only (no telegram/db imports — stays within the
domain layer).

### 2. `src/app/domain/session_state.py`

Add two terminal menu steps to the `Step` enum: `ADMIN_MENU = "ADMIN_MENU"`,
`SUPER_ADMIN_MENU = "SUPER_ADMIN_MENU"`. Do **not** add them to `_NEXT_STEPS` (menus are not
part of the linear report progression).

### 3. `src/app/bot/keyboards.py`

Two new inline-keyboard builders (label args rendered by flow, stable namespaced callback data):

```python
def admin_menu_keyboard(report_label, users_label) -> InlineKeyboardMarkup
    #  menu:report , menu:users
def super_admin_menu_keyboard(report_label, users_label, admins_label, stores_label) -> InlineKeyboardMarkup
    #  menu:report , menu:users , menu:admins , menu:stores
```

### 4. `src/app/bot/flow.py` (orchestration only)

- **Import** `Role, normalize_role, menu_step_for_role, can_manage_users, can_manage_admins,
  can_manage_stores` and the two keyboard builders.
- **New `_route_after_auth(update, user)`** — the single post-auth router:
  ```
  role = normalize_role(user.get("role"))
  step = menu_step_for_role(role)
  if step is None:                      # USER / SPG / unknown / blank
      await self._start_report_flow(update, user); return
  await self._persist(update, step, {"user_name": user["name"]}, user_id=user["user_id"])
  await self._send_menu(update, step)
  ```
- **Redirect the 3 existing `_start_report_flow` call sites** to `_route_after_auth`:
  `handle_start` (linked single user, ~line 112) and `_handle_phone_contact`
  (`ACTIVATED` ~243 and `ALREADY_LINKED` ~247). `_start_report_flow` itself is unchanged and
  still the report entry point reused by `menu:report`.
- **New `_send_menu(update, step)`** — renders `MENU_ADMIN` / `MENU_SUPER_ADMIN` with the
  matching inline keyboard, **no `progress_step`**.
- **New `_current_actor(update)`** — server-side re-check:
  `users = find_active_by_telegram_user_id(effective_user.id, active_status)`;
  return `users[0]` iff exactly one, else `None`. `None` ⇒ deactivated/unlinked ⇒ deny.
- **`handle_callback` dispatch** — add two branches keyed on the persisted step:
  ```
  elif step == Step.ADMIN_MENU:        await self._handle_admin_menu_callback(update, session, data)
  elif step == Step.SUPER_ADMIN_MENU:  await self._handle_super_admin_menu_callback(update, session, data)
  ```
- **`_handle_admin_menu_callback` / `_handle_super_admin_menu_callback`** — each:
  1. `actor = await self._current_actor(update)`; if `None` → `_send("MENU_ACCESS_DENIED")`.
  2. `role = normalize_role(actor["role"])`.
  3. `menu:report` → `_start_report_flow(update, actor)` (allowed for every active role).
  4. `menu:users` → guard `can_manage_users(role)` else `MENU_ACCESS_DENIED`; then placeholder.
  5. (super-admin handler only) `menu:admins` → guard `can_manage_admins`; `menu:stores` →
     guard `can_manage_stores`; else placeholder.
  6. anything else → `UNKNOWN_COMMAND`.
  - Placeholder = `_send(update, "MENU_PLACEHOLDER")`; step is left unchanged so the menu's
    inline keyboard stays tappable (user can still pick `Input Laporan Harian`).
- **Keyboard helper methods** `_admin_menu_keyboard()` / `_super_admin_menu_keyboard()` that
  `_refresh_templates()` then build from `BUTTON_MENU_*` labels (same shape as existing
  `_summary_keyboard()` etc.).

Net effect on existing behavior: a `USER`/`SPG`/unknown-role user follows the *exact* current
path (`_route_after_auth` → `menu_step_for_role` returns `None` → `_start_report_flow`).

### 5. UI copy — `Reference/ui_translate.csv` (+ `make seed`)

Add rows (all `MENU_`-prefixed → category `message`; `BUTTON_`-prefixed → `button`):

| key | message (Bahasa Indonesia) |
|---|---|
| `MENU_ADMIN` | `Menu Admin\n\nSilakan pilih menu:` |
| `MENU_SUPER_ADMIN` | `Menu Super Admin\n\nSilakan pilih menu:` |
| `MENU_PLACEHOLDER` | `🚧 Fitur ini akan segera tersedia.` |
| `MENU_ACCESS_DENIED` | `Kamu tidak punya akses untuk tindakan ini.` |
| `BUTTON_MENU_INPUT_REPORT` | `Input Laporan Harian` |
| `BUTTON_MENU_MANAGE_USERS` | `Kelola User` |
| `BUTTON_MENU_MANAGE_ADMINS` | `Kelola Admin` |
| `BUTTON_MENU_MANAGE_STORES` | `Kelola Store` |

### 6. Default Super Admin — `Reference/user_master.csv`

Change the single existing data row's `User_Role` cell **only**: `USR-0001` `Admin` →
`SUPER_ADMIN`. One-cell role edit, no contact data added/changed; file stays excluded from the
repomix bundle (do not touch `repomix.config.json`). On `make seed` (here and on the VPS),
`USR-0001` becomes the default Super Admin. `normalize_role` already maps existing `Admin`
strings to `ADMIN`, so any other Admin rows added later route to the Admin Menu automatically.

## Tests (new, follow existing fakes — keep all current tests green)

- **`tests/test_roles.py`** (pure domain): `normalize_role` for `ADMIN`, `SUPER_ADMIN`,
  `SUPERADMIN`, lowercase, `SPG`→`USER`, `""`/`None`/`"random"`→`USER`;
  `menu_step_for_role`; the three `can_manage_*` predicates.
- **`tests/test_role_menu_flow.py`** (async flow via the `_FakeUsers`/`_FakeSessions`/
  `_FakeChat`/`_FakeCallbackQuery`/`_FakeUpdate` pattern copied from
  `tests/test_activation_flow.py` + `tests/test_sales_flow.py`):
  - `SPG` linked user `/start` → `AWAITING_LOCATION` (report flow unchanged).
  - `ADMIN` linked user `/start` → `ADMIN_MENU`, message contains `MENU_ADMIN`, keyboard has
    `menu:report` + `menu:users` only.
  - `SUPER_ADMIN` linked user `/start` → `SUPER_ADMIN_MENU`, keyboard has all four buttons.
  - Unknown/blank role linked user `/start` → `AWAITING_LOCATION` (safe fallback).
  - Activation (`AWAITING_PHONE` + contact share) for an `ADMIN`/`SUPER_ADMIN` row → routes to
    the menu, not the report flow.
  - `menu:report` callback (ADMIN and SUPER_ADMIN) → `_start_report_flow` → `AWAITING_LOCATION`.
  - `menu:users` (ADMIN & SUPER_ADMIN), `menu:admins`/`menu:stores` (SUPER_ADMIN) → `MENU_PLACEHOLDER`.
  - **Inactive user**: `handle_start` with no active linked user → `AWAITING_PHONE` (cannot start).
  - **Wrong-role denial**: session at `SUPER_ADMIN_MENU` but `_current_actor` resolves role
    `ADMIN`, callback `menu:admins` → `MENU_ACCESS_DENIED` (server-side re-check).
  - **Deactivated mid-session**: menu callback where `find_active_by_telegram_user_id` returns
    `[]` → `MENU_ACCESS_DENIED`.
  - Include the new `MENU_*` / `BUTTON_MENU_*` keys in the test's local `_templates()` dict.

## Verification

1. `make test` — full suite (new `test_roles.py`, `test_role_menu_flow.py`, and **all existing
   tests, especially `test_activation_flow.py` / `test_location_flow.py` / `test_sales_flow.py`
   / `test_stock_issue_flow.py`, stay green**).
2. `make seed` — loads the new `ui_translate` rows and flips `USR-0001` to `SUPER_ADMIN`.
3. `make up`, then smoke `/start` (polling or tunnel):
   - `USR-0001` (now `SUPER_ADMIN`) → Super Admin Menu (4 buttons).
   - A `USER`/`SPG` row → goes straight into the daily report (location prompt) — unchanged.
   - `Input Laporan Harian` from the Super Admin Menu → reaches the same location/store/sales
     flow and a report can be submitted end-to-end.
   - `Kelola User` / `Kelola Admin` / `Kelola Store` → placeholder message; menu stays usable.
   - To smoke an `ADMIN` specifically, temporarily set a row's role to `ADMIN` (DB or CSV) and
     `/start`.

## Risks / follow-ups

- The previously-seeded `Admin` (`USR-0001`) now lands on a menu instead of the report directly
  — that is the intended Phase 1 behavior; the report is one tap away via `Input Laporan Harian`.
- `Reference/user_master.csv` is sensitive (real contacts) — only the one role cell changes and
  it must never be committed with contact edits nor added to repomix includes.
- Phases 2–4 will replace the `MENU_PLACEHOLDER` handlers with real CRUD; the namespaced
  `menu:*` callback data and the `_current_actor` re-check are designed to extend without churn.
- No schema migration needed (the `role` column already exists). The "last active Super Admin
  cannot self-deactivate" safety rule is a Phase 3 concern, out of scope here.

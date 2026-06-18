# Admin, Super Admin, Store, and User Management Master Plan

## 1. Goal

Add role-based management to the existing Telegram bot without disturbing the current daily store report flow.

The bot should support three main roles:

* `SUPER_ADMIN`
* `ADMIN`
* `USER`

Existing `SPG` records should be treated as `USER` through safe normalization or read-time role handling, so old report users continue working.

The final system should allow:

* `SUPER_ADMIN` to submit daily reports, manage Users, manage Admins, and manage Stores.
* `ADMIN` to submit daily reports and manage Users.
* `USER` to submit the existing daily store report.

The daily report flow must remain stable and must keep passing all existing tests.

---

## 2. Core Principle

This is an expansion of the current bot, not a rewrite.

The implementation must follow the existing repository structure.

No new architecture should be invented.

Key rules:

* Domain logic stays in `domain/`.
* SQL/database access stays in `repositories/`.
* Telegram orchestration stays in `bot/flow.py`.
* User-facing copy stays in `ui_translate` and `Reference/ui_translate.csv`.
* Schema changes, if needed, must be idempotent.
* Every phase must be testable independently.
* Existing daily report behavior must remain unchanged.

---

## 3. Role Permissions

| Role | Main access |
|---|---|
| `SUPER_ADMIN` | Can submit daily reports and manage Users, Admins, and Stores. |
| `ADMIN` | Can submit daily reports and manage Users. |
| `USER` | Can submit daily reports only. |

Rules:

* `USER` enters the existing daily report flow directly.
* `ADMIN` sees Admin Menu with `Input Laporan Harian` and `Kelola User`.
* `SUPER_ADMIN` sees Super Admin Menu with `Input Laporan Harian`, `Kelola User`, `Kelola Admin`, and `Kelola Store`.
* `ADMIN` must not access `Kelola Admin` or `Kelola Store`.
* `USER` must not access any management menu.
* `SUPER_ADMIN` has access to the same User management capability as `ADMIN`.
* Permission checks must happen server-side on every protected callback, not only by hiding buttons.
* Inactive users must not be able to start or activate into protected flows.

---

## 4. Target Menu Structure

The final menu structure should be:

```text
/start or activation
  ├─ USER → existing daily report flow
  ├─ ADMIN → Admin Menu
  │    ├─ Input Laporan Harian → existing daily report flow
  │    └─ Kelola User
  │         ├─ Tambah User
  │         └─ Daftar User
  │              └─ User Detail
  │                   ├─ Ubah Data
  │                   ├─ Nonaktifkan / Aktifkan Kembali
  │                   └─ Reset Link Telegram
  └─ SUPER_ADMIN → Super Admin Menu
       ├─ Input Laporan Harian → existing daily report flow
       ├─ Kelola User
       │    ├─ Tambah User
       │    └─ Daftar User
       │         └─ User Detail
       │              ├─ Ubah Data
       │              ├─ Nonaktifkan / Aktifkan Kembali
       │              └─ Reset Link Telegram
       ├─ Kelola Admin
       │    ├─ Tambah Admin
       │    └─ Daftar Admin
       │         └─ Admin Detail
       │              ├─ Ubah Data
       │              ├─ Nonaktifkan / Aktifkan Kembali
       │              └─ Reset Link Telegram
       └─ Kelola Store
            ├─ Tambah Store
            └─ Daftar Store
                 └─ Store Detail
                      ├─ Ubah Data
                      └─ Nonaktifkan / Aktifkan Kembali
```

Notes:

* `Input Laporan Harian` must call the same existing report flow used by `USER`.
* The daily report flow must not be duplicated or rewritten.
* `Kelola User` should be implemented once and reused by both `ADMIN` and `SUPER_ADMIN`.
* `Kelola Admin` is only for `SUPER_ADMIN`.
* `Kelola Store` is only for `SUPER_ADMIN`.

---

## 5. Role Routing

After `/start` or successful activation, route the user based on role:

* `USER` or legacy `SPG` → existing daily report flow.
* `ADMIN` → Admin Menu.
* `SUPER_ADMIN` → Super Admin Menu.

Unknown or blank roles should safely fall back to `USER`, not Admin or Super Admin.

For `ADMIN` and `SUPER_ADMIN`, the daily report flow is still available from the menu through:

```text
Input Laporan Harian → existing daily report flow
```

The existing daily report flow must reuse the current report flow entry point.

---

## 6. Navigation Rules

Use one consistent navigation model across all management flows.

### `Batal`

`Batal` ends the current session.

Use it only inside guided input/edit flows, such as:

* Add User
* Edit User
* Add Admin
* Edit Admin
* Add Store
* Edit Store

When pressed, it should clear the session and return to the cancelled/start state.

### `Kembali`

`Kembali` is navigation only.

Use it on menus, lists, detail screens, and confirmation screens.

It should move one level back and must not clear the session.

### `Sebelumnya`

`Sebelumnya` moves one step back inside a guided input flow.

It should preserve already-entered draft data.

### Confirmation Screens

Risky actions must use confirmation screens with:

* `Ya`
* `Kembali`

Do not use `Batal` on confirmation screens.

---

## 7. Main Functional Scope

## A. Role Routing

Route users after `/start` or successful activation based on role.

Required behavior:

* `USER` or legacy `SPG` goes to the existing daily report flow.
* `ADMIN` goes to Admin Menu.
* `SUPER_ADMIN` goes to Super Admin Menu.
* Unknown or blank roles safely fall back to `USER`.
* Existing daily report tests stay green.

---

## B. Shared User Management

`ADMIN` and `SUPER_ADMIN` should both be able to manage User records through:

```text
Admin Menu / Super Admin Menu → Kelola User
```

Required capabilities:

* Add User
* List Users
* View User Detail
* Edit User basic data
* Deactivate/reactivate User
* Reset Telegram link

User fields that can be managed:

* name
* phone
* email
* notes
* status
* Telegram link fields, only for reset

User fields that must not be edited through normal edit flow:

* role
* historical report relations

Add User must create a new user with:

* role `USER`
* status `Aktif`
* empty Telegram link fields

Rules:

* `ADMIN` may manage only `USER` records.
* `SUPER_ADMIN` may also manage `USER` records.
* Neither `ADMIN` nor `SUPER_ADMIN` should edit a User into an Admin through `Kelola User`.
* Role escalation must never happen from `Kelola User`.
* Duplicate phone numbers must be rejected using normalized phone comparison.
* A newly added User should be able to self-activate later by sharing the registered phone contact.

---

## C. Super Admin: Admin Management

`SUPER_ADMIN` should be able to manage Admin records through:

```text
Super Admin Menu → Kelola Admin
```

Required capabilities:

* Add Admin
* List Admins
* View Admin Detail
* Edit Admin basic data
* Deactivate/reactivate Admin
* Reset Telegram link

Admin fields that can be managed:

* name
* phone
* email
* notes
* status
* Telegram link fields, only for reset

Admin fields that must not be edited through normal edit flow:

* role
* historical report relations

Add Admin must create a new user with:

* role `ADMIN`
* status `Aktif`
* empty Telegram link fields

Rules:

* Only `SUPER_ADMIN` can access `Kelola Admin`.
* `ADMIN` must not be able to create, edit, deactivate, reactivate, or reset Admin records.
* Duplicate phone numbers must be rejected using normalized phone comparison.
* A newly added Admin should be able to self-activate later by sharing the registered phone contact.

---

## D. Super Admin: Store Management

`SUPER_ADMIN` should be able to manage Store records through:

```text
Super Admin Menu → Kelola Store
```

Required capabilities:

* Add Store
* List Stores
* View Store Detail
* Edit Store fields
* Deactivate/reactivate Store

Store fields:

* department store / partner
* branch
* city
* brand
* latitude
* longitude
* allowed radius
* notes
* status

Add Store must create an active store that immediately becomes usable by the existing report location/store selection flow.

Store identity should be based on:

* brand
* department store / partner
* branch
* city

Rules:

* Only `SUPER_ADMIN` can access `Kelola Store`.
* Duplicate active store identity must be rejected.
* If an inactive store has the same identity as another active store, it must not be reactivated.
* Store deactivation must be non-destructive.
* Store status changes must not delete or modify historical daily reports.
* Inactive stores must disappear from active store matching/selection.
* Stores do not have Telegram link reset actions.

---

## 8. Safety Rules

The full implementation must follow these rules:

* No hard delete for users or stores.
* Deactivate/reactivate must be status-only.
* Risky actions require confirmation.
* Reset Telegram link clears only `telegram_user_id` and `telegram_chat_id`.
* Historical `daily_reports` must never be deleted or broken.
* Deactivated users cannot start or activate.
* Deactivated stores must not appear in active store matching.
* Super Admin must not be able to deactivate themself.
* If later multiple Super Admins are supported, the last active Super Admin must not be deactivated.
* All protected actions must re-check the actor’s current active role at action time.

---

## 9. Data and Architecture Rules

Keep the implementation aligned with the current codebase.

### Domain Layer

Use the domain layer for:

* role normalization
* phone validation
* user/admin validators
* store validators
* duplicate detection helpers
* step transition helpers

### Repository Layer

Use repositories for:

* list/get/create/update methods for users and stores
* SQL queries
* database persistence

Repositories should not contain Telegram-specific code.

### Bot Flow Layer

Use `bot/flow.py` for:

* menu rendering
* callback routing
* input step orchestration
* review/confirmation handling
* server-side permission checks

### UI Translation

Use `ui_translate` for all user-facing copy.

Rules:

* no hardcoded bot messages
* menu/list/detail/management screens should not use daily report progress text
* all buttons should use translated labels
* callback data should be stable and namespaced

---

## 10. Validation Rules

### User/Admin Validation

* name is required
* phone is required and normalized
* duplicate phone is rejected
* email is optional but must be valid when provided
* notes are optional

### Store Validation

* department/partner is required
* branch is required
* city is required
* brand is required
* latitude must be valid
* longitude must be valid
* allowed radius must be a positive number
* notes are optional
* duplicate active store identity is rejected

### Edit Validation

* keeping the current record’s own phone or store identity is allowed
* changing to another active record’s duplicate phone/store identity is rejected
* editing basic data must not modify role, status, Telegram link, or historical report relations unless the action specifically targets that field

---

## 11. Testing Strategy

Every implementation phase must include tests before moving forward.

Required test coverage:

* role routing
* permission denial for wrong roles
* inactive user behavior
* menu navigation
* daily report entry from Admin and Super Admin menus
* add flows
* list/detail flows
* edit flows
* duplicate validation
* confirmation behavior
* deactivate/reactivate behavior
* reset Telegram link behavior
* daily report regression

After every phase:

* run all tests
* seed data
* smoke test `/start` as `USER`, `ADMIN`, and `SUPER_ADMIN`
* verify existing daily report flow still works
* verify `ADMIN` and `SUPER_ADMIN` can enter daily report through `Input Laporan Harian`

---

## 12. Four-Phase Roadmap

The detailed phased plan should be split into four larger phases.

### Phase 1: Role Foundation, Menus, and Daily Report Entry

Introduce roles, role normalization, post-auth routing, and base menus.

Includes:

* `USER` → existing daily report flow
* `ADMIN` → Admin Menu
  * `Input Laporan Harian`
  * `Kelola User`
* `SUPER_ADMIN` → Super Admin Menu
  * `Input Laporan Harian`
  * `Kelola User`
  * `Kelola Admin`
  * `Kelola Store`

Acceptance:

* `USER` can still submit the daily report exactly as before.
* `ADMIN` can open Admin Menu and start the daily report from `Input Laporan Harian`.
* `SUPER_ADMIN` can open Super Admin Menu and start the daily report from `Input Laporan Harian`.
* Management menu buttons may still be placeholders in this phase.
* All old daily report tests still pass.

---

### Phase 2: Shared User Management

Build `Kelola User` once and allow access from both `ADMIN` and `SUPER_ADMIN`.

Includes:

* Add User
* List Users
* User Detail
* Edit User
* Deactivate/reactivate User
* Reset Telegram link

Acceptance:

* `ADMIN` can manage Users.
* `SUPER_ADMIN` can manage Users through the same flow.
* `ADMIN` cannot manage Admins or Stores.
* User management cannot escalate a User into Admin or Super Admin.
* New Users can activate and enter the existing daily report flow.
* Existing daily report behavior remains unchanged.

---

### Phase 3: Super Admin Admin Management

Build `Kelola Admin` for `SUPER_ADMIN`.

Includes:

* Add Admin
* List Admins
* Admin Detail
* Edit Admin
* Deactivate/reactivate Admin
* Reset Telegram link

Acceptance:

* `SUPER_ADMIN` can manage Admins.
* `ADMIN` cannot access Admin management.
* Admin management cannot edit Admins into Super Admins.
* New Admins can activate and access Admin Menu.
* Deactivated Admins cannot start or activate.
* Existing daily report behavior remains unchanged.

---

### Phase 4: Super Admin Store Management

Build `Kelola Store` for `SUPER_ADMIN`.

Includes:

* Add Store
* List Stores
* Store Detail
* Edit Store
* Deactivate/reactivate Store

Acceptance:

* `SUPER_ADMIN` can manage Stores.
* `ADMIN` cannot access Store management.
* New active Stores can be used by the existing report flow.
* Deactivated Stores disappear from active store matching/selection.
* Reactivating a Store is blocked if its identity conflicts with another active Store.
* Historical daily reports remain intact.
* Existing daily report behavior remains unchanged.

---

## 13. Completion Definition

This project is complete when:

* `SUPER_ADMIN` can submit daily reports and fully manage Users, Admins, and Stores.
* `ADMIN` can submit daily reports and fully manage Users.
* `USER` can submit daily reports exactly as before.
* wrong-role access is blocked server-side.
* inactive users and stores are excluded from active flows.
* historical reports remain intact.
* all management actions are confirmed, safe, and non-destructive.
* all existing and new tests pass.

---

## 14. Notes for Later Detailed Phase Planning

When converting this master plan into detailed phase prompts:

* Keep each phase independently testable.
* Do not combine Phase 1 with management CRUD implementation.
* Implement shared `Kelola User` once, then reuse it for both `ADMIN` and `SUPER_ADMIN`.
* Keep `Kelola Admin` and `Kelola Store` Super Admin-only.
* Preserve the existing daily report flow entry point.
* Make sure `Input Laporan Harian` for Admin and Super Admin calls the same report flow as User.
* Keep all permission checks server-side.

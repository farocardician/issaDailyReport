# Admin and Super Admin Role Management Master Plan

## 1. Goal

Add role-based management to the existing Telegram bot without changing the current daily report flow.

Target roles:

* `SUPER_ADMIN`
* `ADMIN`
* `USER`

Use `USER` as the generic daily-report role. Existing `SPG` data should be migrated or normalized to `USER`, but the current report flow must continue working during transition.

Follow:

* `CLAUDE.md` for architecture, layering, schema, tests, and Codegen rules.
* `README.md` for current product behavior.
* `TelegramBotUIUXGuideline.md` for Telegram flow, copy style, buttons, validation, review, cancel, previous, and confirmation behavior.

Do not invent a new architecture.

---

## 2. Role Permissions

| Role          | Permissions                                                                        |
| ------------- | ---------------------------------------------------------------------------------- |
| `SUPER_ADMIN` | Open Super Admin menu, add Admin, add Store, later manage Admin and Store records. |
| `ADMIN`       | Open Admin menu, add User, later manage User records.                              |
| `USER`        | Use the existing daily store report flow.                                          |

Rules:

* `ADMIN` must not access Super Admin features.
* `USER` must not access Admin or Super Admin features.
* All permission checks must happen server-side, not only through visible buttons.

---

## 3. Phase Plan

## Phase 1 — Role Routing + Menus

### Goal

Route users after `/start` or activation based on `users.role`.

### Flow

* `USER` → existing daily report flow.
* `ADMIN` → Admin menu.
* `SUPER_ADMIN` → Super Admin menu.

### Main work

* Add role constants/helper in domain layer.
* Add new session steps for Admin menu and Super Admin menu.
* Add menu keyboards.
* Add required `ui_translate` keys.
* Normalize legacy `SPG` role to `USER` safely.

### Tests

* `USER` still starts the existing report flow.
* Legacy `SPG` still works or is migrated to `USER`.
* `ADMIN` sees Admin menu.
* `SUPER_ADMIN` sees Super Admin menu.
* Inactive users cannot start.
* Unknown role is handled safely.

### Acceptance

Current report flow still passes all existing tests.

---

## Phase 2 — Super Admin Add Admin

### Goal

Allow Super Admin to create Admin users.

### Flow

`Super Admin Menu → Tambah Admin → name → phone → email optional → notes optional → review → save`

### Main work

* Add Add Admin steps.
* Reuse existing phone activation concept.
* New Admin should have:

  * role `ADMIN`
  * status `Aktif`
  * empty Telegram link fields
* Prevent duplicate phone numbers.
* Add required repository methods.
* Add `ui_translate` keys.

### Tests

* Super Admin can add Admin.
* Admin/User cannot add Admin.
* Duplicate phone is rejected.
* Invalid input reprompts.
* Save only happens after review confirmation.
* New Admin can activate through existing contact share.

### Acceptance

New Admin can be created and later activated by sharing the registered phone contact.

---

## Phase 3 — Super Admin Add Store

### Goal

Allow Super Admin to create stores.

### Flow

`Super Admin Menu → Tambah Store → store fields → review → save`

### Required fields

* department store / partner
* branch
* city
* brand
* latitude
* longitude
* allowed radius
* notes optional

### Main work

* Add Add Store steps.
* Add validation for required fields, coordinates, and radius.
* Generate store ID safely.
* Prevent duplicate active store identity.
* Add repository methods.
* Add `ui_translate` keys.

### Tests

* Super Admin can add Store.
* Admin/User cannot add Store.
* Invalid latitude/longitude/radius reprompts.
* Duplicate store is rejected.
* Save only happens after review confirmation.
* New active store appears in existing store selection/matching flow.

### Acceptance

New store can be used by the existing daily report flow.

---

## Phase 4 — Admin Add User

### Goal

Allow Admin to create User accounts.

### Flow

`Admin Menu → Tambah User → name → phone → email optional → notes optional → review → save`

### Main work

* Reuse the Add Admin pattern.
* Role is fixed to `USER`.
* Status is `Aktif`.
* Telegram link fields are empty.
* Prevent duplicate phone numbers.
* Add `ui_translate` keys.

### Tests

* Admin can add User.
* Admin cannot add Admin or Super Admin.
* Super Admin-only callbacks are denied for Admin.
* Duplicate phone is rejected.
* Save only happens after review confirmation.
* New User can activate through existing contact share and enter the report flow.

### Acceptance

Admin can create a User without receiving Super Admin permissions.

---

## Phase 5 — Edit / Deactivate / Reset Link

### Goal

Add safe management actions for existing records.

### Scope

Super Admin can manage:

* Admin users
* Stores

Admin can manage:

* Users

### Actions

For users:

* edit basic fields
* deactivate
* reactivate
* reset Telegram link

For stores:

* edit store fields
* deactivate
* reactivate

### Safety rules

* No hard delete.
* Risky actions require confirmation.
* Reset Telegram link clears only Telegram link fields.
* Deactivated users cannot activate/start.
* Deactivated stores do not appear in active store selection.
* Do not delete or break historical reports.
* Prevent Super Admin from deactivating themself or the last active Super Admin.

### Tests

* Correct role can manage correct records.
* Wrong role is denied.
* Edit saves only after confirmation.
* Deactivate/reactivate requires confirmation.
* Reset link requires confirmation.
* Inactive users/stores are excluded from active flows.
* Existing report tests still pass.

### Acceptance

Management actions are safe, permission-checked, and non-destructive.

---

## 4. Implementation Order

The five phases are correctly sized.

Recommended order:

1. Phase 1 — Role Routing + Menus
2. Phase 2 — Super Admin Add Admin
3. Phase 3 — Super Admin Add Store
4. Phase 4 — Admin Add User
5. Phase 5 — Edit / Deactivate / Reset Link

Do not combine Phase 1 with other phases. It is the foundation and must be tested alone.

Phase 5 may be split only if it becomes too large:

* Phase 5A — manage users
* Phase 5B — manage stores

---

## 5. Codegen Checklist

Before coding:

* Read `CLAUDE.md`, `README.md`, and `TelegramBotUIUXGuideline.md`.
* Understand the existing repo from `repomix-output.md`.
* Preserve existing daily report behavior.

During coding:

* Keep domain logic in `domain/`.
* Keep SQL in `repositories/`.
* Keep orchestration in `bot/flow.py`.
* Keep user-facing copy in `ui_translate` and `Reference/ui_translate.csv`.
* Keep schema changes idempotent in `sql/schema.sql`.
* Follow existing keyboard, progress, validation, review, cancel, and previous behavior.
* Add tests per phase.

After coding each phase:

* Run `make test`.
* Run `make seed`.
* Smoke test `/start` for `USER`, `ADMIN`, and `SUPER_ADMIN`.
* Update `README.md` and `CLAUDE.md` in the existing style.

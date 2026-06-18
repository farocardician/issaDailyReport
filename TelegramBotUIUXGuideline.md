# Telegram Bot UI/UX Guideline

## Purpose

This guideline defines the standard Telegram bot interaction style for future projects.

Use it as a reference when building **guided Telegram bots that collect user input step by step**. The business domain can change, but the experience should stay consistent: private-chat only, clear progress, simple messages, predictable buttons, safe navigation, strict-but-friendly validation, a review screen, and explicit confirmation before anything is saved.

The goal is **not** to copy the daily-report business logic. The goal is to reuse the interaction patterns so every new bot feels familiar.

How to use this document:

- Read it before designing a new bot's flow.
- Follow the **Generic Implementation Checklist** while building.
- Treat **What To Reuse** as the standard and **What Not To Copy Blindly** as the domain-specific parts to replace.

---

## Core UX Principles

1. **One step at a time.** Each screen asks for one clear action. Never dump multiple questions into one message.

2. **Always show progress.** Every main step starts with a progress label so the user knows where they are:
   `Langkah 3/6 · Sumber Penjualan`

3. **Buttons for known choices.** If the user picks from a fixed list, give them buttons. Don't make people type a value they could tap.

4. **Text only for open-ended values.** Free text is for notes, names, quantities, codes/SKUs, comments — things that can't be a button.

5. **Short, action-focused messages.** Tell the user what to do *now*, not the whole process.

6. **Predictable navigation.** Continue, Previous, Cancel, Skip, Start, and Start Over always use the same labels and behave the same way.

7. **Review before you save.** Show a full summary and require explicit confirmation before writing final data.

8. **Never overwrite silently.** Duplicate or risky submissions must be confirmed, then saved as a correction / new version — not written over the original.

9. **Editable copy, live.** All wording lives in a template store, re-read on (almost) every send, so admins can change copy without a redeploy.

10. **Private chat only.** The bot works in 1:1 DMs. Reject group/channel use with a polite message.

11. **Separate UX style from business logic.** Different bots collect different data but reuse the same flow shape, keyboard behavior, validation style, and recovery behavior.

---

## Standard Conversation Flow

Use this general pattern. The exact steps and their count change per domain; the *shape* does not.

0. **Guard the channel.** On every incoming update, confirm it's a private chat. If not, reply with a "private chat only" message and stop.

1. **Start.**
   - `/start`, **or** the user tapping/typing the `Mulai` (Start) button, begins or fully resets the flow.
   - The Start action is recognized **at any point**, so the user can always escape to a clean beginning.
   - Reset the session, then show the first step with its instruction and keyboard.

2. **Identify or initialize context.**
   - Examples: choose store, select account, verify identity, choose project/customer/date.
   - Use a **reply keyboard** for Telegram-native input (share location, share contact).
   - Use an **inline keyboard** for picking from known options.
   - If identity matters, verify it here (PIN, OTP, phone, account binding — whatever fits).

3. **Collect data step by step.**
   - Each step updates the **draft** in the session (kept separate from final saved data).
   - Each main step shows progress.
   - Ask one question, or one tight logical group, at a time.

4. **Use sub-flows for repeated data.**
   - When the user selects multiple items, collect each item's details one by one.
   - Show contextual sub-progress: `Sumber 2/3 · Shopee`.

5. **Section review (only for heavy sections).**
   - For a section with several inputs, show a mini-summary with Continue / Edit / Cancel before moving on.
   - Lighter sections can skip this and surface in the final review instead. Don't add a review screen to every section.

6. **Final review.**
   - Show all collected data in a readable summary, with empty values rendered as `-`.
   - Offer Submit, Start Over, Cancel.

7. **Handle duplicates / risky submissions.**
   - If a submission for the same key already exists, route to an explicit confirmation.
   - On confirm, save as a **correction / new version**, never an overwrite.

8. **Done.**
   - Send a clear success message.
   - Clear the session.
   - Show a `Mulai` button so the user can start again.
   - Notify admin/downstream if the product needs it.

**Happy-path example (this repo's shape, generalized):**
`START → AWAIT CONTEXT INPUT → (CONFIRM | CHOOSE | MANUAL) → VERIFY IDENTITY → MULTI-SELECT + PER-ITEM INPUT → SECTION REVIEW → SECOND MULTI-SELECT → OPTIONAL NOTE → FINAL REVIEW → (CONFIRM DUPLICATE?) → DONE`

---

## Message Style

Tone: clear, calm, helpful, plain. No jargon (`callback`, `state`, `JSON`, `database` never appear in user text).

Recommended structure for a step message:

```
Langkah X/Y · Nama Tahap

Short instruction.

Current selection / current input status (if relevant).

What to do next.
```

Example:

```
Langkah 3/6 · Sumber Penjualan

Pilih satu atau lebih sumber penjualan.

Belum ada sumber penjualan yang dipilih.

Pilih sumber, atau tekan Tidak Ada Penjualan.
```

Formatting rules:

- Short paragraphs, blank lines between sections.
- Show selected items with a checkmark prefix. **The prefix itself is a template value** (e.g. `SELECTED_PREFIX`), so it can be changed or localized — don't hardcode the glyph in logic:

  ```
  Dipilih:
  ✓ Outlet
  ✓ Shopee
  ```

- Use `-` for intentionally empty values.
- Use locale-appropriate number formatting (e.g. `1.000.000`) via a format template, not inline string code.
- Telegram HTML is allowed but keep it simple, and make sure rendered output never leaks raw tags.
- Keep explanations out of the bot; the bot guides, it doesn't document.

Progress labels:

- Main step: `Langkah {{current}}/{{total}} · {{phase}}`
- Sub-step (item loops): `{{label}} {{current}}/{{total}} · {{title}}`

```
Sumber 2/3 · Shopee
Kendala 1/2 · Size Habis
```

Keep `{{total}}` stable for the duration of a flow so the count doesn't jump around.

---

## Button and Keyboard Rules

### Use a Reply Keyboard when

The action is Telegram-native input or simple navigation that sits alongside typed input.

Good cases:
- Share location, share phone/contact.
- Navigation during a text-input step (`Sebelumnya`, `Batal`).
- Continue/Edit/Cancel on a text-driven summary.
- A single "start again" action after cancel/finish.

Examples:
```
[Bagikan Lokasi]
[Pilih Manual]
```
```
[Sebelumnya] [Batal]
```
```
[Lanjutkan] [Ubah]
[Batal]
```

Reply-keyboard rules:
- Keep it small; never use a reply keyboard for a long list.
- Set `resize_keyboard=true`.
- Set `one_time_keyboard=true` when it shouldn't linger.
- For a single expected action (Start, "None"), set `input_field_placeholder` to that label so the one thing to do is obvious.
- When you move the user to a state that should have **no** reply keyboard, send `ReplyKeyboardRemove()` (e.g. on session expiry) so a stale keyboard doesn't hang around.

### Use an Inline Keyboard when

The action belongs to a specific bot message — selections, confirmations, edits, submit.

Good cases:
- Confirm a proposed item; choose from a list.
- Multi-select toggles.
- Edit a specific section.
- Submit / Start Over / Cancel on final review.
- Duplicate confirmation.

Examples:
```
[Ya] [Pilih yang lain]
```
```
[Outlet] [Shopee]
[Tokopedia] [Website]
[Tidak Ada Penjualan]
```
```
[Submit] [Mulai Ulang]
[Batal]
```

Inline-keyboard rules:
- **Always answer the callback query immediately** (even with an empty answer) so the user's tap spinner clears.
- Keep `callback_data` stable and namespaced, e.g. `sales_source:toggle:{id}`, `summary:submit`.
- When you advance away from a step that showed inline buttons, **remove that inline keyboard** (edit the message's markup to empty) so the old buttons can't be tapped again. Swallow the harmless "message is not modified" error if it occurs.
- Use the checkmark prefix on selected items.

### Single-choice buttons
- Tapping selects immediately, then the bot advances (or asks for confirmation if the choice is risky/ambiguous).

### Multi-select buttons
- Tapping toggles on/off; selected items show the prefix.
- The message updates with a live "Dipilih:" summary.
- The "None" option (`Tidak Ada` / `Tidak Ada Penjualan`) shows **only when nothing is selected**.
- The Continue button appears **only after at least one item is selected**, and should name the next item when possible: `Lanjut input Outlet`.

### Text input
Use when the answer is numeric, open-ended, a code/SKU/name/note, or the list is too large for buttons. Pair text steps with navigation:
- If the step is mainly typed input, prefer a **reply keyboard** for nav (`Sebelumnya`, `Batal`) so the text field stays free.
- An **inline** nav row (`Sebelumnya`, `Lanjutkan`, `Lewati`) is acceptable when the step is mostly button-driven with optional typing. Pick one per step and be consistent within a sub-flow.

---

## Navigation Rules

### Start
`/start` **and** the Start button text both start/restart the flow, recognized at any point.
- Delete/reset the session, persist the first step, show the first-step keyboard.

### Continue
Label `Lanjutkan`, or a specific `Lanjut input {{item}}`.
- Appears only when the current step has enough valid data.
- Moves forward; in multi-select flows it begins the per-item detail loop.

### Previous (`Sebelumnya`)
- Returns to the previous input in the same sub-flow without erasing valid data.
- In a detail loop, steps back one selected item.
- From the **first** detail item, returns to the picker with selections preserved.

### Cancel (`Batal`)
- Ends and clears the session.
- Sends a short cancellation message.
- Shows a `Mulai` button to restart.

### Skip (`Lewati`)
- Only on truly optional fields.
- Saves the field as blank / `-`.
- Never shown on required steps.

### Start Over (`Mulai Ulang`)
- On review screens. Makes clear current input will be discarded, resets the session, returns to step one.

---

## Input and Validation Rules

Strict enough to protect data quality, friendly enough to recover from.

### General
- Trim whitespace; normalize acceptable formats; store the **normalized** value in the draft.
- Preserve the user's text for open-ended fields.
- On invalid input, **reprompt the same step** — do not advance, do not save.

### Numeric input
- Accept lenient local formatting: strip spaces and thousand separators (`.` `,`), then require digits only.
- Reject anything still non-numeric after normalization, with a short example.

```
Angka belum valid.

Ketik angka saja, contoh:
100000
```

### Optional text
- Allow `-` as an explicit "nothing here", and tell the user:

```
Ketik catatan tambahan, atau ketik - jika tidak ada.
```

### Unknown text in a step
- Stay on the step, re-send the prompt + keyboard, and do not save the stray text (unless the step explicitly accepts free text).

### Stale / invalid inline tap
- Never crash. Treat it like unknown input: answer the callback, then show a safe reprompt / the latest valid prompt. (Removing keyboards on step exit prevents most of these.)

---

## Multi-Step and Multi-Select Rules

### Picker screen contains
1. Progress label
2. Instruction
3. Selected summary
4. Option buttons (from config/DB, active only, in configured sort order)
5. "None" — only when empty
6. Dynamic Continue — only when something is selected

Empty state:
```
Langkah 4/6 · Kendala

Pilih satu atau lebih kendala.

Belum ada yang dipilih.

Pilih kendala, atau tekan Tidak Ada.
```

After selection:
```
Langkah 4/6 · Kendala

Pilih satu atau lebih kendala.

Dipilih:
✓ Size Habis
✓ Warna Habis
```
Buttons:
```
[✓ Size Habis]
[✓ Warna Habis]
[Stok Kosong]
[Lanjut input Size Habis]
```

### Selected-data rules
- Store selected IDs in order; snapshot the **labels** at selection time (so later display/saving doesn't depend on config still existing).
- Order items by configured sort order, not tap order (unless the product needs tap order).
- Remove an option → drop its detail data. Keep an option → keep its detail data. Add a new option → collect details only for the new one.

### Detail loop
Ask one selected item at a time:
```
Kendala 1/3 · Size Habis

SKU apa saja yang terdampak?

Belum ada SKU yang diinput.

Ketik SKU satu per satu, atau beberapa SKU dipisahkan koma.
```
Behavior:
- Save the current item's input.
- Continue → next selected item.
- Skip → save `-` (optional detail only).
- Previous → back one item, preserving input; from the first item, back to the picker.
- After the last item, format the collected details and move to the next main step.

### Multi-select without details
- Continue saves the selected IDs/labels and moves on; selections show up in the final review.

---

## Review and Confirmation Rules

### Section review (selective)
Use for a section with several inputs (e.g. per-source sales). Skip it for light sections.
```
Langkah 3/6 · Review Penjualan

Berikut ringkasan penjualan:

Outlet
Traffic: 10
GMV: 1.000.000
Order: 5
Pieces: 8

Total GMV: 1.000.000
Total Order: 5
Total Pieces: 8

Lanjutkan?
```
Buttons:
```
[Lanjutkan] [Ubah]
[Batal]
```
- `Lanjutkan` → next main step.
- `Ubah` → edit menu (edit one item's fields, or add/remove selected options, then return to review without losing valid data).
- `Batal` → cancel session.

Never force a full restart for a small fix.

### Final review
Show everything before submit:
- Identity/context, all sections, optional notes, empty values as `-`, any status the user should see.
```
[Submit] [Mulai Ulang]
[Batal]
```

### Final submit
- Re-validate required data before saving; block incomplete submissions.
- Handle duplicates explicitly (see below).
- Generate a safe unique record ID (e.g. timestamped + random suffix, regenerated on collision).
- On success: success message → clear session → notify admin/downstream if needed.

---

## Error and Recovery Rules

Keep recovery messages few and consistent. This repo uses essentially **two** templates plus the private-chat guard — resist inventing more.

### Private chat only
If the chat isn't a private DM, reply and stop:
```
Bot ini hanya bisa digunakan lewat chat pribadi.
```

### Unknown / unexpected input (the catch-all)
One reusable handler covers: unexpected text in a step, input that doesn't match the current step, a missing session, and stale/unrecognized inline taps. Stay safe, don't advance, show the same friendly nudge and re-send the current prompt:
```
Saya belum mengerti input ini.

Silakan gunakan tombol yang tersedia, atau ikuti instruksi di bawah.
```
Rules: don't change step, don't save invalid input, don't silently restart.

> Note: you do **not** need a separate "invalid state" message. Fold "no session / bad step / bad callback" into this one catch-all and offer a clean reprompt or restart.

### Expired session
When the session has passed its TTL, delete it, clear any reply keyboard, and offer a clean restart:
```
Sesi sudah berakhir.

Tekan Mulai untuk memulai lagi.
```
Buttons: `[Mulai]` (and send `ReplyKeyboardRemove()` alongside).
Rules: clear expired draft, never continue old state, never submit partial data.

### Duplicate submission
When the same logical key already has a record:
```
Data untuk periode ini sudah pernah dikirim.

Apakah ingin mengirim sebagai koreksi?
```
Buttons: `[Ya, kirim koreksi] [Batal]`
Rules: never overwrite; on confirm save as correction/new version; on cancel, end or return per product rules.

### Cancellation
```
Input dibatalkan.

Tekan Mulai jika ingin mulai lagi.
```
Buttons: `[Mulai]`
Rules: clear the session, submit nothing, make restart easy.

---

## Text and Template Rules

All user-facing copy is template-driven and stored as data, not hardcoded.

Store as editable templates: prompts, button labels, progress labels, section titles, selected-summary labels, error/validation messages, review summaries, admin notifications, status labels, and format strings (number, distance, store/area labels).

Mechanics that make this work:
- **Stable keys.** Code references keys; never rename a key without updating every reference.
- **Live re-fetch.** Re-read templates on (nearly) every send so admin edits take effect immediately, no redeploy.
- **Placeholders** for dynamic values: `{{progress}}`, `{{store_label}}`, `{{current}}`, `{{total}}`, `{{source}}`, `{{issue}}`, `{{sales_breakdown}}`.
- **Three render modes:**
  - *escape* — default; HTML-escape all token values (anything user-derived).
  - *plain* — no escaping; for internal, non-HTML strings (progress labels, button text).
  - *trusted* — escape everything **except** a whitelisted set of internally generated HTML tokens (e.g. a pre-formatted `sales_breakdown`). Never put user input in a trusted token.
- **Config lists live in their own tables**, not inside message templates: the selectable options (sales sources, stock issues, etc.) each have `label`, `sort_order`, `status`/active flag, and any per-option flags. Edit option labels there, edit wording in the template store.
- **Category metadata**, auto-derived from the key prefix, for future admin screens.

Recommended key groups (prefix → purpose), matching this repo's convention:
- `BUTTON_*` — button labels
- `PROGRESS_*`, `CONTEXTUAL_STEP_*`, `NEXT_PHASE_*` — progress + transition labels
- `ASK_*` — step prompts
- `ADMIN_*` — admin notifications
- `STORE_*`, `AREA_*`, `DISTANCE_*`, `LOCATION_STATUS_*` — display/format strings (replace with your domain's display groups)
- Domain groups such as `SALES_*`, `STOCK_ISSUE_*`, `ORDER_*`, `CUSTOMER_*`
- Recovery: a single unknown/catch-all key, an expired-session key, a private-chat key, a cancelled key, a duplicate key

Seeding: load templates and option lists from versioned source files (e.g. CSV) via an idempotent seed. Re-seeding restores source values and discards live DB edits — make that trade-off explicit to admins. Never commit secrets, PINs, or personal data into seed inputs or handoff bundles.

---

## Generic Implementation Checklist

### Flow and state
- [ ] Define a clear state machine (one enum of steps, explicit transitions).
- [ ] Keep step transitions in the domain layer, not in the orchestrator.
- [ ] Store current step in the session.
- [ ] Keep the draft separate from final saved data.
- [ ] Add session expiry (TTL) and check it on every load.
- [ ] `/start` **and** the Start button both reset/initialize, recognized anytime.
- [ ] `/cancel` and the Cancel button both clear the session.
- [ ] Guard: handle private chats only.

### Progress
- [ ] Define main phases; show a progress label atop every main step.
- [ ] Show contextual sub-progress in item loops.
- [ ] Keep the total count stable through the flow.

### Messages
- [ ] One clear action per message; short paragraphs.
- [ ] Show current selection/input when useful.
- [ ] `-` for empty optional values; locale number format via template.

### Keyboards
- [ ] Reply keyboard for Telegram-native input and text-step navigation.
- [ ] Inline keyboard for selections and message-specific actions.
- [ ] Always answer callback queries.
- [ ] Remove the inline keyboard when leaving a step (anti-stale-tap).
- [ ] `ReplyKeyboardRemove` when moving to a no-keyboard state.
- [ ] `input_field_placeholder` for single-action reply keyboards.
- [ ] Hide unavailable buttons; dynamic Continue labels; checkmark prefix (from a template) for selections.

### Validation
- [ ] Normalize input; reject invalid without advancing; reprompt with an example.
- [ ] Preserve valid earlier input; don't accept stray text in button-only steps.

### Multi-select
- [ ] Load options from config/DB; active only; configured sort order.
- [ ] Toggle with inline buttons; show selected summary.
- [ ] Hide "None" after any selection; show Continue only after selection.
- [ ] Snapshot labels; preserve details for kept options; drop details for removed; collect only for newly added.

### Review
- [ ] Section review for heavy sections only; final review before submit.
- [ ] Edit actions that don't force a restart.
- [ ] Re-validate before saving; generate a unique record ID with collision retry.

### Error recovery
- [ ] One catch-all unknown handler (text/step/callback).
- [ ] Expired-session handler (clear + restart + remove keyboard).
- [ ] Duplicate-submission confirmation (correction, not overwrite).
- [ ] Private-chat guard. Always offer a clear recovery path.

### Templates
- [ ] All user-facing text in templates with stable keys + placeholders.
- [ ] Re-fetch templates on send; option labels in their own tables.
- [ ] Escape user values; use a trusted mode only for internal HTML.
- [ ] Tests for important rendered text and keyboard layouts.

---

## What To Reuse From This Repo

Reuse these generically:

1. **Guided state-machine flow** — one current step, one draft object, explicit transitions kept in the domain layer.
2. **Progress label per main step** — `Langkah X/Y · Phase`, with `Item X/Y · Name` for loops.
3. **Thin handlers, one orchestrator** — handlers delegate to a single flow controller that wires updates → domain decisions → repositories → replies.
4. **Pure, testable domain** — business rules and step transitions with no Telegram or DB imports, unit-tested directly.
5. **Repository layer for storage** — SQL/DB access isolated from UX logic.
6. **Template-driven copy, re-fetched live** — editable wording by stable key; three render modes (escape / plain / trusted).
7. **Configurable option lists** — selectable buttons come from tables with active flag + sort order + snapshotted labels.
8. **Inline multi-select with live "Dipilih:" summary** and a dynamic, item-named Continue button.
9. **Reply-keyboard navigation during text input** (`Sebelumnya`, `Batal`).
10. **Selective section review + edit-without-restart**, then a full final review before submit.
11. **Correction instead of overwrite** for duplicates, behind an explicit confirm.
12. **Session TTL + clean restart** on expiry/cancel; Start recognized at any time.
13. **Private-chat guard** on every update.
14. **Always-answer callbacks + remove inline keyboards on step exit** to kill stale-tap bugs.
15. **Unique record IDs with collision retry**, and a single catch-all unknown handler.

---

## What Not To Copy Blindly

Replace these with the new bot's domain unless they genuinely apply:

1. **SPG daily-report logic** — store reporting, sales-source reporting, stock-issue reporting, SKU detail, the daily admin report.
2. **Store GPS matching** — only if the new bot needs location-based selection.
3. **PIN verification** — swap for whatever identity model fits (phone share, OTP, login link, account binding).
4. **Sales-specific fields** — traffic, GMV, order, pieces.
5. **Stock-specific labels** — Size Habis, Warna Habis, Stok Kosong.
6. **The daily duplicate key** — the correction pattern is reusable; the *key* (store + date) is domain-specific.
7. **Bahasa Indonesia copy** — the style is reusable; match the target bot's language.
8. **Exact step count** — six steps is not a rule; size progress to the new flow.
9. **Admin notification format** — reuse the idea of a formatted notification, not the content.
10. **Report ID scheme** — keep "unique + collision-safe", but the `RPT-YYYYMMDD-...` shape is domain flavor.
11. **Table names** — keep "configurable templates + option lists", name tables for the new domain.

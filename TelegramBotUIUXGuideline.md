# Telegram Bot UI/UX Guideline

## Purpose

This guideline defines the standard Telegram bot interaction style for future projects.

Use this as a reference when building guided Telegram bots that collect user input step by step. The business domain can change, but the user experience should stay consistent: clear progress, simple messages, predictable buttons, safe navigation, validation, review, and confirmation before final submission.

The goal is not to copy the exact daily report flow. The goal is to reuse the interaction patterns.

## Core UX Principles

1. **Guide the user one step at a time**
   Do not show too many questions at once. Each screen should ask for one clear action.

2. **Always show progress**
   Users should know where they are in the process using a simple progress label such as:

   `Langkah 3/6 · Data Penjualan`

3. **Use buttons when the choices are known**
   If the user should pick from a fixed list, use buttons. Avoid asking users to type values that can be selected.

4. **Allow text input when the value is open-ended**
   Use free text only for values such as notes, names, quantities, SKU lists, comments, or other manual input.

5. **Keep messages short and useful**
   Each message should explain what the user needs to do now, not the whole process.

6. **Make navigation predictable**
   Use the same labels and behavior for Continue, Previous, Cancel, Skip, Start, and Start Over.

7. **Always review before final submission**
   Before saving final data, show a clear summary and ask for confirmation.

8. **Keep UI text editable**
   Prompts, button labels, progress labels, summaries, and error messages should be stored as templates, not hardcoded.

9. **Separate UX style from business logic**
   Future bots may collect different data, but should reuse the same conversation structure, keyboard behavior, validation style, and recovery behavior.

## Standard Conversation Flow

Use this general flow pattern:

1. **Start**

   * User sends `/start` or taps a `Mulai` button.
   * Bot creates or resets the session.
   * Bot shows the first step with a clear instruction and relevant buttons.

2. **Identify or initialize context**

   * Examples: choose store, select account, verify identity, choose project, choose customer, choose date.
   * Use reply keyboard if Telegram-native input is needed, such as sharing location or contact.
   * Use inline keyboard if selecting from known options.

3. **Collect data step by step**

   * Each step updates the session draft.
   * Each screen shows the current progress.
   * Ask only one question or one logical group at a time.

4. **Use sub-flows for repeated data**

   * If the user selects multiple items, collect details for each item one by one.
   * Show contextual sub-progress such as:

   `Item 2/4 · Tokopedia`

5. **Review section summary**

   * For larger flows, show mini-review screens before moving to the next major section.
   * Allow the user to continue, edit, or cancel.

6. **Review full summary**

   * Show all collected data in a readable format.
   * Provide buttons for Submit, Start Over, or Cancel.

7. **Handle duplicates or risky submissions**

   * If the same user/context/date already has a submission, do not silently overwrite.
   * Ask for explicit confirmation.
   * Save as a correction, new version, or duplicate record depending on the product rules.

8. **Done**

   * Confirm successful submission.
   * Clear or close the active session.
   * Show `Mulai` if the user can start again.

## Message Style

Use a clear, calm, helpful tone.

Recommended message structure:

```md
Langkah X/Y · Nama Tahap

Short instruction.

Current selected/input status, if relevant.

What the user should do next.
```

Example:

```md
Langkah 3/6 · Sumber Penjualan

Pilih satu atau lebih sumber penjualan.

Belum ada sumber penjualan yang dipilih.

Pilih sumber, atau tekan Tidak Ada Penjualan.
```

Formatting rules:

* Use short paragraphs.
* Use blank lines between sections.
* Use checkmarks for selected items:

```md
Dipilih:
✓ Outlet
✓ Shopee
```

* Use `-` for intentionally empty values.
* Use consistent number formatting for the locale.
* Avoid long explanations inside the bot.
* Avoid technical terms such as `callback`, `state`, `JSON`, or `database`.
* Telegram HTML is allowed, but keep it simple.
* If using HTML tags, make sure the final rendered message is clean and does not expose raw tags accidentally.

Progress rules:

* Main steps should use:

```md
Langkah {{current}}/{{total}} · {{phase}}
```

* Substeps should use:

```md
{{label}} {{current}}/{{total}} · {{title}}
```

Example:

```md
Sumber 2/3 · Shopee
Kendala 1/2 · Size Habis
```

## Button and Keyboard Rules

### Use Reply Keyboard When

Use reply keyboard for actions that feel like normal user input or Telegram-native input.

Good use cases:

* Share location
* Share phone/contact
* Continue after text input
* Previous / Cancel during manual input
* Start again after cancellation or completion
* Simple confirmation during a text-input phase

Examples:

```md
[Bagikan Lokasi]
[Pilih Manual]
```

```md
[Sebelumnya] [Batal]
```

```md
[Lanjutkan] [Ubah]
[Batal]
```

Reply keyboard rules:

* Keep it small.
* Use `resize_keyboard`.
* Use `one_time_keyboard` when the keyboard should not stay forever.
* Do not show irrelevant buttons.
* Do not use reply keyboard for large lists.

### Use Inline Keyboard When

Use inline keyboard for selecting from known options or actions tied to a specific bot message.

Good use cases:

* Confirm selected item
* Choose from a list
* Multi-select options
* Edit a specific section
* Submit / restart / cancel on final review
* Duplicate confirmation

Examples:

```md
[Ya] [Pilih yang lain]
```

```md
[Outlet] [Shopee]
[Tokopedia] [Website]
[Tidak Ada Penjualan]
```

```md
[Submit] [Mulai Ulang]
[Batal]
```

Inline keyboard rules:

* Use inline buttons when the action should update the current message.
* Use checkmark prefixes for selected items.
* Keep callback actions stable and predictable.
* Do not require the user to type when a button is safer.

### Single-Choice Buttons

Use single-choice buttons when only one option can be selected.

Behavior:

* Tapping an option saves the value immediately.
* Bot moves to the next step or asks for confirmation.
* If the choice is risky or ambiguous, ask for confirmation first.

### Multi-Select Buttons

Use multi-select buttons when the user can select more than one option.

Behavior:

* Tapping an option toggles it on/off.
* Selected options show a checkmark.
* The message updates with a selected summary.
* `Tidak Ada` or equivalent appears only when nothing is selected.
* Continue button appears only after at least one option is selected.
* Continue button should be specific when possible:

```md
Lanjut input Outlet
Lanjut input Size Habis
```

### Text Input

Use text input when:

* The answer is numeric.
* The answer is open-ended.
* The user needs to enter codes, names, notes, SKUs, or quantities.
* The list is too large for buttons.

Text input screens should usually include reply keyboard navigation:

```md
[Sebelumnya] [Batal]
```

## Navigation Rules

### Start

`/start` should always start or restart the guided flow.

Behavior:

* Create a new session or reset the old one.
* Show the first step.
* Show the correct first-step keyboard.

### Continue

Use `Lanjutkan` or a more specific label such as `Lanjut input {{item}}`.

Behavior:

* Continue should only appear when the current step has enough valid data.
* Continue should move forward to the next logical step.
* For multi-select flows, Continue starts the detail-input loop.

### Previous

Use `Sebelumnya`.

Behavior:

* Previous should return to the previous input in the same sub-flow.
* In a detail loop, Previous moves to the previous selected item.
* From the first detail item, Previous returns to the picker with selected values preserved.
* Do not erase valid data unless the user explicitly removes the option.

### Cancel

Use `Batal`.

Behavior:

* Cancel ends the current session.
* Clear the draft session.
* Show a short cancellation message.
* Show a `Mulai` button so the user can restart easily.

### Skip

Use `Lewati` only when the field is truly optional.

Behavior:

* Skip saves the field as blank or `-`.
* Skip should not appear for required steps.
* Skip should not be used when the product needs a valid choice to continue.

### Start Over

Use `Mulai Ulang` or `Mulai dari awal` on review screens.

Behavior:

* Ask or clearly indicate that current input will be discarded.
* Reset the session.
* Return to the first step.

## Input and Validation Rules

Validation should be strict enough to protect data quality, but friendly enough that users can recover easily.

### General Rules

* Trim whitespace.
* Normalize acceptable formats.
* Accept common local input formats when possible.
* Preserve user text when the field is open-ended.
* Store normalized values in the draft.
* Reprompt without moving forward when input is invalid.

### Numeric Input

For numeric fields:

* Accept thousand separators when reasonable.
* Convert input to a clean integer or decimal.
* Reject input that still contains invalid characters after normalization.
* Show a short error and repeat the same question.

Example:

```md
Angka belum valid.

Ketik angka saja, contoh:
100000
```

### Optional Text

For optional text fields:

* Allow `-` as an intentional empty value.
* Normalize empty optional values to `-` or `null`, depending on storage rules.
* Make the instruction clear:

```md
Ketik catatan tambahan, atau ketik - jika tidak ada.
```

### Unknown Input

When the user sends unexpected text, do not advance the flow.

Behavior:

* Stay in the current step.
* Explain what input is expected.
* Re-send the current prompt and keyboard.
* Do not save unknown text as valid data unless the step explicitly allows free text.

### Invalid Button Callback

If the user taps an expired or invalid inline button:

* Do not crash.
* Show a simple message asking the user to restart or continue from the latest state.
* Prefer reloading the current session and showing the latest valid prompt.

## Multi-Step and Multi-Select Rules

Use this pattern for configurable multi-select flows.

### Picker Screen

The picker screen should show:

1. Progress label
2. Instruction
3. Selected summary
4. Option buttons
5. `Tidak Ada` only when empty
6. Dynamic Continue button only when selected

Example:

```md
Langkah 4/6 · Kendala

Pilih satu atau lebih kendala.

Belum ada yang dipilih.

Pilih kendala, atau tekan Tidak Ada.
```

After selection:

```md
Langkah 4/6 · Kendala

Pilih satu atau lebih kendala.

Dipilih:
✓ Size Habis
✓ Warna Habis
```

Buttons:

```md
[✓ Size Habis]
[✓ Warna Habis]
[Stok Kosong]
[Lanjut input Size Habis]
```

### Selected Data Rules

* Store selected item IDs in order.
* Store selected item labels as snapshots.
* Sort selected items by configured sort order, not by tap order, unless the product specifically needs tap order.
* If the user removes an option, remove its related detail data.
* If the user keeps an option, preserve its related detail data.
* If the user adds a new option, collect details only for the new option.

### Detail Loop

When selected items need details, ask one selected item at a time.

Example:

```md
Kendala 1/3 · Size Habis

SKU apa saja yang terdampak?

Belum ada SKU yang diinput.

Ketik SKU satu per satu, atau beberapa SKU dipisahkan koma.
```

Buttons:

```md
[Sebelumnya] [Lanjutkan] [Lewati]
```

Detail loop behavior:

* Save input for the current item.
* Continue moves to the next selected item.
* Skip saves `-` for optional detail.
* Previous moves back while preserving existing input.
* After the final selected item, format the collected details and move to the next main step.

### Multi-Select Without Details

If selected items do not need details:

* Continue saves the selected labels or IDs.
* Move directly to the next step.
* Show the selected summary in the later review screen.

## Review and Confirmation Rules

### Section Review

Use section review when a section contains multiple inputs.

Example:

```md
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

```md
[Lanjutkan] [Ubah]
[Batal]
```

Behavior:

* `Lanjutkan` moves to the next main step.
* `Ubah` opens an edit menu.
* `Batal` cancels the session.

### Edit Behavior

Edit menu should allow:

* Edit a specific item or section.
* Add/remove selected options when the section uses multi-select.
* Return to review without losing previous valid data.

Do not force the user to restart the whole flow for a small correction.

### Final Review

Before final submit, show a complete summary.

The summary should include:

* Main identity/context
* All collected sections
* Optional notes
* Empty values shown clearly as `-`
* Any status that matters to the user

Buttons:

```md
[Submit] [Mulai Ulang]
[Batal]
```

### Final Submit

Behavior:

* Validate required data again before saving.
* Prevent incomplete submissions.
* Handle duplicate/risky submissions explicitly.
* After successful save, send a success message.
* Clear the active session.
* Notify admin or downstream systems if needed.

## Error and Recovery Rules

### Unknown Input

If the user sends something the current step does not accept:

```md
Saya belum mengerti input ini.

Silakan gunakan tombol yang tersedia, atau ikuti instruksi di bawah.
```

Then re-send the current prompt.

Rules:

* Do not change step.
* Do not save invalid input.
* Do not silently restart.

### Expired Session

When the session has expired:

```md
Sesi sudah berakhir.

Tekan Mulai untuk memulai lagi.
```

Buttons:

```md
[Mulai]
```

Rules:

* Clear expired draft data.
* Do not continue with old state.
* Do not submit partial data.

### Invalid State

If session data is missing or inconsistent:

```md
Sesi tidak bisa dilanjutkan.

Tekan Mulai untuk memulai ulang.
```

Rules:

* Fail safely.
* Avoid saving incomplete data.
* Offer restart.

### Duplicate Submission

If the same logical submission already exists:

```md
Data untuk periode ini sudah pernah dikirim.

Apakah ingin mengirim sebagai koreksi?
```

Buttons:

```md
[Ya, kirim koreksi] [Batal]
```

Rules:

* Do not overwrite silently.
* If confirmed, save as correction/new version.
* If cancelled, end or return to review depending on product rules.

### Cancellation

When cancelled:

```md
Input dibatalkan.

Tekan Mulai jika ingin mulai lagi.
```

Buttons:

```md
[Mulai]
```

Rules:

* Clear the active session.
* Do not submit anything.
* Make restart easy.

## Text and Template Rules

All user-facing copy should be template-driven.

Store these as editable templates:

* Prompt messages
* Button labels
* Progress labels
* Section titles
* Selected summary labels
* Error messages
* Validation messages
* Review summaries
* Admin notifications
* Status labels
* Format strings

Template rules:

* Use stable keys.
* Do not rename keys unless code is updated.
* Use placeholders for dynamic values:

```md
{{progress}}
{{store_label}}
{{current}}
{{total}}
{{source}}
{{issue}}
{{sales_breakdown}}
```

* Escape user-provided values before rendering HTML.
* Only allow trusted internally generated HTML where needed.
* Keep configurable option labels in their own tables or config lists, not inside message templates.
* Support category/description metadata for easier admin maintenance.
* Do not hardcode final user-facing text in flow logic.

Recommended template groups:

* `PROGRESS_*`
* `BUTTON_*`
* `START_*`
* `VALIDATION_*`
* `ERROR_*`
* `REVIEW_*`
* `SUMMARY_*`
* Domain-specific groups such as `SALES_*`, `STOCK_*`, `ORDER_*`, `CUSTOMER_*`

## Generic Implementation Checklist

Use this checklist when building a new Telegram bot with this style.

### Flow and State

* [ ] Define a clear state machine.
* [ ] Store current step in session.
* [ ] Store draft input separately from final submitted data.
* [ ] Add session expiry.
* [ ] Make `/start` reset or initialize the session.
* [ ] Make `/cancel` clear the session.
* [ ] Keep step transitions predictable.

### Progress

* [ ] Define main progress phases.
* [ ] Show progress at the top of every main step.
* [ ] Show contextual sub-progress for loops.
* [ ] Keep total step count stable during the flow.

### Messages

* [ ] Each message asks for one clear action.
* [ ] Use short paragraphs.
* [ ] Show selected/current input when useful.
* [ ] Use `-` for empty optional values.
* [ ] Use consistent formatting and local number format.

### Keyboards

* [ ] Use reply keyboard for Telegram-native input and simple navigation.
* [ ] Use inline keyboard for selections and message-specific actions.
* [ ] Keep buttons short.
* [ ] Hide unavailable buttons.
* [ ] Use dynamic Continue labels when helpful.
* [ ] Use checkmarks for selected options.

### Validation

* [ ] Normalize user input.
* [ ] Reject invalid input without advancing.
* [ ] Reprompt with a helpful example.
* [ ] Preserve valid previous input.
* [ ] Do not accept stray text in button-only steps.

### Multi-Select

* [ ] Load options from config or database.
* [ ] Show only active options.
* [ ] Sort options by configured order.
* [ ] Toggle selection with inline buttons.
* [ ] Show selected summary.
* [ ] Hide `None` option after any selection.
* [ ] Preserve detail data for still-selected options.
* [ ] Remove detail data for unselected options.

### Review

* [ ] Add section review for complex sections.
* [ ] Add final review before submit.
* [ ] Provide edit actions.
* [ ] Provide cancel and start-over actions.
* [ ] Revalidate before saving.

### Error Recovery

* [ ] Handle expired sessions.
* [ ] Handle invalid state.
* [ ] Handle duplicate submissions.
* [ ] Handle unknown input.
* [ ] Handle stale inline buttons.
* [ ] Always offer a clear recovery path.

### Templates

* [ ] Store user-facing text in templates.
* [ ] Store button labels in templates.
* [ ] Store configurable option labels separately.
* [ ] Use stable template keys.
* [ ] Use placeholders for dynamic values.
* [ ] Escape user-provided values.
* [ ] Add tests for important rendered text.

## What To Reuse From This Repo

Reuse these patterns generically:

1. **Guided state-machine flow**
   One current step, one draft object, one clear transition path.

2. **Progress label per step**
   Every main step has a visible `Langkah X/Y · Phase` label.

3. **Contextual substep progress**
   Repeated item loops use `Item X/Y · Item Name`.

4. **Thin handlers, centralized flow orchestration**
   Telegram handlers should delegate to one flow controller.

5. **Pure domain logic**
   Business rules and state transitions should be testable without Telegram or database.

6. **Repository layer for storage**
   Database access should stay separate from bot UX logic.

7. **Template-driven copy**
   User-facing text should come from editable template keys.

8. **Configurable option lists**
   Button options such as categories, sources, issues, or reasons should come from database/config with status and sort order.

9. **Inline multi-select with checkmarks**
   Selected options update the same message and show a live selected summary.

10. **Dynamic next button**
    Continue button can include the next item name, such as `Lanjut input {{item}}`.

11. **Reply keyboard for manual input navigation**
    Use `Sebelumnya` and `Batal` during text input loops.

12. **Review before submit**
    Show summary and confirmation before saving.

13. **Correction instead of overwrite**
    For duplicate submissions, ask confirmation and save as correction/new version.

14. **Session expiry and restart recovery**
    Expired or cancelled sessions should show a clean restart button.

15. **Unit-testable UI helpers**
    Progress, keyboard layout, text formatting, and validation should be covered by tests.

## What Not To Copy Blindly

Do not copy these unless the new bot actually needs them:

1. **SPG daily report business logic**

   * Store reporting
   * Sales source reporting
   * Stock issue reporting
   * SKU detail collection
   * Admin daily report notification

2. **Store GPS matching**

   * Only reuse if the new bot needs location-based selection.

3. **PIN verification**

   * Only reuse if the new bot needs simple identity verification.
   * Other bots may use phone sharing, login links, OTP, or account binding.

4. **Sales-specific fields**

   * Traffic
   * GMV
   * Order
   * Pieces

5. **Stock-specific labels**

   * Size Habis
   * Warna Habis
   * Stok Kosong

6. **Daily duplicate rule**

   * The correction pattern is reusable, but the duplicate key may be different.

7. **Bahasa Indonesia copy**

   * The style is reusable, but the language should match the target bot.

8. **Exact number of steps**

   * Future bots do not need 6 steps.
   * Keep progress consistent with the new flow.

9. **Admin notification format**

   * Reuse the idea of formatted notification, not the exact content.

10. **Database table names**

* Keep the pattern of configurable templates and options, but name tables according to the new domain.

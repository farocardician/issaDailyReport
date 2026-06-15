from app.bot.progress import contextual_step_progress, progress_for_step
from app.domain.session_state import Step, apply_numeric_answer
from app.templates import MessageTemplates


def _templates() -> MessageTemplates:
    return MessageTemplates(
        {
            "PROGRESS_MAIN_LABEL": "Tahap",
            "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
            "CONTEXTUAL_STEP_FORMAT": "{{label}} {{current}}/{{total}} · {{title}}",
            "PROGRESS_PHASE_STORE": "Pilih Toko",
            "PROGRESS_PHASE_PIN": "Verifikasi PIN",
            "PROGRESS_PHASE_TRAFFIC": "Traffic",
            "PROGRESS_PHASE_GMV_OFFLINE": "GMV Offline",
            "PROGRESS_PHASE_GMV_ONLINE": "GMV Online",
            "PROGRESS_PHASE_ORDER_PIECES": "Order & Pieces",
            "PROGRESS_PHASE_ISSUE_NOTE": "Kendala & Catatan",
            "PROGRESS_PHASE_REVIEW_SUBMIT": "Review & Submit",
            "STOCK_ISSUE_DETAIL_STEP_LABEL": "Masalah",
        }
    )


def test_progress_normal_flow_phases() -> None:
    templates = _templates()

    assert progress_for_step(templates, Step.AWAITING_LOCATION) == "Tahap 1/8 · Pilih Toko"
    assert progress_for_step(templates, Step.AWAITING_PIN) == "Tahap 2/8 · Verifikasi PIN"
    assert progress_for_step(templates, Step.ASK_TRAFFIC) == "Tahap 3/8 · Traffic"
    assert progress_for_step(templates, Step.ASK_GMV) == "Tahap 4/8 · GMV Offline"
    assert progress_for_step(templates, Step.ASK_ONLINE_GMV) == "Tahap 5/8 · GMV Online"
    assert progress_for_step(templates, Step.ASK_ORDER) == "Tahap 6/8 · Order & Pieces"
    assert progress_for_step(templates, Step.REVIEW_SUMMARY) == "Tahap 8/8 · Review & Submit"


def test_progress_follows_skipped_numeric_steps() -> None:
    templates = _templates()
    next_step, draft = apply_numeric_answer(Step.ASK_TRAFFIC, {}, 0)

    assert next_step == Step.ASK_ONLINE_GMV
    assert progress_for_step(templates, next_step) == "Tahap 5/8 · GMV Online"

    next_step, _ = apply_numeric_answer(next_step, draft, 0)

    assert next_step == Step.ASK_STOCK_ISSUE
    assert progress_for_step(templates, next_step) == "Tahap 7/8 · Kendala & Catatan"


def test_stock_issue_selection_progress_has_no_contextual_substep() -> None:
    templates = _templates()

    assert progress_for_step(templates, Step.ASK_STOCK_ISSUE) == "Tahap 7/8 · Kendala & Catatan"


def test_contextual_step_label_is_db_backed_and_dynamic() -> None:
    templates = _templates()

    assert contextual_step_progress(
        templates,
        "STOCK_ISSUE_DETAIL_STEP_LABEL",
        1,
        4,
        "Size Habis",
    ) == "Masalah 1/4 · Size Habis"
    assert contextual_step_progress(
        templates,
        "STOCK_ISSUE_DETAIL_STEP_LABEL",
        2,
        2,
        "Warna Habis",
    ) == "Masalah 2/2 · Warna Habis"

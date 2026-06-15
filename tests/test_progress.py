from app.bot.progress import contextual_step_progress, progress_for_step
from app.domain.session_state import Step
from app.templates import MessageTemplates


def _templates() -> MessageTemplates:
    return MessageTemplates(
        {
            "PROGRESS_MAIN_LABEL": "Tahap",
            "PROGRESS_MAIN_FORMAT": "{{label}} {{current}}/{{total}} · {{phase}}",
            "CONTEXTUAL_STEP_FORMAT": "{{label}} {{current}}/{{total}} · {{title}}",
            "PROGRESS_PHASE_STORE": "Pilih Toko",
            "PROGRESS_PHASE_PIN": "Verifikasi PIN",
            "PROGRESS_PHASE_SALES": "Sumber Penjualan",
            "PROGRESS_PHASE_ISSUE_NOTE": "Kendala & Catatan",
            "PROGRESS_PHASE_REVIEW_SUBMIT": "Review & Submit",
            "STOCK_ISSUE_DETAIL_STEP_LABEL": "Masalah",
            "SALES_SOURCE_STEP_LABEL": "Sumber",
        }
    )


def test_progress_uses_five_main_phases() -> None:
    templates = _templates()

    assert progress_for_step(templates, Step.AWAITING_LOCATION) == "Tahap 1/5 · Pilih Toko"
    assert progress_for_step(templates, Step.AWAITING_PIN) == "Tahap 2/5 · Verifikasi PIN"
    assert progress_for_step(templates, Step.ASK_SALES_SOURCES) == "Tahap 3/5 · Sumber Penjualan"
    assert progress_for_step(templates, Step.ASK_SALES_INPUT) == "Tahap 3/5 · Sumber Penjualan"
    assert progress_for_step(templates, Step.REVIEW_SALES_SUMMARY) == "Tahap 3/5 · Sumber Penjualan"
    assert progress_for_step(templates, Step.EDIT_SALES_MENU) == "Tahap 3/5 · Sumber Penjualan"
    assert progress_for_step(templates, Step.ASK_STOCK_ISSUE) == "Tahap 4/5 · Kendala & Catatan"
    assert progress_for_step(templates, Step.REVIEW_SUMMARY) == "Tahap 5/5 · Review & Submit"


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
        "SALES_SOURCE_STEP_LABEL",
        2,
        3,
        "Shopee",
    ) == "Sumber 2/3 · Shopee"

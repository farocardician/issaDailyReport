from __future__ import annotations

from dataclasses import dataclass

from app.domain.session_state import Step
from app.templates import MessageTemplates


@dataclass(frozen=True)
class ProgressSpec:
    current: int
    total: int
    phase_key: str


PROGRESS_BY_STEP: dict[Step, ProgressSpec] = {
    Step.AWAITING_LOCATION: ProgressSpec(1, 5, "PROGRESS_PHASE_STORE"),
    Step.CONFIRM_STORE: ProgressSpec(1, 5, "PROGRESS_PHASE_STORE"),
    Step.CHOOSE_STORE: ProgressSpec(1, 5, "PROGRESS_PHASE_STORE"),
    Step.MANUAL_STORE_SELECTION: ProgressSpec(1, 5, "PROGRESS_PHASE_STORE"),
    Step.AWAITING_PIN: ProgressSpec(2, 5, "PROGRESS_PHASE_PIN"),
    Step.ASK_SALES_SOURCES: ProgressSpec(3, 5, "PROGRESS_PHASE_SALES"),
    Step.ASK_SALES_INPUT: ProgressSpec(3, 5, "PROGRESS_PHASE_SALES"),
    Step.REVIEW_SALES_SUMMARY: ProgressSpec(3, 5, "PROGRESS_PHASE_SALES"),
    Step.EDIT_SALES_MENU: ProgressSpec(3, 5, "PROGRESS_PHASE_SALES"),
    Step.ASK_STOCK_ISSUE: ProgressSpec(4, 5, "PROGRESS_PHASE_ISSUE_NOTE"),
    Step.ASK_NOTE: ProgressSpec(4, 5, "PROGRESS_PHASE_ISSUE_NOTE"),
    Step.REVIEW_SUMMARY: ProgressSpec(5, 5, "PROGRESS_PHASE_REVIEW_SUBMIT"),
    Step.CONFIRM_DUPLICATE: ProgressSpec(5, 5, "PROGRESS_PHASE_REVIEW_SUBMIT"),
}


def progress_for_step(templates: MessageTemplates, step: Step) -> str:
    spec = PROGRESS_BY_STEP[step]
    return templates.render_plain(
        "PROGRESS_MAIN_FORMAT",
        label=templates.render_plain("PROGRESS_MAIN_LABEL"),
        current=spec.current,
        total=spec.total,
        phase=templates.render_plain(spec.phase_key),
    )


def contextual_step_progress(
    templates: MessageTemplates,
    label_key: str,
    current: int,
    total: int,
    title: str,
) -> str:
    return templates.render_plain(
        "CONTEXTUAL_STEP_FORMAT",
        label=templates.render_plain(label_key),
        current=current,
        total=total,
        title=title,
    )

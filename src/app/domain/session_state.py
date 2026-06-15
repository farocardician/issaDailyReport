from enum import StrEnum
from typing import Any, Mapping


class Step(StrEnum):
    START = "START"
    AWAITING_LOCATION = "AWAITING_LOCATION"
    CONFIRM_STORE = "CONFIRM_STORE"
    CHOOSE_STORE = "CHOOSE_STORE"
    MANUAL_STORE_SELECTION = "MANUAL_STORE_SELECTION"
    AWAITING_PIN = "AWAITING_PIN"
    ASK_TRAFFIC = "ASK_TRAFFIC"
    ASK_GMV = "ASK_GMV"
    ASK_ONLINE_GMV = "ASK_ONLINE_GMV"
    ASK_ORDER = "ASK_ORDER"
    ASK_PIECES = "ASK_PIECES"
    ASK_NO_BUY_REASON = "ASK_NO_BUY_REASON"
    ASK_STOCK_ISSUE = "ASK_STOCK_ISSUE"
    ASK_NOTE = "ASK_NOTE"
    REVIEW_SUMMARY = "REVIEW_SUMMARY"
    CONFIRM_DUPLICATE = "CONFIRM_DUPLICATE"
    DONE = "DONE"


_NEXT_STEPS: dict[Step, Step] = {
    Step.START: Step.AWAITING_LOCATION,
    Step.ASK_TRAFFIC: Step.ASK_GMV,
    Step.ASK_GMV: Step.ASK_ONLINE_GMV,
    Step.ASK_ONLINE_GMV: Step.ASK_ORDER,
    Step.ASK_ORDER: Step.ASK_PIECES,
    Step.ASK_PIECES: Step.ASK_STOCK_ISSUE,
    Step.ASK_NO_BUY_REASON: Step.ASK_STOCK_ISSUE,
    Step.ASK_STOCK_ISSUE: Step.ASK_NOTE,
    Step.ASK_NOTE: Step.REVIEW_SUMMARY,
}

NUMERIC_STEP_FIELDS: dict[Step, str] = {
    Step.ASK_TRAFFIC: "traffic",
    Step.ASK_GMV: "offline_gmv",
    Step.ASK_ONLINE_GMV: "online_gmv",
    Step.ASK_ORDER: "order_count",
    Step.ASK_PIECES: "pieces_sold",
}


def next_step(step: Step) -> Step:
    return _NEXT_STEPS[step]


def apply_numeric_answer(
    step: Step,
    draft_report: Mapping[str, Any],
    value: int,
) -> tuple[Step, dict[str, Any]]:
    draft = dict(draft_report)
    draft[NUMERIC_STEP_FIELDS[step]] = value

    if step == Step.ASK_TRAFFIC:
        if value == 0:
            draft["offline_gmv"] = 0
            draft["no_buy_reason"] = "-"
            return Step.ASK_ONLINE_GMV, draft
        return Step.ASK_GMV, draft

    if step == Step.ASK_GMV:
        return Step.ASK_ONLINE_GMV, draft

    if step == Step.ASK_ONLINE_GMV:
        total_gmv = draft.get("offline_gmv", 0) + draft["online_gmv"]
        if total_gmv == 0:
            draft["order_count"] = 0
            draft["pieces_sold"] = 0
            draft["no_buy_reason"] = "-"
            return Step.ASK_STOCK_ISSUE, draft
        return Step.ASK_ORDER, draft

    if step == Step.ASK_ORDER:
        return Step.ASK_PIECES, draft

    if step == Step.ASK_PIECES:
        draft["no_buy_reason"] = "-"
        return Step.ASK_STOCK_ISSUE, draft

    return next_step(step), draft

from app.domain.session_state import Step, next_step


def test_sales_source_steps_replace_legacy_numeric_steps() -> None:
    step_values = {step.value for step in Step}

    assert "ASK_SALES_SOURCES" in step_values
    assert "ASK_SALES_INPUT" in step_values
    assert "REVIEW_SALES_SUMMARY" in step_values
    assert "EDIT_SALES_MENU" in step_values
    assert "ASK_TRAFFIC" not in step_values
    assert "ASK_GMV" not in step_values
    assert "ASK_ONLINE_GMV" not in step_values
    assert "ASK_ORDER" not in step_values
    assert "ASK_PIECES" not in step_values
    assert "ASK_NO_BUY_REASON" not in step_values


def test_remaining_linear_transitions() -> None:
    assert next_step(Step.START) == Step.AWAITING_LOCATION
    assert next_step(Step.ASK_STOCK_ISSUE) == Step.ASK_NOTE
    assert next_step(Step.ASK_NOTE) == Step.REVIEW_SUMMARY

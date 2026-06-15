from app.domain.session_state import Step, apply_numeric_answer


def test_zero_traffic_sets_offline_gmv_and_skips_to_online_gmv() -> None:
    next_step, draft = apply_numeric_answer(Step.ASK_TRAFFIC, {}, 0)

    assert next_step == Step.ASK_ONLINE_GMV
    assert draft["traffic"] == 0
    assert draft["offline_gmv"] == 0
    assert draft["no_buy_reason"] == "-"


def test_zero_traffic_and_zero_online_gmv_skips_order_pieces_and_no_buy_reason() -> None:
    next_step, draft = apply_numeric_answer(
        Step.ASK_ONLINE_GMV,
        {"traffic": 0, "offline_gmv": 0, "no_buy_reason": "-"},
        0,
    )

    assert next_step == Step.ASK_STOCK_ISSUE
    assert draft["online_gmv"] == 0
    assert draft["order_count"] == 0
    assert draft["pieces_sold"] == 0
    assert draft["no_buy_reason"] == "-"


def test_zero_traffic_and_online_sales_asks_order_then_skips_no_buy_after_pieces() -> None:
    next_step, draft = apply_numeric_answer(
        Step.ASK_ONLINE_GMV,
        {"traffic": 0, "offline_gmv": 0, "no_buy_reason": "-"},
        100000,
    )

    assert next_step == Step.ASK_ORDER
    next_step, draft = apply_numeric_answer(Step.ASK_ORDER, draft, 2)
    assert next_step == Step.ASK_PIECES
    next_step, draft = apply_numeric_answer(Step.ASK_PIECES, draft, 3)
    assert next_step == Step.ASK_STOCK_ISSUE
    assert draft["order_count"] == 2
    assert draft["pieces_sold"] == 3
    assert draft["no_buy_reason"] == "-"


def test_positive_traffic_and_zero_total_gmv_skips_order_pieces_and_no_buy_reason() -> None:
    next_step, draft = apply_numeric_answer(Step.ASK_TRAFFIC, {}, 5)
    assert next_step == Step.ASK_GMV
    next_step, draft = apply_numeric_answer(Step.ASK_GMV, draft, 0)
    assert next_step == Step.ASK_ONLINE_GMV
    next_step, draft = apply_numeric_answer(Step.ASK_ONLINE_GMV, draft, 0)

    assert next_step == Step.ASK_STOCK_ISSUE
    assert draft["order_count"] == 0
    assert draft["pieces_sold"] == 0
    assert draft["no_buy_reason"] == "-"


def test_positive_traffic_and_any_gmv_asks_order_pieces_then_stock_issue() -> None:
    next_step, draft = apply_numeric_answer(Step.ASK_TRAFFIC, {}, 5)
    assert next_step == Step.ASK_GMV
    next_step, draft = apply_numeric_answer(Step.ASK_GMV, draft, 100000)
    assert next_step == Step.ASK_ONLINE_GMV
    next_step, draft = apply_numeric_answer(Step.ASK_ONLINE_GMV, draft, 0)
    assert next_step == Step.ASK_ORDER
    next_step, draft = apply_numeric_answer(Step.ASK_ORDER, draft, 1)
    assert next_step == Step.ASK_PIECES
    next_step, draft = apply_numeric_answer(Step.ASK_PIECES, draft, 2)

    assert next_step == Step.ASK_STOCK_ISSUE
    assert draft["no_buy_reason"] == "-"

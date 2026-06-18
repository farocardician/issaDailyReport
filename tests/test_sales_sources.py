from app.domain.sales_sources import input_plan, sales_totals, source_fields


def test_source_fields_adds_traffic_only_when_required() -> None:
    assert source_fields(True) == ("traffic", "gmv", "order_count", "pieces_sold")
    assert source_fields(False) == ("gmv", "order_count", "pieces_sold")


def test_input_plan_keeps_source_order_and_field_order() -> None:
    assert input_plan([("outlet", True), ("shopee", False)]) == [
        ("outlet", "traffic"),
        ("outlet", "gmv"),
        ("outlet", "order_count"),
        ("outlet", "pieces_sold"),
        ("shopee", "gmv"),
        ("shopee", "order_count"),
        ("shopee", "pieces_sold"),
    ]


def test_sales_totals_excludes_traffic() -> None:
    totals = sales_totals(
        {
            "outlet": {"traffic": 10, "gmv": 100000, "order_count": 2, "pieces_sold": 3},
            "shopee": {"gmv": 250000, "order_count": 4, "pieces_sold": 5},
        }
    )

    assert totals == {"gmv": 350000, "order_count": 6, "pieces_sold": 8}

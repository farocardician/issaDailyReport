from app.bot.sales_text import (
    format_amount,
    sales_summary_text,
    selected_sources_text,
    source_input_count,
    source_input_position,
)
from app.templates import MessageTemplates


def _templates() -> MessageTemplates:
    return MessageTemplates(
        {
            "SELECTED_PREFIX": "✓",
            "SALES_SOURCES_SELECTED_EMPTY": "Belum ada sumber penjualan yang dipilih.",
            "SALES_SOURCES_SELECTED_HEADER": "Dipilih:",
            "SALES_SUMMARY_LINE": "{{source}} | traffic={{traffic}} | gmv={{gmv}} | order={{order_count}} | pieces={{pieces_sold}}",
            "SALES_NO_SALES_LABEL": "Tidak Ada Penjualan",
        }
    )


def test_sales_summary_text_uses_snapshot_label_and_totals() -> None:
    summary = sales_summary_text(
        _templates(),
        [
            {
                "source_label": "Shopee Lama",
                "requires_traffic": False,
                "gmv": 100000,
                "order_count": 2,
                "pieces_sold": 3,
            },
            {
                "label": "Outlet",
                "requires_traffic": True,
                "traffic": 5,
                "gmv": 200000,
                "order_count": 4,
                "pieces_sold": 6,
            },
        ],
    )

    assert summary == {
        "sales_breakdown": (
            "Shopee Lama | traffic=- | gmv=100.000 | order=2 | pieces=3\n"
            "Outlet | traffic=5 | gmv=200.000 | order=4 | pieces=6"
        ),
        "total_gmv": "300.000",
        "total_order": 6,
        "total_pieces": 9,
    }


def test_sales_summary_text_no_sales_branch() -> None:
    assert sales_summary_text(_templates(), []) == {
        "sales_breakdown": "Tidak Ada Penjualan",
        "total_gmv": 0,
        "total_order": 0,
        "total_pieces": 0,
    }


def test_selected_sources_text() -> None:
    assert selected_sources_text(_templates(), []) == "Belum ada sumber penjualan yang dipilih."
    assert selected_sources_text(_templates(), ["Outlet", "Shopee"]) == "Dipilih:\n✓ Outlet\n✓ Shopee"


def test_source_input_position_and_count() -> None:
    source_ids = ["outlet", "shopee", "tokopedia"]

    assert source_input_position(source_ids, "shopee") == 2
    assert source_input_count(source_ids) == 3


def test_format_amount_uses_indonesian_thousand_separator() -> None:
    assert format_amount(1234567) == "1.234.567"

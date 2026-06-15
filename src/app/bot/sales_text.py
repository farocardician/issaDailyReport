from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.sales_sources import sales_totals
from app.templates import MessageTemplates


def selected_sources_text(templates: MessageTemplates, labels: Sequence[str]) -> str:
    if not labels:
        return templates.render("SALES_SOURCES_SELECTED_EMPTY")

    lines = [templates.render("SALES_SOURCES_SELECTED_HEADER")]
    selected_prefix = templates.render("SELECTED_PREFIX")
    lines.extend(f"{selected_prefix} {label}" for label in labels)
    return "\n".join(lines)


def sales_summary_text(
    templates: MessageTemplates,
    ordered_sources: Sequence[Mapping[str, Any]],
) -> dict[str, str | int]:
    if not ordered_sources:
        return {
            "sales_breakdown": templates.render("SALES_NO_SALES_LABEL"),
            "total_gmv": 0,
            "total_order": 0,
            "total_pieces": 0,
        }

    totals = sales_totals({str(index): row for index, row in enumerate(ordered_sources)})
    lines = [
        templates.render(
            "SALES_SUMMARY_LINE",
            source=_source_label(row),
            traffic=_traffic_value(row),
            gmv=format_amount(int(row["gmv"])),
            order_count=int(row["order_count"]),
            pieces_sold=int(row["pieces_sold"]),
        )
        for row in ordered_sources
    ]
    return {
        "sales_breakdown": "\n".join(lines),
        "total_gmv": format_amount(totals["gmv"]),
        "total_order": totals["order_count"],
        "total_pieces": totals["pieces_sold"],
    }


def source_input_position(source_ids: Sequence[str], current_source_id: str) -> int:
    return list(source_ids).index(current_source_id) + 1


def source_input_count(source_ids: Sequence[str]) -> int:
    return len(source_ids)


def format_amount(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _source_label(row: Mapping[str, Any]) -> str:
    return str(row.get("source_label") or row["label"])


def _traffic_value(row: Mapping[str, Any]) -> str | int:
    if not bool(row.get("requires_traffic")):
        return "-"
    traffic = row.get("traffic")
    return "-" if traffic is None else int(traffic)

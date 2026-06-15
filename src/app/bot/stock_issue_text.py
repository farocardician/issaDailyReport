from __future__ import annotations

from app.templates import MessageTemplates


def selected_issue_text(templates: MessageTemplates, selected_issues: list[str]) -> str:
    if not selected_issues:
        return templates.render("STOCK_ISSUE_SELECTED_EMPTY")

    lines = [templates.render("STOCK_ISSUE_SELECTED_HEADER")]
    selected_prefix = templates.render("SELECTED_PREFIX")
    lines.extend(f"{selected_prefix} {issue}" for issue in selected_issues)
    return "\n".join(lines)


def sku_list_text(templates: MessageTemplates, sku_values: list[str]) -> str:
    if not sku_values:
        return templates.render("STOCK_ISSUE_SKU_EMPTY")

    lines = [templates.render("STOCK_ISSUE_SKU_HEADER")]
    selected_prefix = templates.render("SELECTED_PREFIX")
    lines.extend(f"{selected_prefix} {sku}" for sku in sku_values)
    return "\n".join(lines)


def parse_sku_values(text: str) -> list[str]:
    return [value.strip() for value in text.split(",") if value.strip()]


def current_detail_position(detail_option_ids: list[str], current_option_id: str) -> int:
    return detail_option_ids.index(current_option_id) + 1


def next_detail_option_id(detail_option_ids: list[str], current_option_id: str | None) -> str | None:
    next_index = detail_option_ids.index(current_option_id) + 1 if current_option_id in detail_option_ids else 0
    if next_index >= len(detail_option_ids):
        return None
    return detail_option_ids[next_index]

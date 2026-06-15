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


def merge_sku_values(current_values: list[str], new_values: list[str]) -> list[str]:
    merged = list(current_values)
    for sku in new_values:
        if sku not in merged:
            merged.append(sku)
    return merged


def current_sku_values(draft: dict, current_option_id: str) -> list[str]:
    return list(dict(draft.get("stock_issue_sku_details", {})).get(current_option_id, []))


def has_current_sku_values(draft: dict, current_option_id: str) -> bool:
    return bool(current_sku_values(draft, current_option_id))


def continue_button_label(
    templates: MessageTemplates,
    next_issue_label: str | None,
    next_phase_label: str,
) -> str:
    if next_issue_label is not None:
        return templates.render_plain("BUTTON_CONTINUE_TO_NEXT_ISSUE", next_issue_label=next_issue_label)
    return templates.render_plain("BUTTON_CONTINUE_TO_NEXT_PHASE", next_phase_label=next_phase_label)


def detail_instruction_text(templates: MessageTemplates, show_skip_instruction: bool) -> str:
    lines = [templates.render("STOCK_ISSUE_DETAIL_INPUT_INSTRUCTION")]
    if show_skip_instruction:
        lines.append(templates.render("STOCK_ISSUE_DETAIL_SKIP_INSTRUCTION"))
    return "\n".join(lines)


def current_detail_position(detail_option_ids: list[str], current_option_id: str) -> int:
    return detail_option_ids.index(current_option_id) + 1


def next_detail_option_id(detail_option_ids: list[str], current_option_id: str | None) -> str | None:
    next_index = detail_option_ids.index(current_option_id) + 1 if current_option_id in detail_option_ids else 0
    if next_index >= len(detail_option_ids):
        return None
    return detail_option_ids[next_index]

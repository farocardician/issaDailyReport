from app.bot.stock_issue_text import (
    continue_button_label,
    detail_instruction_text,
    has_current_sku_values,
    merge_sku_values,
    next_detail_option_id,
    parse_sku_values,
    selected_issue_text,
    sku_list_text,
)
from app.templates import MessageTemplates


def _templates() -> MessageTemplates:
    return MessageTemplates(
        {
            "SELECTED_PREFIX": "✓",
            "STOCK_ISSUE_SELECTED_EMPTY": "Belum ada yang dipilih.",
            "STOCK_ISSUE_SELECTED_HEADER": "Dipilih:",
            "STOCK_ISSUE_SKU_EMPTY": "Belum ada SKU yang diinput.",
            "STOCK_ISSUE_SKU_HEADER": "SKU yang sudah diinput:",
            "BUTTON_CONTINUE_TO_NEXT_ISSUE": "Lanjut ke {{next_issue_label}}",
            "BUTTON_CONTINUE_TO_NEXT_PHASE": "Lanjut ke {{next_phase_label}}",
            "STOCK_ISSUE_DETAIL_INPUT_INSTRUCTION": "Ketik SKU satu per satu, atau beberapa SKU dipisahkan koma.",
            "STOCK_ISSUE_DETAIL_SKIP_INSTRUCTION": "Tekan <b>Lewati SKU</b> kalau tidak perlu isi SKU.",
        }
    )


def test_first_stock_issue_selection_text_has_no_detail_substep() -> None:
    text = selected_issue_text(_templates(), [])

    assert text == "Belum ada yang dipilih."
    assert "1/" not in text


def test_selected_issue_list_displays_checklist() -> None:
    text = selected_issue_text(_templates(), ["Size habis", "Warna habis"])

    assert text == "Dipilih:\n✓ Size habis\n✓ Warna habis"


def test_empty_sku_state_displays_empty_copy() -> None:
    assert sku_list_text(_templates(), []) == "Belum ada SKU yang diinput."


def test_parse_one_sku_input() -> None:
    assert parse_sku_values("SKU-001") == ["SKU-001"]


def test_input_sku_one_by_one_merges_with_existing_values() -> None:
    assert merge_sku_values(["SKU-001"], parse_sku_values("SKU-002")) == ["SKU-001", "SKU-002"]


def test_parse_multiple_comma_separated_skus() -> None:
    assert parse_sku_values("SKU-001, SKU-002,SKU-003") == ["SKU-001", "SKU-002", "SKU-003"]


def test_input_multiple_comma_separated_skus_merges_with_existing_values() -> None:
    assert merge_sku_values(["SKU-001"], parse_sku_values("SKU-002, SKU-003")) == [
        "SKU-001",
        "SKU-002",
        "SKU-003",
    ]


def test_existing_sku_list_displays_checklist_items() -> None:
    text = sku_list_text(_templates(), ["SKU-001", "SKU-002"])

    assert text == "SKU yang sudah diinput:\n✓ SKU-001\n✓ SKU-002"


def test_done_moves_to_next_selected_issue() -> None:
    assert next_detail_option_id(["size_empty", "color_empty"], "size_empty") == "color_empty"


def test_skip_keeps_issue_selected_and_moves_to_next_issue() -> None:
    selected_issue_ids = ["size_empty", "color_empty"]
    details = {"size_empty": []}

    assert "size_empty" in selected_issue_ids
    assert details["size_empty"] == []
    assert next_detail_option_id(selected_issue_ids, "size_empty") == "color_empty"


def test_dynamic_detail_count_follows_selected_issue_count() -> None:
    selected_issue_ids = ["size_empty", "color_empty", "not_arrived", "stock_empty"]

    assert len(selected_issue_ids) == 4
    assert next_detail_option_id(selected_issue_ids, "stock_empty") is None


def test_continue_button_points_to_next_selected_issue_when_available() -> None:
    assert continue_button_label(_templates(), "Warna Habis", "Catatan") == "Lanjut ke Warna Habis"


def test_continue_button_points_to_next_phase_for_last_issue() -> None:
    assert continue_button_label(_templates(), None, "Catatan") == "Lanjut ke Catatan"


def test_skip_instruction_appears_only_when_skip_button_visible() -> None:
    assert detail_instruction_text(_templates(), True) == (
        "Ketik SKU satu per satu, atau beberapa SKU dipisahkan koma.\n"
        "Tekan <b>Lewati SKU</b> kalau tidak perlu isi SKU."
    )
    assert detail_instruction_text(_templates(), False) == "Ketik SKU satu per satu, atau beberapa SKU dipisahkan koma."


def test_sku_presence_controls_skip_visibility() -> None:
    assert not has_current_sku_values({"stock_issue_sku_details": {"size_empty": []}}, "size_empty")
    assert has_current_sku_values({"stock_issue_sku_details": {"size_empty": ["SKU-001"]}}, "size_empty")

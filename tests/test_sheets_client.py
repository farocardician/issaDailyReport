from typing import Any

from gspread.exceptions import WorksheetNotFound

from app.sheets.client import SheetsClient


class _FakeWorksheet:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def clear(self) -> None:
        self.calls.append(("clear", None))

    def update(self, values, range_name, value_input_option=None) -> None:
        self.calls.append(("update", values, range_name, value_input_option))

    def freeze(self, rows: int) -> None:
        self.calls.append(("freeze", rows))

    def set_basic_filter(self) -> None:
        self.calls.append(("set_basic_filter", None))


class _FakeSpreadsheet:
    def __init__(self, worksheet: _FakeWorksheet | None = None) -> None:
        self._worksheet = worksheet
        self.added: list[tuple[str, int, int]] = []

    def worksheet(self, title: str) -> _FakeWorksheet:
        if self._worksheet is None:
            raise WorksheetNotFound(title)
        return self._worksheet

    def add_worksheet(self, title: str, rows: int, cols: int) -> _FakeWorksheet:
        self.added.append((title, rows, cols))
        self._worksheet = _FakeWorksheet()
        return self._worksheet


class _FakeGspreadClient:
    def __init__(self, spreadsheet: _FakeSpreadsheet) -> None:
        self.spreadsheet = spreadsheet
        self.opened_key: str | None = None

    def open_by_key(self, spreadsheet_id: str) -> _FakeSpreadsheet:
        self.opened_key = spreadsheet_id
        return self.spreadsheet


def test_rebuild_worksheet_writes_rows_and_applies_header_controls() -> None:
    worksheet = _FakeWorksheet()
    spreadsheet = _FakeSpreadsheet(worksheet)
    fake_client = _FakeGspreadClient(spreadsheet)

    client = SheetsClient(
        "credentials.json",
        "spreadsheet-id",
        client_factory=lambda filename: fake_client,
    )
    client.rebuild_worksheet("Master_Flat", ["report_id", "gmv"], [["RPT-1", 100]])

    assert fake_client.opened_key == "spreadsheet-id"
    assert worksheet.calls == [
        ("clear", None),
        ("update", [["report_id", "gmv"], ["RPT-1", 100]], "A1", "RAW"),
        ("freeze", 1),
        ("set_basic_filter", None),
    ]


def test_rebuild_worksheet_creates_missing_tab() -> None:
    spreadsheet = _FakeSpreadsheet()
    fake_client = _FakeGspreadClient(spreadsheet)

    client = SheetsClient(
        "credentials.json",
        "spreadsheet-id",
        client_factory=lambda filename: fake_client,
    )
    client.rebuild_worksheet("Master_Flat", ["report_id", "gmv"], [["RPT-1", 100]])

    assert spreadsheet.added == [("Master_Flat", 2, 2)]
    assert spreadsheet._worksheet is not None
    assert spreadsheet._worksheet.calls[0] == ("clear", None)

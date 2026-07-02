from collections.abc import Callable, Sequence
from typing import Any

import gspread
from gspread.exceptions import WorksheetNotFound


class SheetsClient:
    def __init__(
        self,
        credentials_path: str,
        spreadsheet_id: str,
        client_factory: Callable[..., Any] = gspread.service_account,
    ) -> None:
        client = client_factory(filename=credentials_path)
        self._spreadsheet = client.open_by_key(spreadsheet_id)

    def rebuild_worksheet(self, title: str, header: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        try:
            worksheet = self._spreadsheet.worksheet(title)
        except WorksheetNotFound:
            worksheet = self._spreadsheet.add_worksheet(
                title=title,
                rows=max(len(rows) + 1, 1),
                cols=len(header),
            )

        worksheet.clear()
        worksheet.update([list(header), *[list(row) for row in rows]], "A1", value_input_option="RAW")
        worksheet.freeze(rows=1)
        worksheet.set_basic_filter()

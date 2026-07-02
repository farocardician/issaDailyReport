import asyncio
import logging
from pathlib import Path

from app.config import Settings
from app.db import create_pool
from app.domain.sheets_export import MASTER_FLAT_HEADER, build_master_flat_rows
from app.repositories.reports import ReportsRepository
from app.sheets.client import SheetsClient


async def main() -> None:
    settings = Settings()
    if not settings.google_sheets_export_enabled:
        logging.info("Google Sheets export disabled; skipping.")
        return
    if not settings.google_sheets_master_spreadsheet_id:
        raise RuntimeError("GOOGLE_SHEETS_MASTER_SPREADSHEET_ID is required")
    creds = settings.google_application_credentials
    if not creds or not Path(creds).is_file():
        raise RuntimeError(
            f"GOOGLE_APPLICATION_CREDENTIALS must point to an existing file (got {creds!r})"
        )

    pool = await create_pool(settings.database_url)
    try:
        records = await ReportsRepository(pool).list_for_export()
    finally:
        await pool.close()

    rows = build_master_flat_rows(records)
    client = SheetsClient(
        settings.google_application_credentials,
        settings.google_sheets_master_spreadsheet_id,
    )
    client.rebuild_worksheet("Master_Flat", MASTER_FLAT_HEADER, rows)


if __name__ == "__main__":
    asyncio.run(main())

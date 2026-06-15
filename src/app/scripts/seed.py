import asyncio
import csv
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db import bootstrap_schema, create_pool

REFERENCE_DIR = Path("Reference")
DEPRECATED_UI_TRANSLATE_KEYS = (
    "ASK_TRAFFIC",
    "ASK_GMV",
    "ASK_ONLINE_GMV",
    "ASK_ORDER",
    "ASK_PIECES",
    "ASK_NO_BUY_REASON",
    "PROGRESS_PHASE_TRAFFIC",
    "PROGRESS_PHASE_GMV_OFFLINE",
    "PROGRESS_PHASE_GMV_ONLINE",
    "PROGRESS_PHASE_ORDER_PIECES",
    "BUTTON_SALES_DONE",
    "PROGRESS_SUBSTEP_LABEL",
    "PROGRESS_SUBSTEP_FORMAT",
    "PROGRESS_WITH_SUBSTEP_FORMAT",
    "PROGRESS_ISSUE_REASON",
    "PROGRESS_ISSUE_STOCK",
    "PROGRESS_ISSUE_NOTE",
)


async def main() -> None:
    settings = Settings()
    pool = await create_pool(settings.database_url)
    try:
        await bootstrap_schema(pool)
        await seed_stores(pool)
        await seed_users(pool)
        await seed_gmv_sources(pool)
        await seed_ui_translate(pool)
    finally:
        await pool.close()


async def seed_stores(pool) -> None:
    rows = _read_csv(REFERENCE_DIR / "store_master.csv")
    async with pool.acquire() as connection:
        for row in rows:
            await connection.execute(
                """
                INSERT INTO stores (
                    store_id, department_store, branch, city, brand, latitude, longitude,
                    allowed_radius_meter, status, notes
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (store_id) DO UPDATE
                SET department_store = EXCLUDED.department_store,
                    branch = EXCLUDED.branch,
                    city = EXCLUDED.city,
                    brand = EXCLUDED.brand,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    allowed_radius_meter = EXCLUDED.allowed_radius_meter,
                    status = EXCLUDED.status,
                    notes = EXCLUDED.notes
                """,
                row["Store_ID"],
                row["Department_Store"],
                row["Branch"],
                row["City"],
                row["Brand"],
                _float_or_none(row["Latitude"]),
                _float_or_none(row["Longitude"]),
                _int_or_none(row["Allowed_Radius_Meter"]),
                row["Status"],
                _blank_to_none(row["Notes"]),
            )


async def seed_users(pool) -> None:
    rows = _read_csv(REFERENCE_DIR / "user_master.csv")
    async with pool.acquire() as connection:
        for row in rows:
            await connection.execute(
                """
                INSERT INTO users (
                    user_id, role, name, phone, email, pin, telegram_user_id,
                    telegram_chat_id, status, notes
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (user_id) DO UPDATE
                SET role = EXCLUDED.role,
                    name = EXCLUDED.name,
                    phone = EXCLUDED.phone,
                    email = EXCLUDED.email,
                    pin = EXCLUDED.pin,
                    telegram_user_id = EXCLUDED.telegram_user_id,
                    telegram_chat_id = EXCLUDED.telegram_chat_id,
                    status = EXCLUDED.status,
                    notes = EXCLUDED.notes
                """,
                row["User_ID"],
                row["User_Role"],
                row["User_Name"],
                _blank_to_none(row["User_Phone"]),
                _blank_to_none(row["User_Email"]),
                row["User_PIN"],
                _int_or_none(row["Telegram_User_ID"]),
                _int_or_none(row["Telegram_Chat_ID"]),
                row["Status"],
                _blank_to_none(row["Notes"]),
            )


async def seed_gmv_sources(pool) -> None:
    rows = _read_csv(REFERENCE_DIR / "gmv_sources.csv")
    async with pool.acquire() as connection:
        for row in rows:
            await connection.execute(
                """
                INSERT INTO gmv_sources (
                    gmv_source_id, label, source_type, requires_traffic, sort_order, status
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (gmv_source_id) DO UPDATE
                SET label = EXCLUDED.label,
                    source_type = EXCLUDED.source_type,
                    requires_traffic = EXCLUDED.requires_traffic,
                    sort_order = EXCLUDED.sort_order,
                    status = EXCLUDED.status
                """,
                row["Gmv_Source_ID"],
                row["Label"],
                row["Source_Type"],
                _bool(row["Requires_Traffic"]),
                int(row["Sort_Order"]),
                row["Status"],
            )


async def seed_ui_translate(pool) -> None:
    rows = _read_csv(REFERENCE_DIR / "ui_translate.csv", fieldnames=["key", "message"])
    async with pool.acquire() as connection:
        await connection.execute(
            "DELETE FROM ui_translate WHERE key = ANY($1::text[])",
            list(DEPRECATED_UI_TRANSLATE_KEYS),
        )
        for row in rows:
            await connection.execute(
                """
                INSERT INTO ui_translate (key, category, message, description)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (key) DO UPDATE
                SET category = EXCLUDED.category,
                    message = EXCLUDED.message,
                    description = EXCLUDED.description
                """,
                row["key"],
                _template_category(row["key"]),
                row["message"].replace("\\n", "\n"),
                "",
            )


def _read_csv(path: Path, fieldnames: list[str] | None = None) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file, fieldnames=fieldnames))


def _blank_to_none(value: str) -> str | None:
    value = value.strip()
    return value or None


def _int_or_none(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def _float_or_none(value: str) -> float | None:
    value = value.strip()
    return float(value) if value else None


def _bool(value: str) -> bool:
    return value.strip().casefold() == "true"


def _template_category(key: str) -> str:
    if key.startswith("BUTTON_"):
        return "button"
    if key.startswith("PROGRESS_") or key.startswith("CONTEXTUAL_STEP_") or key.startswith("NEXT_PHASE_"):
        return "progress"
    if key.startswith("ASK_"):
        return "prompt"
    if key.startswith("ADMIN_"):
        return "admin_notification"
    if key.startswith("SALES_"):
        return "sales"
    if key.startswith("STOCK_ISSUE_"):
        return "stock_issue"
    if key.startswith("STORE_"):
        return "store_display"
    if key.startswith("AREA_"):
        return "area_display"
    if key.startswith("DISTANCE_"):
        return "distance_display"
    if key.startswith("LOCATION_STATUS_"):
        return "location_status"
    if key.endswith("_COMMAND") or key.endswith("_ERROR") or key in {"SESSION_EXPIRED", "PRIVATE_CHAT_ONLY"}:
        return "system"
    return "message"


if __name__ == "__main__":
    asyncio.run(main())

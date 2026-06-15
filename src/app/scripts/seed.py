import asyncio
import csv
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db import bootstrap_schema, create_pool

REFERENCE_DIR = Path("Reference")
DEPRECATED_MESSAGE_TEMPLATE_KEYS = ("ASK_NO_BUY_REASON",)


async def main() -> None:
    settings = Settings()
    pool = await create_pool(settings.database_url)
    try:
        await bootstrap_schema(pool)
        await seed_stores(pool)
        await seed_users(pool)
        await seed_message_templates(pool)
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


async def seed_message_templates(pool) -> None:
    rows = _read_csv(REFERENCE_DIR / "message_template.csv", fieldnames=["key", "message"])
    async with pool.acquire() as connection:
        await connection.execute(
            "DELETE FROM message_templates WHERE key = ANY($1::text[])",
            list(DEPRECATED_MESSAGE_TEMPLATE_KEYS),
        )
        for row in rows:
            await connection.execute(
                """
                INSERT INTO message_templates (key, message)
                VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE
                SET message = EXCLUDED.message
                """,
                row["key"],
                row["message"].replace("\\n", "\n"),
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


if __name__ == "__main__":
    asyncio.run(main())

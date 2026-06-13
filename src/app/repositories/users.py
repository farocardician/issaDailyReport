from typing import Any

import asyncpg


class UsersRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def find_active_by_pin(self, pin: str, active_status: str) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT user_id, role, name, phone, email, pin, telegram_user_id,
                   telegram_chat_id, status, notes
            FROM users
            WHERE pin = $1 AND status = $2
            """,
            pin,
            active_status,
        )
        return [dict(row) for row in rows]

    async def bind_telegram(self, user_id: str, telegram_user_id: int, telegram_chat_id: int) -> None:
        await self._pool.execute(
            """
            UPDATE users
            SET telegram_user_id = $2,
                telegram_chat_id = $3
            WHERE user_id = $1
            """,
            user_id,
            telegram_user_id,
            telegram_chat_id,
        )

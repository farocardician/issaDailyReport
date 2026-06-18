from typing import Any

import asyncpg


class UsersRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT user_id, role, name, phone, email, telegram_user_id,
                   telegram_chat_id, status, notes
            FROM users
            WHERE user_id = $1
            """,
            user_id,
        )
        return dict(row) if row is not None else None

    async def list_by_role(self, role: str) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT user_id, role, name, phone, email, telegram_user_id,
                   telegram_chat_id, status, notes
            FROM users
            WHERE role = $1
            ORDER BY name
            """,
            role,
        )
        return [dict(row) for row in rows]

    async def list_all(self) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT user_id, role, name, phone, email, telegram_user_id,
                   telegram_chat_id, status, notes
            FROM users
            ORDER BY name
            """
        )
        return [dict(row) for row in rows]

    async def find_active_by_telegram_user_id(
        self,
        telegram_user_id: int,
        active_status: str,
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT user_id, role, name, phone, email, telegram_user_id,
                   telegram_chat_id, status, notes
            FROM users
            WHERE telegram_user_id = $1 AND status = $2
            """,
            telegram_user_id,
            active_status,
        )
        return [dict(row) for row in rows]

    async def list_active(self, active_status: str) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT user_id, role, name, phone, email, telegram_user_id,
                   telegram_chat_id, status, notes
            FROM users
            WHERE status = $1
            """,
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

    async def create_user(
        self,
        user_id: str,
        role: str,
        name: str,
        phone: str,
        email: str | None,
        notes: str | None,
        status: str,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO users (
                user_id, role, name, phone, email, telegram_user_id,
                telegram_chat_id, status, notes
            )
            VALUES ($1, $2, $3, $4, $5, NULL, NULL, $6, $7)
            """,
            user_id,
            role,
            name,
            phone,
            email,
            status,
            notes,
        )

    async def update_basic(
        self,
        user_id: str,
        name: str,
        phone: str,
        email: str | None,
        notes: str | None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE users
            SET name = $2,
                phone = $3,
                email = $4,
                notes = $5
            WHERE user_id = $1
            """,
            user_id,
            name,
            phone,
            email,
            notes,
        )

    async def set_status(self, user_id: str, status: str) -> None:
        await self._pool.execute(
            """
            UPDATE users
            SET status = $2
            WHERE user_id = $1
            """,
            user_id,
            status,
        )

    async def reset_telegram_link(self, user_id: str) -> None:
        await self._pool.execute(
            """
            UPDATE users
            SET telegram_user_id = NULL,
                telegram_chat_id = NULL
            WHERE user_id = $1
            """,
            user_id,
        )

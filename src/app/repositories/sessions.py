import json
from datetime import datetime
from typing import Any

import asyncpg

from app.domain.session_state import Step


class SessionsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, telegram_chat_id: int) -> dict[str, Any] | None:
        row = await self._pool.fetchrow(
            """
            SELECT telegram_chat_id, telegram_user_id, current_step, selected_store_id,
                   user_id, draft_report, updated_at, expires_at
            FROM bot_sessions
            WHERE telegram_chat_id = $1
            """,
            telegram_chat_id,
        )
        if row is None:
            return None
        session = dict(row)
        draft_report = session["draft_report"]
        if isinstance(draft_report, str):
            session["draft_report"] = json.loads(draft_report)
        return session

    async def upsert(
        self,
        telegram_chat_id: int,
        telegram_user_id: int,
        current_step: Step,
        draft_report: dict[str, Any],
        updated_at: datetime,
        expires_at: datetime,
        selected_store_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO bot_sessions (
                telegram_chat_id, telegram_user_id, current_step, selected_store_id,
                user_id, draft_report, updated_at, expires_at
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
            ON CONFLICT (telegram_chat_id) DO UPDATE
            SET telegram_user_id = EXCLUDED.telegram_user_id,
                current_step = EXCLUDED.current_step,
                selected_store_id = EXCLUDED.selected_store_id,
                user_id = EXCLUDED.user_id,
                draft_report = EXCLUDED.draft_report,
                updated_at = EXCLUDED.updated_at,
                expires_at = EXCLUDED.expires_at
            """,
            telegram_chat_id,
            telegram_user_id,
            current_step.value,
            selected_store_id,
            user_id,
            json.dumps(draft_report),
            updated_at,
            expires_at,
        )

    async def delete(self, telegram_chat_id: int) -> None:
        await self._pool.execute(
            "DELETE FROM bot_sessions WHERE telegram_chat_id = $1",
            telegram_chat_id,
        )

from functools import cached_property
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = ""
    admin_chat_id: int = 0
    database_url: str = "postgresql://spg:spg@db:5432/spg"
    bot_mode: Literal["webhook", "polling"] = "webhook"
    webhook_base_url: str = "https://bot.yourdomain.com"
    webhook_path: str = "/telegram/webhook"
    webhook_secret: str = "change-me-random"
    webhook_listen_port: int = 8080
    default_radius_meter: int = 100
    active_status: str = "Aktif"
    inactive_status: str = "Nonaktif"
    session_ttl_minutes: int = 30
    app_tz: str = "Asia/Jakarta"
    cloudflare_tunnel_token: str = ""

    @cached_property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.app_tz)

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_path}"

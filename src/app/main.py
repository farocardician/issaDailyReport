from app.bot.application import build_application
from app.config import Settings
from app.logging_setup import setup_logging


def main() -> None:
    setup_logging()
    settings = Settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not settings.admin_chat_id:
        raise RuntimeError("ADMIN_CHAT_ID is required")

    application = build_application(settings)
    if settings.bot_mode == "webhook":
        application.run_webhook(
            listen="0.0.0.0",
            port=settings.webhook_listen_port,
            url_path=settings.webhook_path,
            webhook_url=settings.webhook_url,
            secret_token=settings.webhook_secret,
        )
    else:
        application.run_polling()


if __name__ == "__main__":
    main()

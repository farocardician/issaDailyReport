import logging

from telegram.ext import Application

from app.bot.flow import ReportFlow
from app.bot.handlers import register_handlers
from app.config import Settings
from app.db import bootstrap_schema, create_pool
from app.repositories.reports import ReportsRepository
from app.repositories.sessions import SessionsRepository
from app.repositories.stores import StoresRepository
from app.repositories.templates import TemplatesRepository
from app.repositories.users import UsersRepository
from app.templates import MessageTemplates

logger = logging.getLogger(__name__)


def build_application(settings: Settings) -> Application:
    async def post_init(application: Application) -> None:
        pool = await create_pool(settings.database_url)
        await bootstrap_schema(pool)
        templates_repository = TemplatesRepository(pool)
        templates = MessageTemplates(await templates_repository.list_all())
        flow = ReportFlow(
            settings=settings,
            templates=templates,
            templates_repository=templates_repository,
            stores=StoresRepository(pool),
            users=UsersRepository(pool),
            reports=ReportsRepository(pool),
            sessions=SessionsRepository(pool),
        )
        application.bot_data["pool"] = pool
        application.bot_data["flow"] = flow
        logger.info("Bot application initialized")

    async def post_shutdown(application: Application) -> None:
        pool = application.bot_data.get("pool")
        if pool is not None:
            await pool.close()
            logger.info("Database pool closed")

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    register_handlers(application)
    return application

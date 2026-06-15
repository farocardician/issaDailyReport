from telegram import Bot
from telegram.constants import ParseMode


async def send_admin_notification(
    bot: Bot,
    admin_chat_id: int,
    message: str,
) -> None:
    if not admin_chat_id:
        return

    await bot.send_message(chat_id=admin_chat_id, text=message, parse_mode=ParseMode.HTML)

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters


def register_handlers(application) -> None:
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(callback_query))
    application.add_handler(MessageHandler(filters.LOCATION | filters.TEXT | filters.CONTACT, inbound_message))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.application.bot_data["flow"].handle_start(update, context)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.application.bot_data["flow"].handle_cancel(update, context)


async def inbound_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.application.bot_data["flow"].handle_message(update, context)


async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.application.bot_data["flow"].handle_callback(update, context)

#!/usr/bin/env python
# pylint: disable=unused-argument

import logging

from config import TELEGRAM_TOKEN
from handlers.text import bot_mentioned, bot_mention_filter, text_handler
from handlers.transcription import transcription_handler
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from database.main import init_database
from telegrambot.handlers.commands import resume, search_image, search_image_callback

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("image", search_image))
    # Image search callback
    application.add_handler(
        CallbackQueryHandler(search_image_callback, pattern="^search_image:")
    )
    # Bot mentioned - filter for mentions of @fimosin_bot
    application.add_handler(
        MessageHandler(bot_mention_filter & filters.TEXT, bot_mentioned)
    )
    # Funções
    application.add_handler(
        MessageHandler(filters.VOICE | filters.VIDEO_NOTE, transcription_handler)
    )
    # Text
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
    )
    init_database()
    application.run_polling()


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# pylint: disable=unused-argument

import logging

from config import TELEGRAM_TOKEN
from handlers.text import text_handler
from handlers.transcription import transcription_handler
from handlers.catch_all import catch_all_handler, catch_all_edited_handler
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from domain import init_database
from telegrambot.handlers.commands import (
    faq,
    resume,
    search_image,
    search_image_callback,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Catch-all - save ALL messages to database
    application.add_handler(
        MessageHandler(filters.ALL, catch_all_handler),
        group=-2,
    )
    # Catch-all for edited messages
    application.add_handler(
        MessageHandler(filters.UpdateType.EDITED_MESSAGE, catch_all_edited_handler),
        group=-2,
    )

    # Commands
    application.add_handler(CommandHandler("faq", faq))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("image", search_image))
    # Image search callback
    application.add_handler(
        CallbackQueryHandler(search_image_callback, pattern="^search_image:")
    )
    # Voice/Video Note transcription
    application.add_handler(
        MessageHandler(filters.VOICE | filters.VIDEO_NOTE, transcription_handler)
    )
    # Text (AI responses only, no DB save - catch-all handles that)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler),
    )

    init_database()
    application.run_polling()


if __name__ == "__main__":
    main()

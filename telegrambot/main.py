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
    delete,
    faq,
    online_agora,
    resume,
    search_image,
    search_image_callback,
    tldr,
)
from telegrambot.handlers.sticker import sticker, sticker_photo_filter, sticker_cmd_filter, sticker_media_filter, delete_sticker
from telegrambot.handlers.errors import error_handler

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
    application.add_error_handler(error_handler)

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
    application.add_handler(CommandHandler("delete", delete))
    application.add_handler(CommandHandler("faq", faq))
    application.add_handler(CommandHandler("resume", resume))
    application.add_handler(CommandHandler("tldr", tldr))
    application.add_handler(CommandHandler("image", search_image))
    application.add_handler(CommandHandler("online_agora", online_agora))
    application.add_handler(CommandHandler("sticker", sticker))
    application.add_handler(CommandHandler("delsticker", delete_sticker))
    # /sticker com foto anexada (caption)
    application.add_handler(
        MessageHandler(sticker_photo_filter, sticker)
    )
    # /sticker com GIF/video/document (caption)
    application.add_handler(
        MessageHandler(sticker_media_filter, sticker)
    )
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

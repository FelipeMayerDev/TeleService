import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from telegram import Update
from telegram.ext import CallbackContext

from domain import MessageService

message_service = MessageService()

logger = logging.getLogger(__name__)


async def media_logger(update: Update, context: CallbackContext):
    """Log media messages (photo, video, audio, document, etc.) to database."""
    if not update.message:
        return

    message = update.message

    try:
        from_user = None
        if message.from_user:
            from_user = message.from_user.username or message.from_user.first_name

        reply_to_message_id = None
        reply_text = None
        to_user = None
        if message.reply_to_message:
            reply_to_message_id = message.reply_to_message.message_id
            reply_text = (
                message.reply_to_message.text or message.reply_to_message.caption
            )
            if message.reply_to_message.from_user:
                to_user = (
                    message.reply_to_message.from_user.username
                    or message.reply_to_message.from_user.first_name
                )

        message_type = "unknown"
        text = message.caption or ""
        if message.photo:
            message_type = "photo"
            if not text:
                text = "[Photo]"
        elif message.video:
            message_type = "video"
            if not text:
                text = "[Video]"
        elif message.audio:
            message_type = "audio"
            text = f"[Audio: {message.audio.title or 'Untitled'}]"
        elif message.document:
            message_type = "document"
            text = f"[Document: {message.document.file_name or 'Unnamed file'}]"
        elif message.animation:
            message_type = "animation"
            if not text:
                text = "[GIF]"
        elif message.location:
            message_type = "location"
            text = (
                f"[Location: {message.location.latitude}, {message.location.longitude}]"
            )
        elif message.contact:
            message_type = "contact"
            text = f"[Contact: {message.contact.first_name}]"
        elif message.poll:
            message_type = "poll"
            text = f"[Poll: {message.poll.question}]"

        message_service.add_telegram_message(
            telegram_message_id=message.message_id,
            text=text,
            chat_id=message.chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
            message_type=message_type,
        )
    except Exception as e:
        logger.error(f"Error logging media message: {e}", exc_info=True)

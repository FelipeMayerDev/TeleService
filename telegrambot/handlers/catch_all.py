import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from telegram import Update
from telegram.ext import CallbackContext

from domain import MessageService

message_service = MessageService()

logger = logging.getLogger(__name__)


def _detect_message_type(message) -> str:
    if message.sticker:
        return "sticker"
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.video_note:
        return "video_note"
    if message.voice:
        return "voice"
    if message.audio:
        return "audio"
    if message.document:
        return "document"
    if message.animation:
        return "animation"
    if message.location:
        return "location"
    if message.contact:
        return "contact"
    if message.poll:
        return "poll"
    if message.dice:
        return "dice"
    if message.venue:
        return "venue"
    if message.sticker:
        return "sticker"
    if message.text:
        return "text"
    return "unknown"


def _get_message_text(message, message_type: str) -> str:
    if message_type == "sticker":
        return f"[Sticker: {message.sticker.emoji or message.sticker.set_name or 'unknown'}]"
    if message_type == "photo":
        return message.caption or "[Photo]"
    if message_type == "video":
        return message.caption or "[Video]"
    if message_type == "video_note":
        return message.caption or "[Video Note]"
    if message_type == "voice":
        return "[Voice]"
    if message_type == "audio":
        return f"[Audio: {message.audio.title or 'Untitled'}]"
    if message_type == "document":
        return f"[Document: {message.document.file_name or 'Unnamed file'}]"
    if message_type == "animation":
        return message.caption or "[GIF]"
    if message_type == "location":
        return f"[Location: {message.location.latitude}, {message.location.longitude}]"
    if message_type == "contact":
        text = f"[Contact: {message.contact.first_name}"
        if message.contact.phone_number:
            text += f" - {message.contact.phone_number}"
        return f"{text}]"
    if message_type == "poll":
        return f"[Poll: {message.poll.question}]"
    if message_type == "dice":
        return f"[Dice: {message.dice.value}]"
    if message_type == "venue":
        return f"[Venue: {message.venue.title}]"
    if message.text:
        return message.text
    if message.caption:
        return message.caption
    return "[Unsupported message type]"


def _get_from_user(message) -> str | None:
    if message.from_user:
        return message.from_user.username or message.from_user.first_name
    return None


def _get_reply_info(message):
    reply_to_message_id = None
    reply_text = None
    to_user = None

    if message.reply_to_message:
        reply_to_message_id = message.reply_to_message.message_id
        reply_text = message.reply_to_message.text or message.reply_to_message.caption
        if message.reply_to_message.from_user:
            to_user = (
                message.reply_to_message.from_user.username
                or message.reply_to_message.from_user.first_name
            )

    return reply_to_message_id, reply_text, to_user


async def catch_all_handler(update: Update, context: CallbackContext):
    if not update.message:
        return

    message = update.message

    try:
        message_type = _detect_message_type(message)
        text = _get_message_text(message, message_type)
        from_user = _get_from_user(message)
        reply_to_message_id, reply_text, to_user = _get_reply_info(message)

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
        logger.error(f"Error saving message (catch-all): {e}", exc_info=True)


async def catch_all_edited_handler(update: Update, context: CallbackContext):
    if not update.edited_message:
        return

    message = update.edited_message

    try:
        message_type = "edited_message"
        text = message.text or message.caption or "[Edited message without text]"
        from_user = _get_from_user(message)
        reply_to_message_id, reply_text, to_user = _get_reply_info(message)

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
        logger.error(f"Error saving edited message: {e}", exc_info=True)

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from telegram import Update
from telegram.ext import CallbackContext

from database.managers import MessageManager


async def message_logger(update: Update, context: CallbackContext):
    if not update.message:
        return

    message = update.message

    from_user = None
    if message.from_user:
        from_user = message.from_user.username or message.from_user.first_name

    reply_to_message_id = None
    reply_text = None
    to_user = None
    if message.reply_to_message:
        reply_to_message_id = message.reply_to_message.message_id
        reply_text = message.reply_to_message.text
        if message.reply_to_message.from_user:
            to_user = (
                message.reply_to_message.from_user.username
                or message.reply_to_message.from_user.first_name
            )

    message_type = "text"
    if message.voice:
        message_type = "voice"
    elif message.video_note:
        message_type = "video_note"
    elif message.photo:
        message_type = "photo"
    elif message.video:
        message_type = "video"
    elif message.audio:
        message_type = "audio"
    elif message.sticker:
        message_type = "sticker"
    elif message.document:
        message_type = "document"
    elif message.animation:
        message_type = "animation"
    elif message.location:
        message_type = "location"
    elif message.contact:
        message_type = "contact"
    elif message.poll:
        message_type = "poll"

    text = message.text or message.caption or ""
    if message.voice:
        text = "[Voice message]"
    elif message.video_note:
        text = "[Video note]"
    elif message.sticker:
        text = "[Sticker]"
    elif message.location:
        text = f"[Location: {message.location.latitude}, {message.location.longitude}]"
    elif message.contact:
        text = f"[Contact: {message.contact.first_name}]"
    elif message.poll:
        text = f"[Poll: {message.poll.question}]"
    elif message.animation:
        text = "[GIF]"

    try:
        MessageManager.add_message(
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
        print(f"Error logging message: {e}")

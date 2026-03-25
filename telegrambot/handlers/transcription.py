import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from telegram import Update
from telegram.ext import CallbackContext

from domain import MessageService
from providers.groq import GroqProvider

message_service = MessageService()


async def transcription_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    message = update.message
    status_message = await message.reply_text("Transcription in progress...")
    _audio_file = await message.voice.get_file()

    file_path = f"/tmp/{_audio_file.file_id}.ogg"
    await _audio_file.download_to_drive(file_path)

    tanscripted = GroqProvider().transcribe_audio(file_path)
    final_message = f"*{user.first_name}* disse: {tanscripted}"

    from_user = None
    if message.from_user:
        from_user = message.from_user.username or message.from_user.first_name

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

    try:
        message_service.add_telegram_message(
            telegram_message_id=message.message_id,
            text=f"[Voice message - {tanscripted}]",
            chat_id=message.chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
            message_type="voice",
        )
    except Exception as e:
        print(f"Error logging voice message: {e}")

    os.remove(file_path)
    await status_message.edit_text(final_message, parse_mode="markdown")

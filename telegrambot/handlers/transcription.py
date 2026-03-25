import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from telegram import Update
from telegram.ext import CallbackContext

from providers.groq import GroqProvider
from database.managers import MessageManager


async def transcription_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    message = update.message
    status_message = await message.reply_text("Transcription in progress...")
    _audio_file = await message.voice.get_file()

    file_path = f"/tmp/{_audio_file.file_id}.ogg"
    await _audio_file.download_to_drive(file_path)

    tanscripted = GroqProvider().transcribe_audio(file_path)

    from_user = None
    if message.from_user:
        from_user = message.from_user.username or message.from_user.first_name

    MessageManager.add_message(
        telegram_message_id=message.message_id,
        text=f"[Voice message - {tanscripted}]",
        chat_id=message.chat_id,
        from_user=from_user,
        to_user=None,
        reply_to_message_id=None,
        reply_text=None,
        message_type="voice_transcription",
    )

    final_message = f"*{user.first_name}* disse: {tanscripted}"
    os.remove(file_path)
    await status_message.edit_text(final_message, parse_mode="markdown")

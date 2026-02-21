import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from telegram import Update
from telegram.ext import CallbackContext

from providers.groq import GroqProvider


async def transcription_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    message = update.message
    status_message = await message.reply_text("Transcription in progress...")
    _audio_file = await message.voice.get_file()

    file_path = f"/tmp/{_audio_file.file_id}.ogg"
    await _audio_file.download_to_drive(file_path)

    tanscripted = GroqProvider().transcribe_audio(file_path)
    final_message = f"*{user}* disse: {tanscripted}"
    os.remove(file_path)
    await status_message.edit_text(final_message, parse_mode="markdown")

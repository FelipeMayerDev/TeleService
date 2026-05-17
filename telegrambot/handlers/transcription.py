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

    if message.voice:
        attachment = message.voice
        file_ext = "ogg"
    elif message.video_note:
        attachment = message.video_note
        file_ext = "mp4"
    else:
        await status_message.edit_text("Tipo de mensagem não suportado.")
        return

    _audio_file = await attachment.get_file()

    file_path = f"/tmp/{_audio_file.file_id}.{file_ext}"
    await _audio_file.download_to_drive(file_path)

    transcribed = GroqProvider().transcribe_audio(file_path)

    if not transcribed:
        await status_message.edit_text("Não foi possível transcrever o áudio.")
        os.remove(file_path)
        return

    final_message = f"*{user.first_name}* disse: {transcribed}"

    os.remove(file_path)
    await status_message.edit_text(final_message, parse_mode="markdown")

import io
import sys
from html import escape
from pathlib import Path

import requests
from PIL import Image

sys.path.append(str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import CallbackContext

from shared import reply_text_safe, reply_video_safe
from telegrambot.handlers.utils import get_media_from_link


async def get_media(update: Update, context: CallbackContext):
    link = update.message.text
    user = update.effective_user

    status_message = await reply_text_safe(
        update.message,
        "Baixando mídia...",
        message_type="status",
        save_to_db=False,
    )

    try:
        media = get_media_from_link(link)
    except Exception as e:
        await status_message.edit_text(f"❌ Erro ao baixar mídia: {str(e)}")
        return

    if not media:
        await status_message.edit_text("❌ Erro: mídia não encontrada")
        return

    video_buffer = media[0]
    video_buffer.seek(0)  # Garante que o buffer está no início

    caption = media[1] if media[1] else "Sem título"
    thumbnail_url = media[2]
    user_mention = user.mention_html() if user else "Unknown"
    final_caption = (
        f"<b>{escape(caption)}</b>\n\n"
        f'<a href="{escape(link)}">🔗 Link</a>\n'
        f" Enviado por {user_mention}"
    )

    await status_message.edit_text("📤 Enviando vídeo...")

    thumb_buffer = None
    if thumbnail_url:
        try:
            thumb_response = requests.get(thumbnail_url, timeout=10)
            if thumb_response.status_code == 200 and thumb_response.content:
                img = Image.open(io.BytesIO(thumb_response.content))
                jpeg_buffer = io.BytesIO()
                img.convert("RGB").save(jpeg_buffer, format="JPEG", quality=85)
                thumb_buffer = jpeg_buffer
                thumb_buffer.name = "thumb.jpg"
                thumb_buffer.seek(0)
        except Exception:
            pass

    try:
        if thumb_buffer and thumb_buffer.getbuffer().nbytes > 0:
            await reply_video_safe(
                update.message,
                video=video_buffer,
                caption=final_caption,
                thumbnail=thumb_buffer,
                parse_mode="HTML",
                message_type="media",
            )
            thumb_buffer.close()
        else:
            await reply_video_safe(
                update.message,
                video=video_buffer,
                caption=final_caption,
                parse_mode="HTML",
                message_type="media",
            )
        video_buffer.close()
        await status_message.delete()
    except Exception as e:
        await status_message.edit_text(
            f"❌ Erro ao enviar o vídeo: {str(e)}"
        )
        video_buffer.close()
        if thumb_buffer:
            thumb_buffer.close()
        return

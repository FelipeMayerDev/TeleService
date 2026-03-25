import io
import sys
from pathlib import Path

import requests
from PIL import Image

sys.path.append(str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import CallbackContext
from telegram.helpers import escape_markdown

from shared import reply_text_safe, reply_video_safe
from telegrambot.handlers.utils import get_media_from_link


async def get_media(update: Update, context: CallbackContext):
    link = update.message.text
    user = update.effective_user

    try:
        media = get_media_from_link(link)
    except Exception as e:
        await reply_text_safe(
            update.message,
            "❌ Erro ao obter informações do link.",
            message_type="error",
            save_to_db=False,
        )
        return

    if not media:
        return

    status_message = await reply_text_safe(
        update.message,
        "Pegando media do link...",
        message_type="status",
        save_to_db=False,
    )
    caption = media[1] or "Sem título"
    thumbnail_url = media[2]
    user_mention = user.mention_markdown() if user else "Unknown"
    final_caption = f"*{escape_markdown(caption)}*\n\nLink: `{escape_markdown(link)}`\n Enviado por {user_mention}"

    try:
        await reply_video_safe(
            update.message,
            video=media[0],
            caption=final_caption,
            thumbnail=thumbnail_url,
            parse_mode="markdown",
            message_type="media",
        )
        await status_message.delete()
    except Exception:
        await status_message.edit_text("⏳ Deu ruim, vamos ter que baixar o vídeo...")
        video_buffer = io.BytesIO()
        thumb_buffer = None

        try:
            response = requests.get(media[0], stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            chunk_size = 1024 * 1024
            last_update = 0

            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    video_buffer.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        progress = int((downloaded / total_size) * 100)
                        current_mb = downloaded / 1024 / 1024
                        total_mb = total_size / 1024 / 1024

                        if progress - last_update >= 10 or progress == 100:
                            progress_bar = "█" * (progress // 10) + "░" * (
                                10 - progress // 10
                            )
                            await status_message.edit_text(
                                f"⏳ Baixando... {progress}%\n"
                                f"[{progress_bar}]\n"
                                f"📊 {current_mb:.1f}MB / {total_mb:.1f}MB"
                            )
                            last_update = progress

            video_buffer.name = "video.mp4"
            video_buffer.seek(0)

            if video_buffer.getbuffer().nbytes == 0:
                await status_message.edit_text("❌ Erro: buffer de vídeo vazio")
                video_buffer.close()
                await status_message.delete()
                return

            if video_buffer.getbuffer().nbytes < 1024:
                await status_message.edit_text(
                    "❌ Erro: vídeo muito pequeno ou corrompido"
                )
                video_buffer.close()
                await status_message.delete()
                return

        except Exception as e:
            await status_message.edit_text(f"❌ Erro ao baixar o vídeo: {str(e)}")
            video_buffer.close()
            await status_message.delete()
            return

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
            await status_message.edit_text("📤 Enviando vídeo...")
            if thumb_buffer and thumb_buffer.getbuffer().nbytes > 0:
                await reply_video_safe(
                    update.message,
                    video=video_buffer,
                    caption=final_caption,
                    thumbnail=thumb_buffer,
                    parse_mode="markdown",
                    message_type="media",
                )
                thumb_buffer.close()
            else:
                await reply_video_safe(
                    update.message,
                    video=video_buffer,
                    caption=final_caption,
                    parse_mode="markdown",
                    message_type="media",
                )
            video_buffer.close()
            await status_message.delete()
        except Exception as e:
            await status_message.edit_text(
                f"❌ Erro ao enviar o vídeo baixado: {str(e)}"
            )
            video_buffer.close()
            if thumb_buffer:
                thumb_buffer.close()
            await status_message.delete()
            return

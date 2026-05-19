import os
import io
import sys
import logging
import requests as req

from PIL import Image
from telegram import Update
from telegram.ext import ContextTypes

sys.path.insert(0, "/app")
from shared import reply_text_safe

from telegram.ext import filters as tg_filters

log = logging.getLogger(__name__)

FAKEGROK_TOKEN = os.getenv("FAKEGROK_TOKEN", "")
STICKER_SET_NAME = "fakegrok_pack_by_fakegrokbot"
STICKER_SET_TITLE = "FakeGrok Pack"
TELEGRAM_API = "https://api.telegram.org"


class StickerPhotoFilter(tg_filters.MessageFilter):
    """Filter para mensagens de foto com caption /sticker."""
    def filter(self, message):
        if not message.photo:
            return False
        caption = (message.caption or "").strip().lower()
        return caption.startswith("/sticker")


sticker_photo_filter = StickerPhotoFilter()


class StickerCmdFilter(tg_filters.MessageFilter):
    """Filter para comandos /sticker em texto."""
    def filter(self, message):
        if not message.text:
            return False
        return message.text.strip().lower().startswith("/sticker")


sticker_cmd_filter = StickerCmdFilter()


def _download_image(img_bytes_or_url: bytes | str) -> bytes | None:
    """Baixa imagem de bytes ou URL e retorna PNG bytes pronto pra sticker."""
    try:
        if isinstance(img_bytes_or_url, str):
            # URL
            resp = req.get(img_bytes_or_url, timeout=15)
            resp.raise_for_status()
            raw = resp.content
        else:
            raw = img_bytes_or_url

        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        # Cover-resize: scale to fill 512x512, crop excess (handles small & large)
        w, h = img.size
        ratio = max(512 / w, 512 / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img.size
        left = (w - 512) // 2
        top = (h - 512) // 2
        img = img.crop((left, top, left + 512, top + 512))

        out = io.BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        return out.getvalue()
    except Exception as e:
        log.error(f"Image processing error: {e}")
        return None


def _upload_sticker(png_bytes: bytes, user_id: int, emoji: str, chat_id: int) -> str | None:
    """Envia sticker pro pack do FakeGrok. Retorna link ou None."""
    url = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/addStickerToSet"
    files = {"png_sticker": ("sticker.png", png_bytes, "image/png")}
    data = {"user_id": str(user_id), "name": STICKER_SET_NAME, "emojis": emoji}

    resp = req.post(url, files=files, data=data, timeout=15).json()

    if resp.get("ok"):
        return f"https://t.me/addstickers/{STICKER_SET_NAME}"

    # Pack nao existe? Criar
    url2 = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/createNewStickerSet"
    files2 = {"png_sticker": ("sticker.png", png_bytes, "image/png")}
    data2 = {
        "user_id": str(user_id),
        "name": STICKER_SET_NAME,
        "title": STICKER_SET_TITLE,
        "emojis": emoji,
    }

    resp2 = req.post(url2, files=files2, data=data2, timeout=15).json()
    if resp2.get("ok"):
        return f"https://t.me/addstickers/{STICKER_SET_NAME}"

    return f"Erro: {resp.get('description', resp2.get('description', 'desconhecido'))}"


async def sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cria sticker a partir de imagem anexada, respondida, ou URL."""
    user = update.effective_user
    message = update.message
    user_id = user.id if user else 1

    png_bytes = None

    try:
        # 1. Imagem respondida (reply)
        if message.reply_to_message:
            replied = message.reply_to_message
            if replied.photo:
                photo = replied.photo[-1]
                f = await photo.get_file()
                buf = io.BytesIO()
                await f.download_to_memory(buf)
                png_bytes = _download_image(buf.getvalue())
            elif replied.sticker and not replied.sticker.is_animated and not replied.sticker.is_video:
                sf = await replied.sticker.get_file()
                sbuf = io.BytesIO()
                await sf.download_to_memory(sbuf)
                png_bytes = _download_image(sbuf.getvalue())
            else:
                text = replied.text or replied.caption or ""
                url = _extract_url(text)
                if url:
                    png_bytes = _download_image(url)
                else:
                    await reply_text_safe(
                        message, "Responde a uma imagem, sticker ou URL de imagem.", 
                        message_type="error", save_to_db=False,
                    )
                    return
        # 2. Foto na mesma mensagem
        elif message.photo:
            log.info(f"Photo received: sizes={[p.file_size for p in message.photo]}")
            photo = message.photo[-1]
            f = await photo.get_file()
            buf = io.BytesIO()
            await f.download_to_memory(buf)
            png_bytes = _download_image(buf.getvalue())
        # 3. URL no texto do comando ou caption
        else:
            text_parts = []
            if context.args:
                text_parts.extend(context.args)
            if message.caption:
                text_parts.append(message.caption)
            text = " ".join(text_parts)
            url = _extract_url(text)
            if url:
                png_bytes = _download_image(url)
            else:
                await reply_text_safe(
                    message,
                    "Usa assim:\n• /sticker + imagem\n• /sticker + URL\n• Responde a uma imagem com /sticker",
                    message_type="error",
                    save_to_db=False,
                )
                return

        if not png_bytes:
            await reply_text_safe(
                message, "❌ Não consegui processar a imagem.", 
                message_type="error", save_to_db=False,
            )
            return

        emoji = _pick_emoji(context.args)

        status = await reply_text_safe(
            message, "Criando sticker... 🎨", message_type="status", save_to_db=False,
        )

        result = _upload_sticker(png_bytes, user_id, emoji, message.chat_id)

        if result and not result.startswith("Erro"):
            await status.edit_text(f"✅ Sticker adicionado!\n📁 [FakeGrok Pack]({result}) {emoji}", parse_mode="markdown")
        else:
            await status.edit_text(f"❌ {result}")
    except Exception as e:
        log.error(f"sticker handler error: {e}", exc_info=True)
        await reply_text_safe(
            message, f"❌ Erro: {str(e)}", message_type="error", save_to_db=False,
        )


def _delete_sticker_from_set(sticker_file_id: str) -> str:
    """Deleta um sticker do pack via file_id."""
    url = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/deleteStickerFromSet"
    data = {"sticker": sticker_file_id}
    resp = req.post(url, data=data, timeout=15).json()
    if resp.get("ok"):
        return "✅ Sticker removido do pack!"
    return f"❌ Erro: {resp.get('description', 'desconhecido')}"


async def delete_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove sticker do pack. Responde a um sticker com /delsticker."""
    message = update.message

    if not message.reply_to_message or not message.reply_to_message.sticker:
        await reply_text_safe(
            message, "Responde a um sticker com /delsticker pra remover do pack.",
            message_type="error", save_to_db=False,
        )
        return

    sticker = message.reply_to_message.sticker
    if not sticker.file_id:
        await reply_text_safe(
            message, "❌ Não consegui identificar o sticker.",
            message_type="error", save_to_db=False,
        )
        return

    status = await reply_text_safe(
        message, "Removendo sticker... 🗑️", message_type="status", save_to_db=False,
    )

    result = _delete_sticker_from_set(sticker.file_id)
    await status.edit_text(result)


def _extract_url(text: str) -> str | None:
    """Extrai URL de um texto."""
    import re
    match = re.search(r'https?://\S+', text)
    return match.group(0) if match else None


def _pick_emoji(args: list | None) -> str:
    """Pega emoji dos argumentos ou usa padrão."""
    if not args:
        return "😂"
    text = " ".join(args)
    for c in text:
        # Verifica se é emoji
        if ord(c) > 0x2600 and ord(c) < 0x27BF or ord(c) > 0x1F600:
            return c
    return "😂"

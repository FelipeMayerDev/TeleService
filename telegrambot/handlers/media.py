import io
import sys
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlunparse

import requests
from PIL import Image

sys.path.append(str(Path(__file__).parent.parent))

from telegram import Update
from telegram.ext import CallbackContext

from domain.models import MediaShare
from shared import reply_photo_safe, reply_text_safe, reply_video_safe
from telegrambot.handlers.commands import get_text_content
from telegrambot.handlers.utils import get_media_from_link, probe_media, youtube_too_long


def _normalize_link(url: str) -> str:
    # ponytail: descarta query/fragment/trailing slash e o prefixo www. — mesmo
    # vídeo compartilhado com/sem www ou tracking params vira a mesma chave.
    # Path NÃO é lowercased: YouTube IDs são case-sensitive.
    p = urlparse(url)
    host = p.netloc[4:] if p.netloc.startswith("www.") else p.netloc
    path = p.path.rstrip("/")
    # /watch sem o ?v= colapsaria TODOS os vídeos do YouTube numa chave só —
    # move o ID da query pro path.
    if host.endswith("youtube.com") and path == "/watch" and p.query:
        qs = parse_qs(p.query)
        if qs.get("v"):
            path = f"/watch/{qs['v'][0]}"
    return urlunparse((p.scheme, host, path, "", "", ""))


def _join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " e " + names[-1]


def _senders_for_link(link: str, chat_id: int, current: str) -> list[str]:
    """Quem já enviou este link no chat (cronológico, dedup) + o atual no final."""
    norm = _normalize_link(link)
    senders: list[str] = []
    try:
        query = (
            MediaShare
            .select(MediaShare.sender)
            .where((MediaShare.link == norm) & (MediaShare.chat_id == chat_id))
            .order_by(MediaShare.created_at.asc())
        )
        for row in query:
            if row.sender not in senders:
                senders.append(row.sender)
    except Exception:
        pass
    if current not in senders:
        senders.append(current)
    return senders


def _record_share(link: str, sender: str, chat_id: int) -> None:
    try:
        MediaShare.create(link=_normalize_link(link), sender=sender, chat_id=chat_id)
    except Exception:
        pass


async def get_media(update: Update, context: CallbackContext):
    link = update.message.text
    user = update.effective_user

    status_message = await reply_text_safe(
        update.message, "Baixando...", message_type="status", save_to_db=False,
    )
    user_mention = user.mention_html() if user else "Unknown"
    user_name = (user.full_name or user.first_name or "Unknown") if user else "Unknown"
    chat_id = update.message.chat_id

    # ponytail: rastreia quem já mandou este link. Repetido (≥2 pessoas) →
    # "enviado por X e Y" + (amanhã é a vez de quem?)
    senders = _senders_for_link(link, chat_id, user_name)
    _record_share(link, user_name, chat_id)
    if len(senders) >= 2:
        sent_by = (
            f" enviado por {escape(_join_names(senders))}"
            f"\n\n<i>(amanhã é a vez de quem?)</i>"
        )
    else:
        sent_by = f" Enviado por {user_mention}"

    # 1. Tem mídia? Probe primeiro — vídeo nunca deve cair em texto
    if youtube_too_long(link):
        await status_message.edit_text(
            "❌ Vídeos do YouTube são aceitos só até 3 minutos. O /resume resume vídeo longo."
        )
        return
    if probe_media(link):
        try:
            buffer, title, thumbnail_url, media_type = get_media_from_link(link)
        except Exception as e:
            await status_message.edit_text(f"❌ Erro ao baixar: {e}")
            return

        buffer.seek(0)
        caption = (
            f"<b>{escape(title or 'Sem título')}</b>\n\n"
            f'<a href="{escape(link)}">🔗 Link</a>\n'
            f"{sent_by}"
        )

        # --- Imagem ---
        if media_type == "image":
            await status_message.edit_text("📤 Enviando imagem...")
            try:
                await reply_photo_safe(
                    update.message, photo=buffer, caption=caption,
                    parse_mode="HTML", message_type="media",
                )
                await status_message.delete()
            except Exception as e:
                await status_message.edit_text(f"❌ Erro ao enviar imagem: {e}")
            finally:
                buffer.close()
            return

        # --- Vídeo ---
        await status_message.edit_text("📤 Enviando vídeo...")
        thumb_buffer = None
        if thumbnail_url:
            try:
                r = requests.get(thumbnail_url, timeout=10)
                if r.status_code == 200 and r.content:
                    img = Image.open(io.BytesIO(r.content))
                    tb = io.BytesIO()
                    img.convert("RGB").save(tb, format="JPEG", quality=85)
                    thumb_buffer = tb
                    thumb_buffer.name = "thumb.jpg"
                    thumb_buffer.seek(0)
            except Exception:
                pass

        try:
            await reply_video_safe(
                update.message, video=buffer, caption=caption,
                thumbnail=thumb_buffer, parse_mode="HTML", message_type="media",
            )
            await status_message.delete()
        except Exception as e:
            await status_message.edit_text(f"❌ Erro ao enviar vídeo: {e}")
        finally:
            buffer.close()
            if thumb_buffer:
                thumb_buffer.close()
        return

    # 2. Sem mídia → extrai texto + imagens (tweet com foto, artigo, etc)
    text_content = get_text_content(link)
    if not text_content:
        await status_message.edit_text("❌ Nenhum conteúdo encontrado")
        return

    text, title, images = text_content

    # Tem imagem (tweet com foto) → envia como photo + texto no caption
    if images:
        try:
            img_resp = requests.get(images[0], timeout=15)
            if img_resp.status_code == 200 and img_resp.content:
                img_buf = io.BytesIO(img_resp.content)
                img_buf.seek(0)
                safe_text = escape(text)
                if len(safe_text) > 800:
                    safe_text = safe_text[:800].rstrip() + " […]"
                cap = (
                    f"<b>{escape(title)}</b>\n\n"
                    f"{safe_text}\n\n"
                    f'<a href="{escape(link)}">🔗 Link</a>\n'
                    f"{sent_by}"
                )
                await status_message.delete()
                await reply_photo_safe(
                    update.message, photo=img_buf, caption=cap,
                    parse_mode="HTML", message_type="media",
                )
                img_buf.close()
                return
        except Exception:
            pass  # download da imagem falhou → cai pra texto

    # Sem imagem → texto puro
    header = (
        f"<b>{escape(title)}</b>\n\n"
        f'<a href="{escape(link)}">🔗 Link</a>\n'
        f"{sent_by}\n\n"
    )
    body = escape(text)
    budget = 4096 - len(header) - 20
    if len(body) > budget:
        body = body[:budget].rstrip() + " […]"

    await status_message.delete()
    await reply_text_safe(
        update.message, f"{header}<i>{body}</i>",
        parse_mode="HTML", message_type="text",
    )

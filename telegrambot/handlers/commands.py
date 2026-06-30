import logging

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import requests
from bs4 import BeautifulSoup

from domain.services import MessageService
from providers.groq import GroqProvider
from providers.serp import SerpProvider
from providers.zai import ZAIProvider
from shared import reply_photo_safe, reply_text_safe
from telegrambot.handlers.utils import is_valid_link, transcribe_audio

logger = logging.getLogger(__name__)
message_service = MessageService()


def get_text_content(url: str) -> tuple[str, str] | None:
    """Baixa o conteúdo de texto de um site e retorna (texto, título)."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Tenta pegar o título
        title = soup.find('title')
        title = title.get_text().strip() if title else url

        # Remove scripts e estilos
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()

        # Pega o texto principal
        text = soup.get_text(separator=' ', strip=True)

        # Limpa o texto
        text = ' '.join(text.split())

        if len(text) < 100:
            return None

        return (text, title)

    except Exception as e:
        logger.error(f"Error getting text content: {e}")
        return None


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message

    if not user or (user.username or "").lower() != "fockytheguy":
        return

    replied_message = message.reply_to_message if message else None
    if not replied_message:
        await reply_text_safe(
            message,
            "Responda uma mensagem minha com /delete.",
            message_type="error",
            save_to_db=False,
        )
        return

    if not replied_message.from_user or replied_message.from_user.id != context.bot.id:
        await reply_text_safe(
            message,
            "Só posso apagar mensagens que eu mesmo mandei.",
            message_type="error",
            save_to_db=False,
        )
        return

    try:
        await replied_message.delete()
    except Exception as e:
        logger.error(f"Error deleting bot message: {e}")
        await reply_text_safe(
            message,
            "Não consegui apagar essa mensagem.",
            message_type="error",
            save_to_db=False,
        )


async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_text_safe(
        update.message,
        """📚 *Comandos do TeleService*

📥 *Mídia:*
• Envie links de vídeo/áudio e eu baixo automaticamente
• Suporta: YouTube, Instagram (reels/reel), TikTok, Twitter/X, Facebook, etc.
• Aceita links normais, fóruns, artigos, tweets...

📝 *Resumo:*
• `/resume <link>` - Resuma qualquer conteúdo (vídeo, áudio, artigo, tweet)
  - Baixa e transcreve vídeos/áudios
  - Extrai texto de artigos/blogs
  - Máximo 15 minutos para mídia
• `/tldr <número>` - Resuma as últimas N mensagens (máx 300)

🔍 *Busca:*
• `/image <termo>` - Busca imagens no Google

👥 *Discord:*
• `/online_agora` - Lista usuários online nos canais de voz

🎨 *Stickers:*
• `/sticker` - Cria sticker de foto/GIF/video (envie com a mídia)

⚙️ *Admin (só @fockytheguy):*
• `/delete` - Apaga mensagem do bot
• `/delsticker` - Deleta sticker do pack
• `/falar <msg>` - Manda mensagem no chat principal

🐌 *Notas:*
• Pooling da Steam pela API é lento (ver doc oficial)
• Vídeos com restrição de idade podem não funcionar

❓ *Erro ao baixar mídia?*
• Geralmente é restrição de idade ou link expirado
• Procure o @fockytheguy para ajuste""",
        parse_mode="markdown",
        message_type="faq",
    )


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    link = update.message.text.split(" ", 1)[1]

    message = await reply_text_safe(
        update.message,
        "Analisando link e extraindo conteúdo...",
        message_type="status",
        save_to_db=False,
    )

    # Tenta primeiro como vídeo/áudio
    is_media = False
    try:
        if is_valid_link(link):
            is_media = True
            content = transcribe_audio(link, "base", "")
        else:
            content = None
    except Exception:
        content = None

    # Se não for mídia ou falhou, tenta baixar texto
    if not content or not content[0]:
        text_content = get_text_content(link)
        if text_content:
            text, title = text_content
            content = (text, title, "Texto")
            is_media = False
        else:
            await message.edit_text(
                "Não foi possível obter conteúdo deste link (vídeo, áudio ou texto).",
            )
            return

    resume = ZAIProvider().chat(
        f"<system_prompt>Resuma esse conteúdo em no máximo 150 palavras, não use emojis, responda sempre em português pt-br</system_prompt><input>title: {content[1]}\ncontent: {content[0]}</input>"
    )

    if is_media:
        source_text = f"Transcrição de {content[2]}"
    else:
        source_text = "Texto do site"

    final_text = f"""{user.mention_markdown()} segue o seu resumo de *{content[1]}* :
        -_{resume}_

        - Fonte: *{source_text}*
        """
    await message.edit_text(final_text, parse_mode="markdown")

    await reply_text_safe(
        update.message,
        final_text,
        parse_mode="markdown",
        message_type="video_resume",
    )


async def search_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    query = update.message.text.split(" ", 1)[1]
    message = await reply_text_safe(
        update.message,
        f"{user.mention_markdown()} pediu fotos de _{query}_",
        parse_mode="markdown",
        message_type="status",
        save_to_db=False,
    )
    image = SerpProvider().search_image(query, use_cache=False)
    if not image:
        await message.edit_text(
            f"Não foi possível encontrar imagens para '{query}'. Tente novamente com outro termo."
        )
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Solicitar outra", callback_data=f"search_image:{query}"
                )
            ]
        ]
    )
    await reply_photo_safe(
        update.message,
        photo=image,
        caption=f"{query} - Solicitada por {user.mention_markdown()}",
        parse_mode="markdown",
        message_type="search_image",
        reply_markup=keyboard,
    )
    await message.delete()


async def search_image_callback(update: Update, context) -> None:
    query = update.callback_query.data.split(":", 1)[1]
    user = update.effective_user
    await update.callback_query.answer("Buscando outra imagem...")
    image = SerpProvider().search_image(query, use_cache=False)
    if not image:
        await reply_text_safe(
            update.callback_query.message,
            f"Não foi possível encontrar imagens para '{query}'. Tente novamente com outro termo.",
            message_type="error",
        )
        return
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Solicitar outra", callback_data=f"search_image:{query}"
                )
            ]
        ]
    )
    await reply_photo_safe(
        update.callback_query.message,
        photo=image,
        caption=f"{query} - Solicitada por {user.mention_markdown()}",
        parse_mode="markdown",
        message_type="search_image",
        reply_markup=keyboard,
    )


async def tldr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    if not context.args:
        await reply_text_safe(
            message,
            "Use /tldr <número> (máximo 300).",
            message_type="error",
            save_to_db=False,
        )
        return

    try:
        limit = int(context.args[0])
    except ValueError:
        await reply_text_safe(
            message,
            "O número precisa ser válido. Exemplo: /tldr 50",
            message_type="error",
            save_to_db=False,
        )
        return

    if limit < 1:
        await reply_text_safe(
            message,
            "O número precisa ser maior que zero.",
            message_type="error",
            save_to_db=False,
        )
        return

    limit = min(limit, 300)
    status_message = await reply_text_safe(
        message,
        f"Resumindo as últimas {limit} mensagens...",
        message_type="status",
        save_to_db=False,
    )

    messages = message_service.get_last_messages(message.chat_id, limit=limit + 1)
    messages = [m for m in messages if m.platform_message_id != message.message_id][:limit]

    if not messages:
        await status_message.edit_text("Não encontrei mensagens suficientes pra resumir.")
        return

    transcript_lines = []
    for item in reversed(messages):
        sender = item.from_user or "Unknown"
        text = (item.text or "").strip()
        if not text:
            continue
        transcript_lines.append(f"{sender}: {text}")

    if not transcript_lines:
        await status_message.edit_text("Não encontrei texto útil pra resumir.")
        return

    prompt = (
        "Faça um resumo geral, em português brasileiro, do que foi falado "
        "nestas mensagens de um grupo. Destaque os principais assuntos, decisões, "
        "piadas/contextos recorrentes e qualquer pendência. Seja direto.\n\n"
        + "\n".join(transcript_lines)
    )

    try:
        summary = GroqProvider().chat(prompt).strip()
    except Exception as e:
        logger.error(f"Error generating TLDR with Groq: {e}", exc_info=True)
        await status_message.edit_text("Não consegui gerar o resumo agora.")
        return

    if len(summary) > 4000:
        summary = summary[:3997] + "..."

    try:
        await status_message.edit_text(summary, parse_mode="HTML")
    except Exception:
        await status_message.edit_text(summary)


async def online_agora(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista os usuários online no Discord com seus status."""
    import os
    import asyncio
    import discord

    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

    if not DISCORD_TOKEN:
        await reply_text_safe(
            update.message,
            "❌ DISCORD_TOKEN não configurado.",
            message_type="error",
            save_to_db=False,
        )
        return

    status_message = await reply_text_safe(
        update.message,
        "🔍 Buscando usuários online no Discord...",
        message_type="status",
        save_to_db=False,
    )

    intents = discord.Intents.default()
    intents.voice_states = True
    intents.members = True

    client = discord.Client(intents=intents)

    online_text = None

    @client.event
    async def on_ready():
        nonlocal online_text
        logger.info(f"Connected to Discord as {client.user}")

        # Encontrar o canal de voz com membros
        voice_channel = None
        for guild in client.guilds:
            for vc in guild.voice_channels:
                if vc.members:
                    voice_channel = vc
                    break
            if voice_channel:
                break

        if not voice_channel:
            online_text = "❌ Não há ninguém online nos canais de voz do Discord."
        else:
            lines = [f"📢 **Canal: {voice_channel.name}**\n"]
            lines.append("Usuários online:\n")

            for member in sorted(voice_channel.members, key=lambda m: m.display_name.lower()):
                if member.bot:
                    continue

                voice = member.voice
                if not voice:
                    continue

                status_icon = ""
                if voice.self_stream:
                    status_icon = "🔴"  # Streaming
                elif voice.self_deaf:
                    status_icon = "🔇"  # Deafened
                elif voice.self_mute:
                    status_icon = "🎤"  # Muted

                status_text = f" {status_icon}" if status_icon else ""
                lines.append(f"- {member.display_name}{status_text}")

            online_text = "".join(lines)

        await client.close()

    try:
        await asyncio.wait_for(client.start(DISCORD_TOKEN), timeout=10)
        await asyncio.sleep(2)  # Dar tempo para o on_ready executar
        await client.close()
    except asyncio.TimeoutError:
        await client.close()
        online_text = "⏱️ Timeout ao conectar ao Discord."
    except Exception as e:
        logger.error(f"Error connecting to Discord: {e}")
        online_text = f"❌ Erro ao conectar ao Discord: {str(e)}"

    if online_text:
        await status_message.edit_text(online_text)


async def falar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manda uma mensagem no chat principal. Apenas @fockytheguy pode usar."""
    import os
    from telegram import Bot

    user = update.effective_user
    message = update.effective_message

    if not user or (user.username or "").lower() != "fockytheguy":
        return

    if not message:
        return

    chat_id = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
    if not chat_id:
        await message.reply_text("TELEGRAM_CHAT_ID não configurado.")
        return

    if not context.args:
        await message.reply_text("Use /falar <mensagem>")
        return

    text = " ".join(context.args)

    try:
        bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
        await bot.send_message(chat_id=chat_id, text=text)

        # Salvar no banco também
        from shared import reply_text_safe
        await reply_text_safe(
            message,
            f"✅ Mensagem enviada para o chat {chat_id}",
            message_type="falar",
            save_to_db=False,
        )
    except Exception as e:
        await message.reply_text(f"Erro ao enviar mensagem: {e}")

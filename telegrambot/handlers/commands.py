from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from providers.serp import SerpProvider
from providers.zai import ZAIProvider
from shared import reply_photo_safe, reply_text_safe
from telegrambot.handlers.utils import is_valid_link, transcribe_audio


async def faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply_text_safe(
        update.message,
        """📚 *FAQ*

🐌 *Pooling da Steam pela API é lento*
• Pode ler na documentação oficial
• Não possui webhook (não é de graça)

❓ *Bot não pegou o link da sua mídia?*
• Geralmente é restrição de idade
• Solução: Envie seu cookie pro Focky""",
        parse_mode="markdown",
        message_type="faq",
    )


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    link = update.message.text.split(" ", 1)[1]
    if not is_valid_link(link):
        return await reply_text_safe(
            update.message,
            "Video inválido.. lembrando que o limite é de 15 minutos!",
            message_type="error",
            save_to_db=False,
        )
    message = await reply_text_safe(
        update.message,
        "Iniciando resumo.. isso pode demorar...",
        message_type="status",
        save_to_db=False,
    )
    content = transcribe_audio(link, "base", "")

    if not content or not content[0]:
        await message.edit_text(
            "Não foi possível obter legendas para este vídeo.",
            reply_markup=ForceReply(selective=True),
        )
        return

    resume = ZAIProvider().chat(
        f"<system_prompt>Resuma esse conteúdo de um vídeo do youtube em no máximo 150 palavras, não use emojis, responda sempre em português pt-br</system_prompt><input>title: {content[1]}\ncontent: {content[0]}</input>"
    )
    final_text = f"""{user.mention_markdown()} segue o seu resumo do video *{content[1]}* :
        -_{resume}_

        - Transcrito pelo *{content[2].value}*
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
    image = SerpProvider().search_image(query)
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
    image = SerpProvider().search_image(query)
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

    await reply_text_safe(
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
        await reply_text_safe(
            update.message,
            online_text,
            message_type="online_status",
        )

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from providers.serp import SerpProvider
from providers.zai import ZAIProvider
from telegrambot.handlers.utils import is_valid_link, transcribe_audio


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    link = update.message.text.split(" ", 1)[1]
    if not is_valid_link(link):
        return await update.message.reply_text(
            "Video inválido.. lembrando que o limite é de 15 minutos!"
        )
    message = await update.message.reply_text("Iniciando resumo.. isso pode demorar...")
    content = transcribe_audio(link, "base", "")

    if not content or not content[0]:
        await message.edit_text(
            f"Não foi possível obter legendas para este vídeo.",
            reply_markup=ForceReply(selective=True),
        )
        return

    resume = ZAIProvider().chat(
        f"<system_prompt>Resuma esse conteúdo de um vídeo do youtube em no máximo 150 palavras, não use emojis, responda sempre em português pt-br</system_prompt><input>title: {content[1]}\ncontent: {content[0]}</input>"
    )
    await message.edit_text(
        f"""{user.mention_markdown()} segue o seu resumo do video *{content[1]}* :
        -_{resume}_

        - Transcrito pelo *{content[2].value}*
        """,
        parse_mode="markdown",
    )


async def search_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    query = update.message.text.split(" ", 1)[1]
    message = await update.message.reply_text(
        f"{user.mention_markdown()} pediu fotos de _{query}_",
        parse_mode="markdown",
    )
    image = SerpProvider().search_image(query)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Solicitar outra", callback_data=f"search_image:{query}"
                )
            ]
        ]
    )
    await update.message.reply_photo(
        photo=image,
        caption=f"{query} - Solicitada por {user.mention_markdown()}",
        parse_mode="markdown",
        reply_markup=keyboard,
    )
    await message.delete()


async def search_image_callback(update: Update, context) -> None:
    query = update.callback_query.data.split(":", 1)[1]
    user = update.effective_user
    await update.callback_query.answer("Buscando outra imagem...")
    image = SerpProvider().search_image(query)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Solicitar outra", callback_data=f"search_image:{query}"
                )
            ]
        ]
    )
    await update.callback_query.message.reply_photo(
        photo=image,
        caption=f"{query} - Solicitada por {user.mention_markdown()}",
        parse_mode="markdown",
        reply_markup=keyboard,
    )

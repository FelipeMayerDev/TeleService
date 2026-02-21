import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from telegram import Update
from telegram.ext import CallbackContext, filters

from database.managers import MessageManager
from providers.zai import ZAIProvider
from telegrambot.handlers.media import get_media
from telegrambot.handlers.utils import is_link, is_allowed_link



async def text_handler(update: Update, context: CallbackContext):
    MessageManager.add_message(
        telegram_message_id=update.message.message_id,
        text=update.message.text,
        chat_id=update.message.chat_id,
        from_user=update.message.from_user.username,
        to_user=update.message.reply_to_message.from_user.username
        if update.message.reply_to_message
        else None,
        reply_to_message_id=update.message.reply_to_message.message_id
        if update.message.reply_to_message
        else None,
    )
    if is_allowed_link(update.message.text):
        await get_media(update, context)


async def bot_mentioned(update: Update, context: CallbackContext):
    if not "@fimosin_bot" in update.message.text:
        return

    await text_handler(update, context)
    # Verificar se é um reply (mencionado) ou se é uma mensagem simples
    # caso seja reply, enviar mensagem original e mensagem do reply como contexto
    if update.message.reply_to_message:
        reply_message = update.message.reply_to_message.text
        reply_message_user = update.message.reply_to_message.from_user.full_name
        context_message = update.message.text
        context_message_user = update.message.from_user.full_name
        full_prompt = f"{reply_message_user}: {reply_message}\n{context_message_user}: {context_message}"
        ia_response = ZAIProvider().chat(full_prompt)
        await update.message.reply_text(ia_response)
    else:
        ia_response = ZAIProvider().chat(update.message.text)
        await update.message.reply_text(ia_response)

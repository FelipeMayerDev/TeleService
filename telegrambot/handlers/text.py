import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from telegram import Update
from telegram.ext import CallbackContext, filters

from database.managers import MessageManager
from providers.zai import ZAIProvider
from telegrambot.handlers.media import get_media
from telegrambot.handlers.utils import is_link, is_allowed_link


def is_bot_mentioned(update: Update) -> bool:
    """Check if the bot @fimosin_bot is mentioned in the message."""
    if not update.message or not update.message.text:
        return False

    # Check text first for simple mentions
    if "@fimosin_bot" in update.message.text:
        return True

    # Check entities for proper mentions
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mention_text = update.message.text[
                    entity.offset : entity.offset + entity.length
                ]
                if mention_text == "@fimosin_bot":
                    return True
    return False


async def text_handler(update: Update, context: CallbackContext):
    try:
        from_user = None
        if update.message.from_user:
            from_user = update.message.from_user.username or update.message.from_user.first_name

        reply_to_message_id = None
        reply_text = None
        to_user = None
        if update.message.reply_to_message:
            reply_to_message_id = update.message.reply_to_message.message_id
            reply_text = update.message.reply_to_message.text
            if update.message.reply_to_message.from_user:
                to_user = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name

        MessageManager.add_message(
            telegram_message_id=update.message.message_id,
            text=update.message.text,
            chat_id=update.message.chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
            message_type="text",
        )
    except Exception as e:
        print(f"Error logging text message: {e}")

    if is_allowed_link(update.message.text):
        await get_media(update, context)

    # Check if bot is mentioned
    if is_bot_mentioned(update):
        # Verificar se é um reply (mencionado) ou se é uma mensagem simples
        # caso seja reply, enviar mensagem original e mensagem do reply como contexto
        if update.message.reply_to_message:
            reply_message = update.message.reply_to_message.text
            reply_message_user = update.message.reply_to_message.from_user.full_name
            context_message = update.message.text
            context_message_user = update.message.from_user.full_name
            full_prompt = f"{reply_message_user}: {reply_message}\n{context_message_user}: {context_message}"
            ia_response = ZAIProvider().chat(full_prompt)
            await update.message.reply_text(ia_response, parse_mode="markdown")
        else:
            ia_response = ZAIProvider().chat(update.message.text)
            await update.message.reply_text(ia_response, parse_mode="markdown")
        else:
            ia_response = ZAIProvider().chat(update.message.text)
            await update.message.reply_text(ia_response, parse_mode="markdown")

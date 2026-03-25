import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from telegram import Update
from telegram.ext import CallbackContext, filters
from telegram.error import BadRequest

from database.managers import MessageManager
from providers.zai import ZAIProvider
from telegrambot.handlers.media import get_media
from telegrambot.handlers.utils import is_link, is_allowed_link

logger = logging.getLogger(__name__)


def is_bot_mentioned(update: Update) -> bool:
    """Check if bot @fimosin_bot is mentioned in message."""
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
    if not update.message:
        return

    message = update.message

    # Check for media links
    if message.text and is_allowed_link(message.text):
        await get_media(update, context)

    # Check if bot is mentioned
    if is_bot_mentioned(update):
        # Verificar se é um reply (mencionado) ou se é uma mensagem simples
        # caso seja reply, enviar mensagem original e mensagem do reply como contexto
        if message.reply_to_message:
            reply_message = message.reply_to_message.text
            reply_message_user = (
                message.reply_to_message.from_user.full_name
                if message.reply_to_message.from_user
                else "Unknown"
            )
            context_message = message.text
            context_message_user = (
                message.from_user.full_name if message.from_user else "Unknown"
            )
            full_prompt = f"{reply_message_user}: {reply_message}\n{context_message_user}: {context_message}"
            ia_response = ZAIProvider().chat(full_prompt)
            try:
                await message.reply_text(ia_response, parse_mode="markdown")
            except BadRequest as e:
                logger.warning(f"Markdown parse error, sending without formatting: {e}")
                await message.reply_text(ia_response)
        else:
            ia_response = ZAIProvider().chat(message.text)
            try:
                await message.reply_text(ia_response, parse_mode="markdown")
            except BadRequest as e:
                logger.warning(f"Markdown parse error, sending without formatting: {e}")
                await message.reply_text(ia_response)

    # Save to database (only if text exists)
    if not message.text:
        return

    try:
        from_user = None
        if message.from_user:
            from_user = message.from_user.username or message.from_user.first_name

        reply_to_message_id = None
        reply_text = None
        to_user = None
        if message.reply_to_message:
            reply_to_message_id = message.reply_to_message.message_id
            reply_text = message.reply_to_message.text
            if message.reply_to_message.from_user:
                to_user = (
                    message.reply_to_message.from_user.username
                    or message.reply_to_message.from_user.first_name
                )

        MessageManager.add_message(
            telegram_message_id=message.message_id,
            text=message.text,
            chat_id=message.chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
            message_type="text",
        )
    except Exception as e:
        logger.error(f"Error logging text message: {e}", exc_info=True)

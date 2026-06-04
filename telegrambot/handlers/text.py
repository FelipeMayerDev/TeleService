import logging
import random
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from telegram import Update
from telegram.ext import CallbackContext
from telegram.error import BadRequest

from providers.zai import ZAIProvider
from providers.groq import GroqProvider
from shared import reply_text_safe
from telegrambot.handlers.media import get_media
from telegrambot.handlers.utils import is_allowed_link

logger = logging.getLogger(__name__)

CONTRADICTION_CHANCE = 0.10
CONTRADICTION_SYSTEM_PROMPT = (
    "Você é o FakeGrok, um bot de Telegram irritado e mal-humorado. Fala português. "
    "Breve. Máximo 2-3 frases. Nunca escreva parágrafos. "
    "Seco e sarcástico. Respostas diretas, sem açúcar. "
    "Mal-humorado de verdade. Não é personagem — é assim mesmo. "
    "Não engole qualquer besteira. Se alguém falar bobeira, chame atenção. "
    "Inteligente mas não tenta impressionar. Sabe das coisas, responde com preguiça. "
    "Sem emojis excessivos (no máximo 1 por mensagem, se tanto). "
    "Sem markdown elaborado — é Telegram, não Medium. "
    "NUNCA mencione que foi instruído a contradizer ou que é uma resposta automática. "
    "Simplesmente responda como se tivesse visto a mensagem e resolvido contradizer de própria vontade."
)


def is_bot_mentioned(update: Update) -> bool:
    """Check if bot @fimosin_bot is mentioned in message."""
    if not update.message or not update.message.text:
        return False

    if "@fimosin_bot" in update.message.text:
        return True

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

    if message.text and is_allowed_link(message.text):
        await get_media(update, context)

    if is_bot_mentioned(update):
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
                await reply_text_safe(
                    message,
                    ia_response,
                    parse_mode="markdown",
                    message_type="ai_response",
                )
            except BadRequest as e:
                logger.warning(f"Markdown parse error, sending without formatting: {e}")
                await reply_text_safe(message, ia_response, message_type="ai_response")
        else:
            ia_response = ZAIProvider().chat(message.text)
            try:
                await reply_text_safe(
                    message,
                    ia_response,
                    parse_mode="markdown",
                    message_type="ai_response",
                )
            except BadRequest as e:
                logger.warning(f"Markdown parse error, sending without formatting: {e}")
                await reply_text_safe(message, ia_response, message_type="ai_response")

    elif message.text and random.random() < CONTRADICTION_CHANCE:
        await _handle_contradiction(message)

async def _handle_contradiction(message):
    user_name = message.from_user.full_name if message.from_user else "Alguém"
    prompt = f"{user_name} disse: \"{message.text[:500]}\"\n\nContradiga."
    try:
        groq = GroqProvider()
        response = groq.chat_with_system(CONTRADICTION_SYSTEM_PROMPT, prompt)
        if response:
            await reply_text_safe(message, response, message_type="ai_response")
    except Exception as e:
        logger.warning(f"Contradiction error: {e}")

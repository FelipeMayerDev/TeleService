import logging
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()
logger = logging.getLogger(__name__)


async def send_telegram_message(
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    text: Optional[str] = None,
    photo: Optional[str] = None,
) -> Optional[Tuple[int, int]]:
    if token is None:
        token = os.getenv("TELEGRAM_TOKEN")
    if chat_id is None:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print(token)
        logger.warning("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not configured")
        return None

    print(token)
    bot = Bot(token=token)

    try:
        if photo:
            message = await bot.send_photo(chat_id=chat_id, photo=photo, caption=text)
            log_text = text[:50] if text else "No caption"
            logger.info(f"Sent photo to Telegram: {log_text}...")
            return (message.message_id, int(chat_id))
        else:
            if not text:
                logger.warning("No text provided for message")
                return None
            message = await bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"Sent to Telegram: {text[:50]}...")
            return (message.message_id, int(chat_id))
    except Exception as e:
        logger.error(f"Error sending to Telegram: {e}")
        return None


async def edit_telegram_message(
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    message_id: Optional[int] = None,
    text: Optional[str] = None,
) -> bool:
    if token is None:
        token = os.getenv("TELEGRAM_TOKEN")
    if chat_id is None:
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id or message_id is None or not text:
        logger.warning(
            "TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, message_id or text not provided"
        )
        return False

    bot = Bot(token=token)

    try:
        await bot.edit_message_text(
            chat_id=int(chat_id),
            message_id=int(message_id),
            text=str(text),
        )
        logger.info(f"Edited Telegram message {message_id}: {text[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Error editing Telegram message: {e}")
        return False

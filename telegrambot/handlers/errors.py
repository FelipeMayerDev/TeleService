class VideoNotFound(Exception):
    pass


import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import NetworkError, TimedOut, RetryAfter

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    logger.error("Exception while handling an update:", exc_info=error)

    if isinstance(error, NetworkError):
        if "Bad Gateway" in str(error):
            logger.warning(f"Bad Gateway from Telegram API, will retry: {error}")
        else:
            logger.warning(f"Network error, will retry: {error}")
    elif isinstance(error, TimedOut):
        logger.warning(f"Request timed out, will retry: {error}")
    elif isinstance(error, RetryAfter):
        logger.warning(f"Rate limited by Telegram API: {error}")

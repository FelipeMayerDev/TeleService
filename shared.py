import logging
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from telegram import Bot, Message
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

import discord
from discord import Message as DiscordMessage, Interaction
from discord.ext import commands

from domain import MessageService

load_dotenv()
logger = logging.getLogger(__name__)

message_service = MessageService()


async def send_telegram_message(
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
    text: Optional[str] = None,
    photo: Optional[str] = None,
    save_to_db: bool = False,
    message_type: Optional[str] = None,
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
            if save_to_db and chat_id:
                message_service.add_telegram_message(
                    telegram_message_id=message.message_id,
                    text=text or "[Photo]",
                    chat_id=int(chat_id),
                    from_user="System",
                    to_user=None,
                    reply_to_message_id=None,
                    reply_text=None,
                    message_type=message_type or "photo",
                )
            return (message.message_id, int(chat_id))
        else:
            if not text:
                logger.warning("No text provided for message")
                return None
            message = await bot.send_message(chat_id=chat_id, text=text)
            logger.info(f"Sent to Telegram: {text[:50]}...")
            if save_to_db and chat_id:
                message_service.add_telegram_message(
                    telegram_message_id=message.message_id,
                    text=text,
                    chat_id=int(chat_id),
                    from_user="System",
                    to_user=None,
                    reply_to_message_id=None,
                    reply_text=None,
                    message_type=message_type or "text",
                )
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


async def reply_text_safe(
    message: Message,
    text: str,
    parse_mode: Optional[str] = None,
    message_type: str = "text",
    save_to_db: bool = True,
) -> Message:
    reply_msg = await message.reply_text(text, parse_mode=parse_mode)

    if save_to_db and reply_msg:
        from_user = None

        try:
            if message.reply_to_message and message.reply_to_message.bot:
                from_user = (
                    message.reply_to_message.bot.first_name
                    or message.reply_to_message.bot.username
                )
            elif message.reply_to_message and message.reply_to_message.from_user:
                from_user = (
                    message.reply_to_message.from_user.username
                    or message.reply_to_message.from_user.first_name
                )
        except Exception:
            from_user = None

        try:
            message_service.add_telegram_message(
                telegram_message_id=reply_msg.message_id,
                text=text,
                chat_id=message.chat_id,
                from_user=from_user or "Bot",
                to_user=None,
                reply_to_message_id=message.message_id,
                reply_text=message.text or message.caption,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving reply_text to database: {e}")

    return reply_msg


async def reply_photo_safe(
    message: Message,
    photo,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    message_type: str = "photo",
    save_to_db: bool = True,
) -> Message:
    reply_msg = await message.reply_photo(photo, caption=caption, parse_mode=parse_mode)

    if save_to_db and reply_msg:
        from_user = None

        try:
            if message.reply_to_message and message.reply_to_message.bot:
                from_user = (
                    message.reply_to_message.bot.first_name
                    or message.reply_to_message.bot.username
                )
            elif message.reply_to_message and message.reply_to_message.from_user:
                from_user = (
                    message.reply_to_message.from_user.username
                    or message.reply_to_message.from_user.first_name
                )
        except Exception:
            from_user = None

        try:
            message_service.add_telegram_message(
                telegram_message_id=reply_msg.message_id,
                text=caption or "[Photo]",
                chat_id=message.chat_id,
                from_user=from_user or "Bot",
                to_user=None,
                reply_to_message_id=message.message_id,
                reply_text=message.text or message.caption,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving reply_photo to database: {e}")

    return reply_msg


async def reply_video_safe(
    message: Message,
    video,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    message_type: str = "video",
    save_to_db: bool = True,
) -> Message:
    reply_msg = await message.reply_video(video, caption=caption, parse_mode=parse_mode)

    if save_to_db and reply_msg:
        from_user = None

        try:
            if message.reply_to_message and message.reply_to_message.bot:
                from_user = (
                    message.reply_to_message.bot.first_name
                    or message.reply_to_message.bot.username
                )
            elif message.reply_to_message and message.reply_to_message.from_user:
                from_user = (
                    message.reply_to_message.from_user.username
                    or message.reply_to_message.from_user.first_name
                )
        except Exception:
            from_user = None

        try:
            message_service.add_telegram_message(
                telegram_message_id=reply_msg.message_id,
                text=caption or "[Video]",
                chat_id=message.chat_id,
                from_user=from_user or "Bot",
                to_user=None,
                reply_to_message_id=message.message_id,
                reply_text=message.text or message.caption,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving reply_video to database: {e}")

    return reply_msg


async def send_message_safe(
    bot: Bot,
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = None,
    message_type: str = "text",
    save_to_db: bool = True,
) -> Optional[Message]:
    sent_msg = await bot.send_message(chat_id, text, parse_mode=parse_mode)

    if save_to_db and sent_msg:
        try:
            message_service.add_telegram_message(
                telegram_message_id=sent_msg.message_id,
                text=text,
                chat_id=chat_id,
                from_user="System",
                to_user=None,
                reply_to_message_id=None,
                reply_text=None,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving send_message to database: {e}")

    return sent_msg


async def send_photo_safe(
    bot: Bot,
    chat_id: int,
    photo,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    message_type: str = "photo",
    save_to_db: bool = True,
) -> Optional[Message]:
    sent_msg = await bot.send_photo(
        chat_id, photo, caption=caption, parse_mode=parse_mode
    )

    if save_to_db and sent_msg:
        try:
            message_service.add_telegram_message(
                telegram_message_id=sent_msg.message_id,
                text=caption or "[Photo]",
                chat_id=chat_id,
                from_user="System",
                to_user=None,
                reply_to_message_id=None,
                reply_text=None,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving send_photo to database: {e}")

    return sent_msg


async def discord_reply_text_safe(
    message: DiscordMessage,
    content: str,
    message_type: str = "discord_message",
    save_to_db: bool = True,
) -> DiscordMessage:
    reply_msg = await message.reply(content)

    if save_to_db and reply_msg:
        from_user = None
        if reply_msg.author:
            from_user = (
                reply_msg.author.name
                or reply_msg.author.display_name
                or reply_msg.author.global_name
            )

        try:
            message_service.add_discord_message(
                discord_message_id=reply_msg.id,
                text=content,
                chat_id=reply_msg.channel.id,
                from_user=from_user or "DiscordBot",
                to_user=None,
                reply_to_message_id=message.id,
                reply_text=message.content,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving discord reply to database: {e}")

    return reply_msg


async def discord_channel_send_text_safe(
    channel: discord.TextChannel,
    content: str,
    message_type: str = "discord_message",
    save_to_db: bool = True,
) -> DiscordMessage:
    sent_msg = await channel.send(content)

    if save_to_db and sent_msg:
        from_user = None
        if sent_msg.author:
            from_user = (
                sent_msg.author.name
                or sent_msg.author.display_name
                or sent_msg.author.global_name
            )

        try:
            message_service.add_discord_message(
                discord_message_id=sent_msg.id,
                text=content,
                chat_id=channel.id,
                from_user=from_user or "DiscordBot",
                to_user=None,
                reply_to_message_id=None,
                reply_text=None,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving discord send to database: {e}")

    return sent_msg


async def discord_followup_send_safe(
    interaction: Interaction,
    content: str,
    message_type: str = "discord_interaction",
    save_to_db: bool = True,
    ephemeral: bool = False,
) -> Optional[DiscordMessage]:
    await interaction.response.defer(ephemeral=ephemeral)
    followup_msg = await interaction.followup.send(content, ephemeral=ephemeral)

    if save_to_db and followup_msg and not ephemeral:
        from_user = None
        if followup_msg.author:
            from_user = (
                followup_msg.author.name
                or followup_msg.author.display_name
                or followup_msg.author.global_name
            )

        try:
            message_service.add_discord_message(
                discord_message_id=followup_msg.id,
                text=content,
                chat_id=followup_msg.channel.id if followup_msg.channel else 0,
                from_user=from_user or "DiscordBot",
                to_user=None,
                reply_to_message_id=None,
                reply_text=None,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving discord followup to database: {e}")

    return followup_msg


async def discord_send_embed_safe(
    channel: discord.TextChannel,
    embed: discord.Embed,
    message_type: str = "discord_embed",
    save_to_db: bool = True,
) -> DiscordMessage:
    sent_msg = await channel.send(embed=embed)

    if save_to_db and sent_msg:
        from_user = None
        if sent_msg.author:
            from_user = (
                sent_msg.author.name
                or sent_msg.author.display_name
                or sent_msg.author.global_name
            )

        try:
            message_service.add_discord_message(
                discord_message_id=sent_msg.id,
                text=embed.title or "[Embed]",
                chat_id=channel.id,
                from_user=from_user or "DiscordBot",
                to_user=None,
                reply_to_message_id=None,
                reply_text=None,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving discord embed to database: {e}")

    return sent_msg


async def discord_reply_embed_safe(
    message: DiscordMessage,
    embed: discord.Embed,
    message_type: str = "discord_embed",
    save_to_db: bool = True,
) -> DiscordMessage:
    reply_msg = await message.reply(embed=embed)

    if save_to_db and reply_msg:
        from_user = None
        if reply_msg.author:
            from_user = (
                reply_msg.author.name
                or reply_msg.author.display_name
                or reply_msg.author.global_name
            )

        try:
            message_service.add_discord_message(
                discord_message_id=reply_msg.id,
                text=embed.title or "[Embed]",
                chat_id=reply_msg.channel.id,
                from_user=from_user or "DiscordBot",
                to_user=None,
                reply_to_message_id=message.id,
                reply_text=message.content,
                message_type=message_type,
            )
        except Exception as e:
            logger.error(f"Error saving discord embed reply to database: {e}")

    return reply_msg

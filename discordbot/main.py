#!/usr/bin/env python

import logging
import ctypes
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
import discord.opus
from config import DISCORD_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
from domain import init_database

# Load Opus codec for voice connections
if not discord.opus.is_loaded():
    try:
        _lib = ctypes.util.find_library('opus')
        if _lib:
            discord.opus.load_opus(_lib)
        else:
            print('WARNING: Opus library not found!')
    except Exception as e:
        print(f'WARNING: Failed to load Opus: {e}')
from handlers import music_commands, VoiceStateHandler
from handlers.online_status import get_online_users_with_status
from shared import discord_channel_send_text_safe, send_telegram_message
from telegram import Bot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

voice_state_handler: Optional[VoiceStateHandler] = None


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    logger.info("Music player commands loaded")

    global voice_state_handler
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not configured, voice state notifications disabled"
        )
        return

    voice_state_handler = VoiceStateHandler(
        bot=Bot(token=TELEGRAM_TOKEN),
        telegram_chat_id=int(TELEGRAM_CHAT_ID),
        cooldown=5,
        ignored_bot_names=set(),
    )


@client.event
async def on_voice_state_update(member, before, after):
    if member == client.user:
        if before.channel and not after.channel:
            logger.warning(
                f"Bot disconnected from voice channel in guild {member.guild.id}"
            )
        elif after.channel and not before.channel:
            logger.info(f"Bot connected to voice channel in guild {member.guild.id}")
        elif before.channel != after.channel:
            logger.info(f"Bot moved voice channels in guild {member.guild.id}")

    if voice_state_handler:
        await voice_state_handler.handle_voice_state(member, before, after)


@client.event
async def on_member_join(member):
    if member.bot:
        return

    logger.info(f"{member.display_name} joined the server")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return

    text = f"🎉 {member.display_name} entrou no Discord!"
    await send_telegram_message(
        token=TELEGRAM_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        save_to_db=True,
        message_type="member_join",
    )


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!hello"):
        await discord_channel_send_text_safe(
            message.channel, "Hello!", message_type="hello"
        )

    content = message.content
    prefix = "!"

    if not content.startswith(prefix):
        return

    args = content[len(prefix) :]
    command = args.split()[0].lower() if args else ""
    args = args[len(command) :].strip() if command else ""

    if command == "play":
        await music_commands.handle_play_command(message, args)
    elif command == "queue" or command == "q":
        await music_commands.handle_queue_command(message, args)
    elif command == "shuffle":
        await music_commands.handle_shuffle_command(message)
    elif command == "skip":
        await music_commands.handle_skip_command(message)
    elif command == "pause":
        await music_commands.handle_pause_command(message)
    elif command == "resume":
        await music_commands.handle_resume_command(message)
    elif command == "stop":
        await music_commands.handle_stop_command(message)
    elif command == "nowplaying" or command == "np":
        await music_commands.handle_nowplaying_command(message)
    elif command == "lyrics" or command == "l":
        await music_commands.handle_lyrics_command(message)
    elif command == "disconnect" or command == "dc":
        await music_commands.handle_disconnect_command(message)
    elif command == "clear":
        await music_commands.handle_clear_command(message)
    elif command == "remove":
        await music_commands.handle_remove_command(message, args)
    elif command == "move":
        await music_commands.handle_move_command(message, args)
    elif command == "online_agora" or command == "online":
        # Lista usuários online com status
        status_text = get_online_users_with_status(message)
        await discord_channel_send_text_safe(
            message.channel, status_text, message_type="online_status"
        )


def main():
    init_database()

    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables")
        return

    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

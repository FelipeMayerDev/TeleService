#!/usr/bin/env python

import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from config import DISCORD_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
from handlers import music_commands, VoiceStateHandler
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
    if voice_state_handler:
        await voice_state_handler.handle_voice_state(member, before, after)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith("!hello"):
        await message.channel.send("Hello!")

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


def main():
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables")
        return

    client.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

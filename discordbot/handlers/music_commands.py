import logging
import random

import discord
from discord.ext import commands

from .music_player import MusicPlayer
from .music_ui import create_queue_embed, create_player_embed, MusicView, QueueView
from .music_utils import get_song_info, search_song
from shared import discord_channel_send_text_safe, discord_reply_text_safe

logger = logging.getLogger(__name__)


players: dict[int, MusicPlayer] = {}


def get_player(guild_id: int) -> MusicPlayer:
    if guild_id not in players:
        players[guild_id] = MusicPlayer(guild_id)
    return players[guild_id]


async def handle_play_command(message: discord.Message, args: str):
    guild_id = message.guild.id

    if not message.author.voice or not message.author.voice.channel:
        await discord_reply_text_safe(
            message,
            "You need to be in a voice channel to play music!",
            message_type="error",
        )
        return

    voice_channel = message.author.voice.channel
    player = get_player(guild_id)

    if not args:
        await discord_reply_text_safe(
            message,
            "Please provide a URL or search query!",
            message_type="error",
        )
        return

    is_url = args.startswith("http://") or args.startswith("https://")

    await discord_channel_send_text_safe(
        message.channel,
        "🔍 Searching for music...",
        message_type="status",
        save_to_db=False,
    )

    try:
        if is_url:
            song_info = get_song_info(args)
            if not song_info:
                await discord_reply_text_safe(
                    message,
                    "Could not fetch song information!",
                    message_type="error",
                )
                return
            songs = [song_info]
        else:
            results = search_song(args)
            if not results:
                await discord_reply_text_safe(
                    message,
                    "No results found!",
                    message_type="error",
                )
                return
            songs = results

        if not songs:
            await discord_reply_text_safe(
                message,
                "No songs found!",
                message_type="error",
            )
            return

        added_count = player.add_multiple_to_queue(songs)

        if added_count == 1:
            song = songs[0]
            await discord_channel_send_text_safe(
                message.channel,
                f"✅ Added to queue:\n"
                f"**{song['title']}**\n"
                f"👤 {song['artist']}\n"
                f"⏱️ {song.get('duration', 0)} seconds",
                message_type="music_added",
            )
        else:
            await discord_channel_send_text_safe(
                message.channel,
                f"✅ Added {added_count} songs to queue!",
                message_type="music_added",
            )

        if not player.is_playing or player.is_paused:
            if player.voice_client and player.voice_client.is_connected():
                if voice_channel != player.voice_client.channel:
                    await player.voice_client.move_to(voice_channel)
            else:
                player.voice_client = await voice_channel.connect()

            await player.play_next()

            embed = create_player_embed(player)
            view = MusicView(player)

            msg = await message.channel.send(embed=embed, view=view)
            player.set_player_message(msg)

    except Exception as e:
        logger.error(f"Error in play command: {e}")
        await discord_reply_text_safe(
            message,
            f"Error playing music: {str(e)}",
            message_type="error",
        )


async def handle_queue_command(message: discord.Message, args: str):
    guild_id = message.guild.id
    player = get_player(guild_id)

    page = 1
    if args:
        try:
            page = int(args)
        except ValueError:
            pass

    if not player.queue:
        await discord_reply_text_safe(
            message,
            "Queue is empty! Add songs first.",
            message_type="info",
        )
        return

    embed, view = create_queue_embed(player, page)
    await message.channel.send(embed=embed, view=view)


async def handle_shuffle_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.queue:
        await discord_reply_text_safe(
            message,
            "Queue is empty! Add songs first.",
            message_type="info",
        )
        return

    is_shuffled = player.shuffle_queue_mode()

    if is_shuffled:
        await discord_reply_text_safe(
            message,
            "🔀 Queue shuffled!",
            message_type="music_shuffle",
        )
    else:
        await discord_reply_text_safe(
            message,
            "📋 Queue restored to original order",
            message_type="music_shuffle",
        )

    if player.player_message:
        await player.update_player_message()


async def handle_skip_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.is_playing:
        await discord_reply_text_safe(
            message,
            "Nothing is playing right now!",
            message_type="info",
        )
        return

    if await player.skip():
        await discord_reply_text_safe(
            message,
            "⏭️ Skipped to next song!",
            message_type="music_skip",
        )

        if player.player_message:
            await player.update_player_message()
    else:
        await discord_reply_text_safe(
            message,
            "Could not skip or no next song",
            message_type="error",
        )


async def handle_pause_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.pause():
        await discord_reply_text_safe(
            message,
            "⏸️ Paused playback",
            message_type="music_pause",
        )

        if player.player_message:
            await player.update_player_message()
    else:
        await discord_reply_text_safe(
            message,
            "Could not pause (nothing playing or already paused)",
            message_type="error",
        )


async def handle_resume_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.resume():
        await discord_reply_text_safe(
            message,
            "▶️ Resumed playback",
            message_type="music_resume",
        )

        if player.player_message:
            await player.update_player_message()
    else:
        await discord_reply_text_safe(
            message,
            "Could not resume (not paused)",
            message_type="error",
        )


async def handle_stop_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.stop():
        await discord_reply_text_safe(
            message,
            "⏹️ Stopped playback and cleared queue",
            message_type="music_stop",
        )

        if player.player_message:
            await player.update_player_message()
    else:
        await discord_reply_text_safe(
            message,
            "Nothing to stop",
            message_type="info",
        )


async def handle_nowplaying_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.current:
        await discord_reply_text_safe(
            message,
            "Nothing is playing right now!",
            message_type="info",
        )
        return

    song = player.current
    elapsed, total, progress = player.get_progress()

    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**[{song['title']}]({song.get('webpage_url', '')})**\n"
        f"👤 {song['artist']}\n"
        f"⏱️ {elapsed}/{total} seconds ({progress}%)",
        color=discord.Color.blue(),
    )

    thumbnail = song.get("thumbnail")
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    embed.set_footer(text=f"Position: 1 of {len(player.queue) + 1} in queue")

    from shared import discord_send_embed_safe

    await discord_send_embed_safe(message.channel, embed, message_type="nowplaying")


async def handle_lyrics_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.current:
        await discord_reply_text_safe(
            message,
            "Nothing is playing right now!",
            message_type="info",
        )
        return

    await discord_channel_send_text_safe(
        message.channel,
        "🔍 Searching for lyrics...",
        message_type="status",
        save_to_db=False,
    )

    lyrics = await player.get_current_lyrics()

    if lyrics:
        from .music_ui import create_lyrics_embed
        from shared import discord_send_embed_safe

        embed = create_lyrics_embed(lyrics, player.current)

        try:
            await discord_send_embed_safe(message.channel, embed, message_type="lyrics")
        except discord.errors.HTTPException:
            await discord_channel_send_text_safe(
                message.channel,
                "Lyrics are too long! Check DM instead.",
                message_type="error",
            )

            try:
                await message.author.send(embed=embed)
            except Exception:
                await discord_channel_send_text_safe(
                    message.channel,
                    "Could not send lyrics via DM either.",
                    message_type="error",
                )
    else:
        await discord_reply_text_safe(
            message,
            "Lyrics not found for this song.",
            message_type="error",
        )


async def handle_disconnect_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.disconnect():
        await discord_reply_text_safe(
            message,
            "👋 Disconnected from voice channel",
            message_type="music_disconnect",
        )
    else:
        await discord_reply_text_safe(
            message,
            "Not connected to any voice channel",
            message_type="info",
        )


async def handle_clear_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if player.clear_queue():
        await message.reply("🗑️ Queue cleared!")

        if player.player_message:
            await player.update_player_message()
    else:
        await message.reply("Queue is already empty")


async def handle_remove_command(message: discord.Message, args: str):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not args:
        await message.reply(
            "Please provide the position of the song to remove (e.g., !remove 1)"
        )
        return

    try:
        index = int(args) - 1

        if index < 0:
            await discord_reply_text_safe(
                message,
                "Invalid position!",
                message_type="error",
            )
            return

        song = player.remove_from_queue(index)

        if song:
            await discord_reply_text_safe(
                message,
                f"🗑️ Removed from queue: **{song['title']}**",
                message_type="music_remove",
            )

            if player.player_message:
                await player.update_player_message()
        else:
            await discord_reply_text_safe(
                message,
                "Invalid position or queue is empty!",
                message_type="error",
            )
    except ValueError:
        await discord_reply_text_safe(
            message,
            "Invalid position! Please use a number (e.g., !remove 1)",
            message_type="error",
        )


async def handle_move_command(message: discord.Message, args: str):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not args:
        await discord_reply_text_safe(
            message,
            "Usage: !move <from> <to> (e.g., !move 1 5)",
            message_type="error",
        )
        return

    try:
        parts = args.split()
        if len(parts) < 2:
            await discord_reply_text_safe(
                message,
                "Usage: !move <from> <to> (e.g., !move 1 5)",
                message_type="error",
            )
            return

        from_pos = int(parts[0]) - 1
        to_pos = int(parts[1]) - 1

        if (
            from_pos < 0
            or to_pos < 0
            or from_pos >= len(player.queue)
            or to_pos >= len(player.queue)
        ):
            await discord_reply_text_safe(
                message,
                "Invalid positions!",
                message_type="error",
            )
            return

        song = player.queue.pop(from_pos)
        player.queue.insert(to_pos, song)

        await discord_reply_text_safe(
            message,
            f"🔄 Moved **{song['title']}** from position {from_pos + 1} to {to_pos + 1}",
            message_type="music_move",
        )

        if player.player_message:
            await player.update_player_message()

    except ValueError:
        await discord_reply_text_safe(
            message,
            "Invalid positions! Please use numbers (e.g., !move 1 5)",
            message_type="error",
        )


async def cleanup_player(guild_id: int):
    if guild_id in players:
        player = players[guild_id]
        await player.disconnect()
        del players[guild_id]

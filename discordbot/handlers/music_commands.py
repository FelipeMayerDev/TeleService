import logging
import random

import discord
from discord.ext import commands

from .music_player import MusicPlayer
from .music_ui import create_queue_embed, create_player_embed, MusicView, QueueView
from .music_utils import get_song_info, search_song

logger = logging.getLogger(__name__)


players: dict[int, MusicPlayer] = {}


def get_player(guild_id: int) -> MusicPlayer:
    if guild_id not in players:
        players[guild_id] = MusicPlayer(guild_id)
    return players[guild_id]


async def handle_play_command(message: discord.Message, args: str):
    guild_id = message.guild.id

    if not message.author.voice or not message.author.voice.channel:
        await message.reply("You need to be in a voice channel to play music!")
        return

    voice_channel = message.author.voice.channel
    player = get_player(guild_id)

    if not args:
        await message.reply("Please provide a URL or search query!")
        return

    is_url = args.startswith("http://") or args.startswith("https://")

    await message.channel.send("🔍 Searching for music...")

    try:
        if is_url:
            song_info = get_song_info(args)
            if not song_info:
                await message.reply("Could not fetch song information!")
                return
            songs = [song_info]
        else:
            results = search_song(args)
            if not results:
                await message.reply("No results found!")
                return
            songs = results

        if not songs:
            await message.reply("No songs found!")
            return

        added_count = player.add_multiple_to_queue(songs)

        if added_count == 1:
            song = songs[0]
            await message.channel.send(
                f"✅ Added to queue:\n"
                f"**{song['title']}**\n"
                f"👤 {song['artist']}\n"
                f"⏱️ {song.get('duration', 0)} seconds"
            )
        else:
            await message.channel.send(f"✅ Added {added_count} songs to the queue!")

        if not player.is_playing and not player.is_paused:
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
        await message.reply(f"Error playing music: {str(e)}")


async def handle_queue_command(message: discord.Message, args: str):
    guild_id = message.guild.id
    player = get_player(guild_id)

    page = 1
    if args:
        try:
            page = int(args)
        except ValueError:
            pass

    embed = create_queue_embed(player, page=page)
    view = QueueView(player, current_page=page)

    await message.channel.send(embed=embed, view=view)


async def handle_shuffle_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.queue:
        await message.reply("Queue is empty! Add songs first.")
        return

    is_shuffled = player.shuffle_queue_mode()

    if is_shuffled:
        await message.reply("🔀 Queue shuffled!")
    else:
        await message.reply("📋 Queue restored to original order")

    if player.player_message:
        await player.update_player_message()


async def handle_skip_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.is_playing:
        await message.reply("Nothing is playing right now!")
        return

    if await player.skip():
        await message.reply("⏭️ Skipped to next song!")

        if player.player_message:
            await player.update_player_message()
    else:
        await message.reply("Could not skip or no next song")


async def handle_pause_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.pause():
        await message.reply("⏸️ Paused playback")

        if player.player_message:
            await player.update_player_message()
    else:
        await message.reply("Could not pause (nothing playing or already paused)")


async def handle_resume_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.resume():
        await message.reply("▶️ Resumed playback")

        if player.player_message:
            await player.update_player_message()
    else:
        await message.reply("Could not resume (not paused)")


async def handle_stop_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.stop():
        await message.reply("⏹️ Stopped playback and cleared queue")

        if player.player_message:
            await player.update_player_message()
    else:
        await message.reply("Nothing to stop")


async def handle_nowplaying_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.current:
        await message.reply("Nothing is playing right now!")
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

    await message.channel.send(embed=embed)


async def handle_lyrics_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not player.current:
        await message.reply("Nothing is playing right now!")
        return

    await message.channel.send("🔍 Searching for lyrics...")

    lyrics = await player.get_current_lyrics()

    if lyrics:
        from .music_ui import create_lyrics_embed

        embed = create_lyrics_embed(lyrics, player.current)

        try:
            await message.channel.send(embed=embed)
        except discord.errors.HTTPException:
            await message.channel.send(f"Lyrics are too long! Check DM instead.")

            try:
                await message.author.send(embed=embed)
            except Exception:
                await message.channel.send("Could not send lyrics via DM either.")
    else:
        await message.reply("Lyrics not found for this song.")


async def handle_disconnect_command(message: discord.Message):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if await player.disconnect():
        await message.reply("👋 Disconnected from voice channel")
    else:
        await message.reply("Not connected to any voice channel")


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
            await message.reply("Invalid position!")
            return

        song = player.remove_from_queue(index)

        if song:
            await message.reply(f"🗑️ Removed from queue: **{song['title']}**")

            if player.player_message:
                await player.update_player_message()
        else:
            await message.reply("Invalid position or queue is empty!")
    except ValueError:
        await message.reply("Invalid position! Please use a number (e.g., !remove 1)")


async def handle_move_command(message: discord.Message, args: str):
    guild_id = message.guild.id
    player = get_player(guild_id)

    if not args:
        await message.reply("Usage: !move <from> <to> (e.g., !move 1 5)")
        return

    try:
        parts = args.split()
        if len(parts) < 2:
            await message.reply("Usage: !move <from> <to> (e.g., !move 1 5)")
            return

        from_pos = int(parts[0]) - 1
        to_pos = int(parts[1]) - 1

        if (
            from_pos < 0
            or to_pos < 0
            or from_pos >= len(player.queue)
            or to_pos >= len(player.queue)
        ):
            await message.reply("Invalid positions!")
            return

        song = player.queue.pop(from_pos)
        player.queue.insert(to_pos, song)

        await message.reply(
            f"🔄 Moved **{song['title']}** from position {from_pos + 1} to {to_pos + 1}"
        )

        if player.player_message:
            await player.update_player_message()

    except ValueError:
        await message.reply("Invalid positions! Please use numbers (e.g., !move 1 5)")


async def cleanup_player(guild_id: int):
    if guild_id in players:
        player = players[guild_id]
        await player.disconnect()
        del players[guild_id]

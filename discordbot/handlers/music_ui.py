import logging

import discord
from discord import ui

from .music_utils import format_duration

logger = logging.getLogger(__name__)


def create_player_embed(player) -> discord.Embed:
    if player.current:
        title = player.current.get("title", "Unknown Title")
        artist = player.current.get("artist", "Unknown Artist")
        duration = player.current.get("duration", 0)
        thumbnail = player.current.get("thumbnail")
        url = player.current.get("webpage_url", "")

        status_emoji = "⏸️" if player.is_paused else "▶️"
        status_text = "Paused" if player.is_paused else "Now Playing"

        embed = discord.Embed(
            title=f"{status_emoji} {status_text}",
            description=f"**[{title}]({url})**\n👤 {artist}\n",
            color=discord.Color.blue()
            if not player.is_paused
            else discord.Color.orange(),
        )

        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        elapsed, total, progress = player.get_progress()
        progress_bar = create_progress_bar(progress)
        embed.add_field(
            name="Progress",
            value=f"{progress_bar} `{format_duration(elapsed)} / {format_duration(total)}`",
            inline=False,
        )

        queue_info = f"🎵 {len(player.queue)} song{'s' if len(player.queue) != 1 else ''} in queue"
        if player.is_shuffle:
            queue_info += " | 🔀 Shuffle ON"
        embed.add_field(name="Queue", value=queue_info, inline=False)

        embed.set_footer(text="Use the buttons below to control playback")

    else:
        embed = discord.Embed(
            title="🎵 Music Player",
            description="No song is currently playing. Use `!play <url>` to start!",
            color=discord.Color.gray(),
        )

        if player.queue:
            embed.add_field(
                name="Queue",
                value=f"🎵 {len(player.queue)} song{'s' if len(player.queue) != 1 else ''} in queue",
                inline=False,
            )

    return embed


def create_queue_embed(player, page: int = 1, per_page: int = 10) -> discord.Embed:
    total_songs = len(player.queue)
    total_pages = (total_songs + per_page - 1) // per_page
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_songs)

    embed = discord.Embed(
        title="📋 Music Queue",
        description=f"Total songs: {total_songs}",
        color=discord.Color.purple(),
    )

    if player.current:
        embed.add_field(
            name="▶️ Now Playing",
            value=f"**{player.current.get('title', 'Unknown')}**\n"
            f"👤 {player.current.get('artist', 'Unknown')}\n"
            f"⏱️ {format_duration(player.current.get('duration', 0))}",
            inline=False,
        )

    if total_songs > 0:
        queue_list = []
        for i in range(start_idx, end_idx):
            song = player.queue[i]
            position = i + 1
            queue_list.append(
                f"**{position}.** {song.get('title', 'Unknown')}\n"
                f"   👤 {song.get('artist', 'Unknown')} | ⏱️ {format_duration(song.get('duration', 0))}"
            )

        embed.add_field(
            name=f"Up Next (Page {page}/{total_pages})",
            value="\n".join(queue_list),
            inline=False,
        )
    else:
        embed.add_field(
            name="Queue",
            value="The queue is empty. Use `!play <url>` to add songs!",
            inline=False,
        )

    if player.is_shuffle:
        embed.add_field(name="Mode", value="🔀 Shuffle Enabled", inline=False)

    embed.set_footer(
        text=f"Page {page}/{total_pages} • Total duration: {format_duration(player.get_total_duration())}"
    )

    return embed


def create_lyrics_embed(lyrics: str, song_info: dict) -> discord.Embed:
    title = song_info.get("title", "Unknown")
    artist = song_info.get("artist", "Unknown")

    max_chars = 2000
    if len(lyrics) > max_chars:
        lyrics = lyrics[: max_chars - 50] + "\n... (lyrics truncated)"

    embed = discord.Embed(
        title=f"📜 Lyrics: {title}",
        description=f"👤 {artist}\n\n```{lyrics}```",
        color=discord.Color.gold(),
    )

    embed.set_footer(text="Lyrics provided by lrclib.net")

    return embed


def create_progress_bar(progress: int, length: int = 20) -> str:
    filled = int((progress / 100) * length)
    bar = "█" * filled + "░" * (length - filled)
    return bar


class MusicView(ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)
        self.player = player

    def _update_button_states(self):
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = not self._can_use_button(item.custom_id)

    def _can_use_button(self, custom_id: str) -> bool:
        if not self.player.voice_client or not self.player.voice_client.is_connected():
            return False

        if custom_id == "pause" and (
            not self.player.is_playing or self.player.is_paused
        ):
            return False

        if custom_id == "resume" and not self.player.is_paused:
            return False

        if custom_id == "skip" and not self.player.is_playing:
            return False

        if custom_id == "stop" and not self.player.is_playing:
            return False

        if custom_id == "shuffle" and not self.player.queue:
            return False

        if custom_id == "lyrics" and not self.player.current:
            return False

        return True

    @ui.button(label="⏸️ Pause", style=discord.ButtonStyle.secondary, custom_id="pause")
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        if await self.player.pause():
            await interaction.followup.send("⏸️ Paused playback", ephemeral=True)
            await self._update_view()
        else:
            await interaction.followup.send("Could not pause playback", ephemeral=True)

    @ui.button(label="▶️ Resume", style=discord.ButtonStyle.primary, custom_id="resume")
    async def resume_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        if await self.player.resume():
            await interaction.followup.send("▶️ Resumed playback", ephemeral=True)
            await self._update_view()
        else:
            await interaction.followup.send("Could not resume playback", ephemeral=True)

    @ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger, custom_id="stop")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        if await self.player.stop():
            await interaction.followup.send(
                "⏹️ Stopped playback and cleared queue", ephemeral=True
            )
            await self._update_view()
        else:
            await interaction.followup.send("Could not stop playback", ephemeral=True)

    @ui.button(label="⏭️ Skip", style=discord.ButtonStyle.primary, custom_id="skip")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        if await self.player.skip():
            await interaction.followup.send("⏭️ Skipped to next song", ephemeral=True)
            await self._update_view()
        else:
            await interaction.followup.send(
                "Could not skip or no next song", ephemeral=True
            )

    @ui.button(
        label="🔀 Shuffle", style=discord.ButtonStyle.success, custom_id="shuffle"
    )
    async def shuffle_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        is_shuffled = self.player.shuffle_queue_mode()
        if is_shuffled:
            await interaction.followup.send("🔀 Queue shuffled!", ephemeral=True)
        else:
            await interaction.followup.send("📋 Queue unshuffled", ephemeral=True)

        await self._update_view()

    @ui.button(
        label="📜 Lyrics", style=discord.ButtonStyle.secondary, custom_id="lyrics"
    )
    async def lyrics_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        lyrics = await self.player.get_current_lyrics()

        if lyrics:
            embed = create_lyrics_embed(lyrics, self.player.current)

            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                logger.error(f"Error sending lyrics: {e}")
                await interaction.followup.send(
                    "Error displaying lyrics", ephemeral=True
                )
        else:
            await interaction.followup.send(
                "Lyrics not found for this song", ephemeral=True
            )

    @ui.button(label="📋 Queue", style=discord.ButtonStyle.secondary, custom_id="queue")
    async def queue_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()

        embed = create_queue_embed(self.player, page=1)

        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending queue: {e}")
            await interaction.followup.send("Error displaying queue", ephemeral=True)

    async def _update_view(self):
        self._update_button_states()

        if self.player.player_message:
            try:
                embed = create_player_embed(self.player)
                await self.player.player_message.edit(embed=embed, view=self)
            except Exception as e:
                logger.error(f"Error updating view: {e}")


class QueueView(ui.View):
    def __init__(self, player, current_page: int = 1, per_page: int = 10):
        super().__init__(timeout=300)
        self.player = player
        self.current_page = current_page
        self.per_page = per_page
        self.total_pages = (
            (len(player.queue) + per_page - 1) // per_page if player.queue else 1
        )
        self._update_buttons()

    def _update_buttons(self):
        total_songs = len(self.player.queue)
        self.total_pages = (
            (total_songs + self.per_page - 1) // self.per_page if total_songs > 0 else 1
        )

        for item in self.children:
            if isinstance(item, ui.Button):
                if item.custom_id == "prev_page":
                    item.disabled = self.current_page <= 1
                elif item.custom_id == "next_page":
                    item.disabled = self.current_page >= self.total_pages
                elif item.custom_id in ["refresh", "close"]:
                    item.disabled = False

    @ui.button(
        label="◀️ Prev", style=discord.ButtonStyle.secondary, custom_id="prev_page"
    )
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            self._update_buttons()
            await self._update_message(interaction)

    @ui.button(
        label="▶️ Next", style=discord.ButtonStyle.secondary, custom_id="next_page"
    )
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._update_buttons()
            await self._update_message(interaction)

    @ui.button(
        label="🔄 Refresh", style=discord.ButtonStyle.primary, custom_id="refresh"
    )
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        self._update_buttons()
        await self._update_message(interaction)

    @ui.button(label="❌ Close", style=discord.ButtonStyle.danger, custom_id="close")
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(view=None)

    async def _update_message(self, interaction: discord.Interaction):
        embed = create_queue_embed(self.player, self.current_page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

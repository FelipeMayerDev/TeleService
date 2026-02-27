import asyncio
import logging
import random
from typing import Optional

import discord
from discord.ext import tasks

from .music_utils import (
    get_audio_source,
    get_lyrics,
    get_song_info,
    search_song,
    shuffle_queue,
)

logger = logging.getLogger(__name__)


class MusicPlayer:
    TIMEOUT_SECONDS = 300

    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.queue: list = []
        self.original_queue: list = []
        self.current: Optional[dict] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.is_shuffle: bool = False
        self.last_played: float = 0
        self.timeout_task: Optional[asyncio.Task] = None
        self.player_message: Optional[discord.Message] = None

    def add_to_queue(self, song: dict) -> bool:
        try:
            self.queue.append(song)

            if self.is_shuffle:
                index = len(self.queue) - 1
                for i in range(len(self.queue) - 1, 0, -1):
                    j = random.randint(0, i)
                    self.queue[i], self.queue[j] = self.queue[j], self.queue[i]

            self._cancel_timeout()
            return True
        except Exception as e:
            logger.error(f"Error adding to queue: {e}")
            return False

    def add_multiple_to_queue(self, songs: list) -> int:
        added = 0
        for song in songs:
            if self.add_to_queue(song):
                added += 1
        return added

    def remove_from_queue(self, index: int) -> Optional[dict]:
        try:
            if 0 <= index < len(self.queue):
                song = self.queue.pop(index)
                self._cancel_timeout()
                return song
            return None
        except Exception as e:
            logger.error(f"Error removing from queue: {e}")
            return None

    def clear_queue(self) -> bool:
        try:
            self.queue.clear()
            self.is_shuffle = False
            self._cancel_timeout()
            return True
        except Exception as e:
            logger.error(f"Error clearing queue: {e}")
            return False

    def shuffle_queue_mode(self) -> bool:
        try:
            if self.is_shuffle:
                self.queue = self.original_queue[:]
                self.is_shuffle = False
                return False
            else:
                self.original_queue = self.queue[:]
                self.queue = shuffle_queue(self.queue)
                self.is_shuffle = True
                return True
        except Exception as e:
            logger.error(f"Error shuffling queue: {e}")
            return False

    async def play_next(self) -> bool:
        try:
            if self.timeout_task and not self.timeout_task.done():
                self.timeout_task.cancel()

            if not self.queue:
                logger.info(f"No more songs in queue for guild {self.guild_id}")
                await self._start_timeout()
                return False

            self.current = self.queue.pop(0)
            self.is_playing = True
            self.is_paused = False
            self.last_played = asyncio.get_event_loop().time()

            source = get_audio_source(self.current["url"])

            if not self.voice_client or not self.voice_client.is_connected():
                logger.error(f"Voice client not connected for guild {self.guild_id}")
                return False

            self.voice_client.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._on_track_end(e), self.voice_client.loop
                ),
            )

            logger.info(
                f"Now playing: {self.current['title']} in guild {self.guild_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error playing next track: {e}")
            self.is_playing = False
            return False

    async def _on_track_end(self, error):
        if error:
            logger.error(f"Track ended with error: {error}")

        await self.play_next()

    async def skip(self) -> bool:
        try:
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
                logger.info(f"Skipped track in guild {self.guild_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error skipping track: {e}")
            return False

    async def pause(self) -> bool:
        try:
            if (
                self.voice_client
                and self.voice_client.is_playing()
                and not self.is_paused
            ):
                self.voice_client.pause()
                self.is_paused = True
                logger.info(f"Paused track in guild {self.guild_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error pausing track: {e}")
            return False

    async def resume(self) -> bool:
        try:
            if self.voice_client and self.is_paused:
                self.voice_client.resume()
                self.is_paused = False
                logger.info(f"Resumed track in guild {self.guild_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error resuming track: {e}")
            return False

    async def stop(self) -> bool:
        try:
            if self.voice_client:
                if self.voice_client.is_playing():
                    self.voice_client.stop()
                self.clear_queue()
                self.current = None
                self.is_playing = False
                self.is_paused = False
                logger.info(f"Stopped playback in guild {self.guild_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping playback: {e}")
            return False

    async def disconnect(self) -> bool:
        try:
            if self.timeout_task and not self.timeout_task.done():
                self.timeout_task.cancel()

            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.disconnect()
                self.voice_client = None
                self.clear_queue()
                self.current = None
                self.is_playing = False
                self.is_paused = False
                logger.info(f"Disconnected from voice in guild {self.guild_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
            return False

    def _cancel_timeout(self):
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()
            logger.info(f"Timeout cancelled for guild {self.guild_id}")

    async def _start_timeout(self):
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()

        self.timeout_task = asyncio.create_task(self._timeout_handler())
        logger.info(f"Timeout started for guild {self.guild_id}")

    async def _timeout_handler(self):
        try:
            await asyncio.sleep(self.TIMEOUT_SECONDS)

            if not self.queue or not self.is_playing or self.is_paused:
                logger.info(
                    f"Timeout reached, disconnecting from guild {self.guild_id}"
                )
                await self.disconnect()
        except asyncio.CancelledError:
            logger.info(f"Timeout cancelled for guild {self.guild_id}")
        except Exception as e:
            logger.error(f"Error in timeout handler: {e}")

    def get_queue_position(self, song: dict) -> int:
        try:
            return self.queue.index(song)
        except ValueError:
            return -1

    def get_total_duration(self) -> int:
        duration = 0
        for song in self.queue:
            duration += song.get("duration", 0)
        if self.current:
            duration += self.current.get("duration", 0)
        return duration

    def get_progress(self) -> tuple:
        if not self.voice_client or not self.is_playing:
            return (0, 0, 0)

        try:
            duration = self.current.get("duration", 0)
            elapsed = asyncio.get_event_loop().time() - self.last_played

            if elapsed > duration:
                elapsed = duration

            progress = (elapsed / duration * 100) if duration > 0 else 0
            return (int(elapsed), duration, int(progress))
        except Exception:
            return (0, duration or 0, 0)

    async def get_current_lyrics(self) -> Optional[str]:
        if not self.current:
            return None

        artist = self.current.get("artist", "")
        title = self.current.get("clean_title") or self.current.get("title", "")

        if not artist or not title:
            return None

        try:
            lyrics = await get_lyrics(artist, title)
            return lyrics
        except Exception as e:
            logger.error(f"Error getting lyrics: {e}")
            return None

    def set_player_message(self, message: Optional[discord.Message]):
        self.player_message = message

    async def update_player_message(self):
        if not self.player_message:
            return False

        try:
            from .music_ui import create_player_embed, MusicView

            embed = create_player_embed(self)
            view = MusicView(self)

            await self.player_message.edit(embed=embed, view=view)
            return True
        except Exception as e:
            logger.error(f"Error updating player message: {e}")
            return False

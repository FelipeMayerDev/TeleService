import asyncio
import logging
import os
import random
import re
import time
from typing import Optional, Tuple
from urllib.parse import quote_plus

import aiohttp
import discord
import yt_dlp

logger = logging.getLogger(__name__)


def clean_title(title: Optional[str], artist: Optional[str]) -> str:
    if not title:
        return ""

    cleaned = title

    if artist:
        patterns = [
            rf"^{re.escape(artist)}\s*[-:–]\s*",
            rf"^{re.escape(artist.lower())}\s*[-:–]\s*",
            rf"^{re.escape(artist.title())}\s*[-:–]\s*",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s*\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"\s*\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\s*\{[^}]*\}", "", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


YTDL_FORMAT_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -b:a 192k",
}


ytdl = yt_dlp.YoutubeDL(YTDL_FORMAT_OPTIONS)

LYRICS_CACHE = {}
LYRICS_CACHE_TTL = 3600


class YTDLError(Exception):
    pass


class LyricsError(Exception):
    pass


def get_audio_source(url: str) -> Optional[discord.FFmpegOpusAudio]:
    try:
        info = ytdl.extract_info(url, download=False)

        if "entries" in info:
            info = info["entries"][0]

        if not info:
            raise YTDLError("Could not extract info from URL")

        audio_url = info.get("url")

        if not audio_url:
            formats = info.get("formats", [])
            audio_url = next(
                (f["url"] for f in formats if f.get("acodec") != "none"), None
            )

        if not audio_url:
            raise YTDLError("No audio URL found")

        source = discord.FFmpegOpusAudio(audio_url, **FFMPEG_OPTIONS)

        return source
    except Exception as e:
        logger.error(f"Error getting audio source: {e}")
        raise YTDLError(str(e))


def get_song_info(url: str) -> Optional[dict]:
    try:
        info = ytdl.extract_info(url, download=False)

        if "entries" in info:
            info = info["entries"][0]

        if not info:
            return None

        artist = info.get("artist") or info.get("uploader", "Unknown Artist")
        raw_title = info.get("title", "Unknown Title")

        return {
            "url": url,
            "title": raw_title,
            "clean_title": clean_title(raw_title, artist),
            "artist": artist,
            "duration": info.get("duration", 0),
            "thumbnail": info.get("thumbnail"),
            "webpage_url": info.get("webpage_url", url),
            "id": info.get("id"),
        }
    except Exception as e:
        logger.error(f"Error getting song info: {e}")
        return None


def search_song(query: str) -> Optional[list]:
    try:
        info = ytdl.extract_info(f"ytsearch:{query}", download=False)

        if not info or "entries" not in info:
            return None

        results = []
        for entry in info["entries"][:5]:
            if entry:
                artist = entry.get("artist") or entry.get("uploader")
                raw_title = entry.get("title")
                results.append(
                    {
                        "url": entry.get("webpage_url"),
                        "title": raw_title,
                        "clean_title": clean_title(raw_title, artist),
                        "artist": artist,
                        "duration": entry.get("duration"),
                        "thumbnail": entry.get("thumbnail"),
                        "id": entry.get("id"),
                    }
                )

        return results
    except Exception as e:
        logger.error(f"Error searching song: {e}")
        return None


async def get_lyrics_async(artist: str, title: str) -> Optional[str]:
    clean_song_title = clean_title(title, artist)
    cache_key = f"{artist.lower()}:{clean_song_title.lower()}"

    if cache_key in LYRICS_CACHE:
        cached_data = LYRICS_CACHE[cache_key]
        if time.time() - cached_data["timestamp"] < LYRICS_CACHE_TTL:
            logger.info(f"Cache hit for lyrics: {artist} - {clean_song_title}")
            return cached_data["lyrics"]

    try:
        query = f"{artist} {clean_song_title}"
        logger.info(f"Searching lyrics with query: {query}")
        encoded_query = quote_plus(query)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://lrclib.net/api/search?q={encoded_query}"
            ) as response:
                if response.status != 200:
                    raise LyricsError(f"API returned status {response.status}")

                data = await response.json()

                if not data or not isinstance(data, list):
                    raise LyricsError("No results found")

                for result in data[:3]:
                    synced_lyrics = result.get("syncedLyrics")
                    plain_lyrics = result.get("plainLyrics")

                    lyrics = synced_lyrics or plain_lyrics

                    if lyrics:
                        LYRICS_CACHE[cache_key] = {
                            "lyrics": lyrics,
                            "timestamp": time.time(),
                        }
                        logger.info(f"Found lyrics for: {artist} - {clean_song_title}")
                        return lyrics

                raise LyricsError("No lyrics found in results")

    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching lyrics: {e}")
        raise LyricsError(f"HTTP error: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching lyrics: {e}")
        raise LyricsError(str(e))


async def get_lyrics(artist: str, title: str) -> Optional[str]:
    try:
        return await get_lyrics_async(artist, title)
    except Exception as e:
        logger.error(f"Error getting lyrics: {e}")
        return None


def cleanup_cache():
    current_time = time.time()
    expired_keys = [
        key
        for key, value in LYRICS_CACHE.items()
        if current_time - value["timestamp"] > LYRICS_CACHE_TTL
    ]

    for key in expired_keys:
        del LYRICS_CACHE[key]

    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired lyrics cache entries")


def format_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"


def shuffle_queue(queue: list) -> list:
    if len(queue) <= 1:
        return queue

    queue_copy = queue[:]
    random.shuffle(queue_copy)

    return queue_copy

import re, os
from typing import Optional, Tuple
import yt_dlp
from faster_whisper import WhisperModel

from providers.groq import GroqProvider
from telegrambot.handlers.kinds import Origin

from .errors import VideoNotFound


def clean_subtitle_text(raw):
    lines = raw.splitlines()
    clean = []

    for line in lines:
        line = line.strip()

        if (
            not line
            or line.startswith("WEBVTT")
            or line.startswith("Kind:")
            or line.startswith("Language:")
            or "-->" in line
            or re.match(r"^\d+$", line)
            or re.match(r"^[<&]", line)
        ):
            continue

        clean.append(line)

    text = " ".join(clean).strip()
    return text if text else None


def is_valid_link(link) -> bool:
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)
            if info is None:
                return False

            duration = info.get("duration")
            if duration is None:
                return True
            return duration < (60 * 15)
    except Exception:
        return False


def is_link(text: str) -> bool:
    url_pattern = r"^https?://[^\s]+$"
    return bool(re.match(url_pattern, text))


def is_allowed_link(text: str):
    if not is_link(text):
        return False
    allowed_links = ["youtube.com/shorts/", "instagram.com/reel/", "facebook.com/reel/", "bsky", "/status/"]
    if not any(link for link in allowed_links if link in text):
        return False
    return True


def transcribe_audio(url: str, model_size: str, tmpdir: str) -> dict:
    """Downloads audio and transcribes it with faster-whisper."""
    audio_path = os.path.join(tmpdir, "audio.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": audio_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        _info = ydl.extract_info(url)
        title = _info.get("title")

    mp3_path = os.path.join(tmpdir, "audio.mp3")
    if not os.path.exists(mp3_path):
        files = os.listdir(tmpdir)
        if not files:
            raise FileNotFoundError("Audio download failed.")
        mp3_path = os.path.join(tmpdir, files[0])

    # First, we try in a free provider..
    try:
        text = GroqProvider().transcribe_audio(mp3_path)
        origin = Origin.GROQ
    except Exception as e:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(mp3_path, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments)
        origin = Origin.CPU
    finally:
        print(text)
        os.remove(mp3_path)
        return (text, title, origin)


def get_media_from_link(link) -> Optional[Tuple[any, any]]:
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best",
            "postprocessor_args": ["-movflags", "+faststart"],
            "download": False,
            "skip_download": True,
            "outtmpl": "/dev/null",
            "cachedir": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link)
            if not info.get("url") and not info.get("formats"):
                raise VideoNotFound("Video not found")

        thumbnail = info.get("thumbnail")
        if not thumbnail and info.get("thumbnails"):
            thumbnail = info["thumbnails"][0].get("url") if info["thumbnails"] else None
        if not thumbnail and info.get("formats"):
            for fmt in info["formats"]:
                if fmt.get("thumbnails"):
                    thumbnail = fmt["thumbnails"][0].get("url")
                    break

        video_data = {
            "url": info.get("url"),
            "title": info.get("title"),
            "thumbnail": thumbnail,
        }
        # sender = message.from_user.username or message.from_user.id
        # caption = f"***{video_data['title']}***\n\nLink: {message.text}\nEnviado por: {sender}"
        # await message.reply_video(
        #     video=video_data["url"], caption=caption, parse_mode="Markdown"
        # )
        return (video_data["url"], video_data["title"], video_data["thumbnail"])
    except Exception as e:
        print(f"Error: {e}")
        raise e

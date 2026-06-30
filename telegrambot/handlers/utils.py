import re, os, glob, io
from typing import Optional, Tuple
import yt_dlp
from faster_whisper import WhisperModel

from providers.groq import GroqProvider
from telegrambot.handlers.kinds import Origin

from .errors import VideoNotFound


# Instagram cookies para autenticação
INSTAGRAM_COOKIES_PATH = "/app/instagram-cookies.txt"
YDL_OPTS_BASE = {
    "quiet": True,
    "no_warnings": True,
    "no_save_cookies": True,
    "no_cache_dir": True,
}


def get_ydl_opts(extra_opts=None):
    """Retorna configurações do yt-dlp com cookies se disponíveis."""
    opts = YDL_OPTS_BASE.copy()
    if os.path.exists(INSTAGRAM_COOKIES_PATH):
        opts["cookiefile"] = INSTAGRAM_COOKIES_PATH
    if extra_opts:
        opts.update(extra_opts)
    return opts


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
        ydl_opts = get_ydl_opts({
            "skip_download": True,
        })
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
    allowed_links = ["youtube.com/shorts/", "instagram.com/reel/", "instagram.com/reels/", "instagram.com/p/", "facebook.com/reel/", "bsky", "/status/"]
    if not any(link for link in allowed_links if link in text):
        return False
    return True


def transcribe_audio(url: str, model_size: str, tmpdir: str) -> dict:
    """Downloads audio and transcribes it with faster-whisper."""
    audio_path = os.path.join(tmpdir, "audio.%(ext)s")
    ydl_opts = get_ydl_opts({
        "format": "bestaudio/best",
        "outtmpl": audio_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    })

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
    """Baixa mídia do link e retorna (buffer_video, titulo, thumbnail_url)."""
    try:
        ydl_opts = get_ydl_opts({
            "format": "best[height<=720][ext=mp4]/best[height<=720]/best[ext=mp4]/best",
            "postprocessor_args": ["-movflags", "+faststart"],
            "outtmpl": "/tmp/video.%(ext)s",
            "cachedir": False,
            "socket_timeout": 30,
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)

        # Ler o arquivo baixado para memória
        video_path = "/tmp/video.mp4"
        if not os.path.exists(video_path):
            # Tenta encontrar o arquivo com outro formato
            import glob
            video_files = glob.glob("/tmp/video.*")
            if video_files:
                video_path = video_files[0]
            else:
                raise VideoNotFound("Video download failed")

        with open(video_path, "rb") as f:
            video_buffer = io.BytesIO(f.read())

        # Limpa o arquivo temporário
        os.remove(video_path)

        thumbnail = info.get("thumbnail")
        if not thumbnail and info.get("thumbnails"):
            thumbnail = info["thumbnails"][0].get("url") if info["thumbnails"] else None
        if not thumbnail and info.get("formats"):
            for fmt in info["formats"]:
                if fmt.get("thumbnails"):
                    thumbnail = fmt["thumbnails"][0].get("url")
                    break

        return (video_buffer, info.get("title"), thumbnail)
    except Exception as e:
        print(f"Error: {e}")
        raise e

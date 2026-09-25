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
    allowed_links = ["youtube.com/shorts/", "youtube.com/watch", "youtu.be/", "instagram.com/reel/", "instagram.com/reels/", "instagram.com/p/", "facebook.com/reel/", "bsky", "/status/"]
    if not any(link for link in allowed_links if link in text):
        return False
    return True


def probe_media(link) -> bool:
    """True se yt-dlp reconhece o link e tem mídia (vídeo/imagem) baixável."""
    try:
        ydl_opts = get_ydl_opts({"skip_download": True})
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(link, download=False)
        return True
    except Exception:
        return False


YOUTUBE_MAX_DURATION = 180  # 3 min — mesmo teto dos shorts, agora p/ watch/youtu.be


def youtube_too_long(link: str) -> bool:
    """YouTube (watch/shorts/youtu.be) com duração > 3 min não vira mídia."""
    if not any(h in link for h in ("youtube.com/", "youtu.be/")):
        return False
    try:
        info = yt_dlp.YoutubeDL(get_ydl_opts({"skip_download": True})).extract_info(
            link, download=False
        )
        return (info.get("duration") or 0) > YOUTUBE_MAX_DURATION
    except Exception:
        return False


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


def get_media_from_link(link) -> Optional[Tuple[io.BytesIO, str, str, str]]:
    """Baixa mídia do link e retorna (buffer, titulo, thumbnail_url, tipo).

    tipo: 'video' ou 'image'. A extensão real do arquivo baixado decide qual.
    """
    try:
        ydl_opts = get_ydl_opts({
            # YouTube moderno: sem formatos progressivos (vídeo+áudio juntos) —
            # precisa de merge video+audio (ffmpeg). "best" sozinho falha com
            # "Requested format is not available" em vários vídeos.
            "format": "best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best",
            "postprocessor_args": ["-movflags", "+faststart"],
            "outtmpl": "/tmp/media.%(ext)s",
            "cachedir": False,
            "socket_timeout": 30,
        })
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)

        # Localiza o arquivo baixado — a extensão varia (mp4, jpg, webp, ...)
        files = glob.glob("/tmp/media.*")
        if not files:
            raise VideoNotFound("Media download failed")
        media_path = files[0]

        # ponytail: a extensão real é a fonte de verdade do tipo de mídia
        ext = os.path.splitext(media_path)[1].lower().lstrip(".")
        media_type = "image" if ext in ("jpg", "jpeg", "png", "webp", "gif") else "video"

        with open(media_path, "rb") as f:
            buffer = io.BytesIO(f.read())

        os.remove(media_path)

        thumbnail = info.get("thumbnail")
        if not thumbnail and info.get("thumbnails"):
            thumbnail = info["thumbnails"][0].get("url") if info["thumbnails"] else None
        if not thumbnail and info.get("formats"):
            for fmt in info["formats"]:
                if fmt.get("thumbnails"):
                    thumbnail = fmt["thumbnails"][0].get("url")
                    break

        return (buffer, info.get("title"), thumbnail, media_type)
    except Exception as e:
        print(f"Error: {e}")
        raise e

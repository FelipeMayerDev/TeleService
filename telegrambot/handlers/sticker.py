import os
import io
import sys
import logging
import subprocess
import tempfile
import requests as req

from PIL import Image
from telegram import Update
from telegram.ext import ContextTypes

sys.path.insert(0, "/app")
from shared import reply_text_safe

from telegram.ext import filters as tg_filters

log = logging.getLogger(__name__)

FAKEGROK_TOKEN = os.getenv("FAKEGROK_TOKEN", "")
STICKER_SET_NAME = "fakegrok_pack_by_fakegrokbot"
STICKER_SET_TITLE = "FakeGrok Pack"
TELEGRAM_API = "https://api.telegram.org"

# Separate animated sticker set (TGS/WebM stickers need their own pack)
ANIMATED_STICKER_SET_NAME = "fakegrok_animated_by_fakegrokbot"
ANIMATED_STICKER_SET_TITLE = "FakeGrok Animados"


class StickerPhotoFilter(tg_filters.MessageFilter):
    """Filter para mensagens de foto com caption /sticker."""
    def filter(self, message):
        if not message.photo:
            return False
        caption = (message.caption or "").strip().lower()
        return caption.startswith("/sticker")


sticker_photo_filter = StickerPhotoFilter()


class StickerMediaFilter(tg_filters.MessageFilter):
    """Filter para mensagens de GIF/video/document com caption /sticker."""
    def filter(self, message):
        if not (message.animation or message.video or message.document):
            return False
        caption = (message.caption or "").strip().lower()
        return caption.startswith("/sticker")


sticker_media_filter = StickerMediaFilter()


class StickerCmdFilter(tg_filters.MessageFilter):
    """Filter para comandos /sticker em texto."""
    def filter(self, message):
        if not message.text:
            return False
        return message.text.strip().lower().startswith("/sticker")


sticker_cmd_filter = StickerCmdFilter()


def _parse_sticker_args(args: list | None) -> dict:
    """Parse /sticker args: /sticker [emoji] [--bg] [--anim]

    Examples:
        /sticker          → static sticker, no bg removal
        /sticker 🤣       → static sticker with emoji
        /sticker --bg     → remove background
        /sticker --anim   → animated sticker (auto-detected for GIFs)
        /sticker --bg --anim  → animated + bg removal
        /sticker 🤣 --bg  → bg removal with emoji

    Note: Telegram mobile may replace -- with — (em dash U+2014), so we normalize.
    """
    result = {"emoji": "😂", "remove_bg": False, "animated": False}
    if not args:
        return result

    text = " ".join(args)

    for arg in args:
        # Normalize em dashes and en dashes to hyphens
        arg_clean = arg.replace('\u2014', '-').replace('\u2013', '-').replace('\u2212', '-')
        arg_lower = arg_clean.lower()
        if arg_lower in ("--bg", "-bg", "--nobg", "--remove-bg", "-nobg"):
            result["remove_bg"] = True
        elif arg_lower in ("--anim", "-anim"):
            result["animated"] = True
        else:
            # Check if it's an emoji
            for c in arg:
                if ord(c) > 0x2600 and ord(c) < 0x27BF or ord(c) > 0x1F600:
                    result["emoji"] = c
                    break

    return result


def _remove_bg_from_image(img: Image.Image) -> Image.Image:
    """Remove background from a PIL Image using rembg."""
    from rembg import remove
    output = remove(img)
    return output.convert("RGBA")


def _process_static_image(raw_bytes: bytes, remove_bg: bool = False) -> bytes | None:
    """Process a static image into 512x512 PNG bytes for sticker."""
    try:
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

        if remove_bg:
            img = _remove_bg_from_image(img)

        # Cover-resize: scale to fill 512x512, crop excess
        w, h = img.size
        ratio = max(512 / w, 512 / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        w, h = img.size
        left = (w - 512) // 2
        top = (h - 512) // 2
        img = img.crop((left, top, left + 512, top + 512))

        out = io.BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        return out.getvalue()
    except Exception as e:
        log.error(f"Static image processing error: {e}")
        return None


def _get_video_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=10
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def _process_animated(input_path: str, remove_bg: bool = False) -> bytes | None:
    """Convert GIF/video to animated WebM sticker.

    Telegram limits: max 3s, max 256KB, max 30FPS, VP9, no audio.
    If video is longer than 3s, it gets sped up to fit.
    If remove_bg=True, extracts frames, removes bg, and reassembles.
    Returns WebM bytes ready for upload.
    """
    MAX_DURATION = 3.0
    MAX_FILESIZE = 256 * 1024  # 256 KB

    try:
        output_path = input_path + ".webm"

        # Get original duration to calculate speed factor
        original_duration = _get_video_duration(input_path)
        speed_factor = max(1.0, original_duration / MAX_DURATION) if original_duration > MAX_DURATION else 1.0

        if speed_factor > 1.0:
            log.info(f"Video is {original_duration:.1f}s, speeding up {speed_factor:.1f}x to fit 3s")

        if remove_bg:
            # Extract frames, remove bg from each, reassemble as webm
            with tempfile.TemporaryDirectory() as tmpdir:
                # Extract frames, sped up if needed
                frames_pattern = os.path.join(tmpdir, "frame_%04d.png")
                subprocess.run(
                    ["ffmpeg", "-y", "-i", input_path,
                     "-t", str(min(original_duration, MAX_DURATION)),
                     "-vf", f"setpts=PTS/{speed_factor},fps=30,scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0",
                     frames_pattern],
                    capture_output=True, check=True, timeout=30
                )

                # Find extracted frames
                frames = sorted([f for f in os.listdir(tmpdir) if f.startswith("frame_") and f.endswith(".png")])
                if not frames:
                    log.error("No frames extracted")
                    return None

                # Remove bg from each frame
                from rembg import remove
                for fname in frames:
                    fpath = os.path.join(tmpdir, fname)
                    img = Image.open(fpath).convert("RGBA")
                    img = remove(img).convert("RGBA")
                    img.save(fpath, format="PNG")

                # Create input pattern for ffmpeg
                cleaned_pattern = os.path.join(tmpdir, "frame_%04d.png")

                # Reassemble as webm with transparent bg
                subprocess.run(
                    ["ffmpeg", "-y", "-framerate", "30", "-i", cleaned_pattern,
                     "-c:v", "libvpx-vp9", "-crf", "35", "-b:v", "0",
                     "-vf", "scale=512:512,format=rgba",
                     "-auto-alt-ref", "0",
                     "-pix_fmt", "yuva420p",
                     "-cpu-used", "8", "-row-mt", "1",
                     "-loop", "0",
                     output_path],
                    capture_output=True, check=True, timeout=60
                )
        else:
            # Direct conversion: GIF → WebM, speed up if needed
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path,
                 "-t", str(min(original_duration, MAX_DURATION)),
                 "-vf", f"setpts=PTS/{speed_factor},scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0,format=rgba",
                 "-c:v", "libvpx-vp9", "-crf", "35", "-b:v", "0",
                 "-an",
                 "-auto-alt-ref", "0",
                 "-pix_fmt", "yuva420p",
                 "-r", "30",
                 "-cpu-used", "8", "-row-mt", "1",
                 "-loop", "0",
                 output_path],
                capture_output=True, check=True, timeout=60
            )

        # Check file size and compress more if needed
        file_size = os.path.getsize(output_path)
        if file_size > MAX_FILESIZE:
            log.info(f"WebM is {file_size} bytes, re-encoding with higher CRF...")
            temp_path = output_path + ".tmp"
            os.rename(output_path, temp_path)
            subprocess.run(
                ["ffmpeg", "-y", "-i", temp_path,
                 "-c:v", "libvpx-vp9", "-crf", "50", "-b:v", "0",
                 "-an", "-auto-alt-ref", "0",
                 "-pix_fmt", "yuva420p",
                 "-cpu-used", "8", "-row-mt", "1",
                 "-loop", "0",
                 output_path],
                capture_output=True, check=True, timeout=60
            )
            os.unlink(temp_path)
            file_size = os.path.getsize(output_path)
            log.info(f"Re-encoded WebM: {file_size} bytes")

        if file_size > MAX_FILESIZE:
            log.warning(f"WebM still {file_size} bytes (max {MAX_FILESIZE}), may fail")

        with open(output_path, "rb") as f:
            return f.read()
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else ""
        log.error(f"FFmpeg error: {stderr}")
        return None
    except Exception as e:
        log.error(f"Animated processing error: {e}")
        return None
    finally:
        # Cleanup temp files
        for path in [output_path, output_path + ".tmp"]:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass


def _download_image(img_bytes_or_url: bytes | str) -> bytes | None:
    """Baixa imagem de bytes ou URL e retorna PNG bytes pronto pra sticker."""
    try:
        if isinstance(img_bytes_or_url, str):
            resp = req.get(img_bytes_or_url, timeout=15)
            resp.raise_for_status()
            raw = resp.content
        else:
            raw = img_bytes_or_url

        return _process_static_image(raw)
    except Exception as e:
        log.error(f"Image processing error: {e}")
        return None


def _upload_static_sticker(png_bytes: bytes, user_id: int, emoji: str) -> str | None:
    """Envia sticker estático pro pack do FakeGrok. Retorna link ou None."""
    url = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/addStickerToSet"
    files = {"png_sticker": ("sticker.png", png_bytes, "image/png")}
    data = {"user_id": str(user_id), "name": STICKER_SET_NAME, "emojis": emoji}

    resp = req.post(url, files=files, data=data, timeout=15).json()

    if resp.get("ok"):
        return f"https://t.me/addstickers/{STICKER_SET_NAME}"

    # Pack nao existe? Criar
    url2 = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/createNewStickerSet"
    files2 = {"png_sticker": ("sticker.png", png_bytes, "image/png")}
    data2 = {
        "user_id": str(user_id),
        "name": STICKER_SET_NAME,
        "title": STICKER_SET_TITLE,
        "emojis": emoji,
    }

    resp2 = req.post(url2, files=files2, data=data2, timeout=15).json()
    if resp2.get("ok"):
        return f"https://t.me/addstickers/{STICKER_SET_NAME}"

    return f"Erro: {resp.get('description', resp2.get('description', 'desconhecido'))}"


def _upload_animated_sticker(webm_bytes: bytes, user_id: int, emoji: str) -> str | None:
    """Envia sticker animado pro pack animado do FakeGrok. Retorna link ou None."""
    url = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/addStickerToSet"
    files = {"webm_sticker": ("sticker.webm", webm_bytes, "video/webm")}
    data = {"user_id": str(user_id), "name": ANIMATED_STICKER_SET_NAME, "emojis": emoji}

    resp = req.post(url, files=files, data=data, timeout=30).json()

    if resp.get("ok"):
        return f"https://t.me/addstickers/{ANIMATED_STICKER_SET_NAME}"

    # Pack nao existe? Criar
    url2 = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/createNewStickerSet"
    files2 = {"webm_sticker": ("sticker.webm", webm_bytes, "video/webm")}
    data2 = {
        "user_id": str(user_id),
        "name": ANIMATED_STICKER_SET_NAME,
        "title": ANIMATED_STICKER_SET_TITLE,
        "emojis": emoji,
    }

    resp2 = req.post(url2, files=files2, data=data2, timeout=30).json()
    if resp2.get("ok"):
        return f"https://t.me/addstickers/{ANIMATED_STICKER_SET_NAME}"

    return f"Erro: {resp.get('description', resp2.get('description', 'desconhecido'))}"


def _extract_url(text: str) -> str | None:
    """Extrai URL de um texto."""
    import re
    match = re.search(r'https?://\S+', text)
    return match.group(0) if match else None


async def _download_file(update_msg, file_obj) -> tuple[bytes, str | None]:
    """Download a telegram file and return (bytes, ext_hint)."""
    f = await file_obj.get_file()
    buf = io.BytesIO()
    await f.download_to_memory(buf)
    # Try to determine file type
    hint = None
    if hasattr(file_obj, 'mime_type') and file_obj.mime_type:
        mime = file_obj.mime_type
        if 'gif' in mime or 'webp' in mime:
            hint = 'animated'
        elif 'video' in mime:
            hint = 'animated'
    return buf.getvalue(), hint


async def sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cria sticker a partir de imagem/GIF anexada, respondida, ou URL.

    Flags:
        /sticker --bg      → remove background
        /sticker --anim    → animated sticker (auto-detected for GIFs)
        /sticker --bg --anim → animated + bg removal
    """
    user = update.effective_user
    message = update.message
    user_id = user.id if user else 1

    # Extract args from command text or caption
    if context.args:
        log.info(f"sticker args from command: {context.args}")
        args = _parse_sticker_args(context.args)
    else:
        # Came from MessageHandler (caption-based), parse from caption
        caption = message.caption or ""
        parts = caption.strip().split()
        log.info(f"sticker args from caption: caption='{caption}' parts={parts}")
        args = _parse_sticker_args(parts[1:] if len(parts) > 1 else None)

    # Auto-detect animated input (GIF/video always animated, no flag needed)
    is_animated_input = False
    input_bytes = None
    input_type = "static"  # static, animated, url
    input_type = "static"  # static, animated, url

    try:
        # 1. Imagem respondida (reply)
        if message.reply_to_message:
            replied = message.reply_to_message

            # Photo → static
            if replied.photo:
                f = await replied.photo[-1].get_file()
                buf = io.BytesIO()
                await f.download_to_memory(buf)
                input_bytes = buf.getvalue()
                input_type = "static"

            # Sticker → check if animated or static
            elif replied.sticker:
                if replied.sticker.is_animated or replied.sticker.is_video:
                    f = await replied.sticker.get_file()
                    buf = io.BytesIO()
                    await f.download_to_memory(buf)
                    input_bytes = buf.getvalue()
                    input_type = "animated"
                    is_animated_input = True
                else:
                    sf = await replied.sticker.get_file()
                    sbuf = io.BytesIO()
                    await sf.download_to_memory(sbuf)
                    input_bytes = sbuf.getvalue()
                    input_type = "static"

            # Animation (GIF) or Video → animated
            elif replied.animation or replied.video:
                media = replied.animation or replied.video
                f = await media.get_file()
                buf = io.BytesIO()
                await f.download_to_memory(buf)
                input_bytes = buf.getvalue()
                input_type = "animated"
                is_animated_input = True

            # Document (GIFs sometimes arrive as document)
            elif replied.document:
                mime = replied.document.mime_type or ""
                fname = (replied.document.file_name or "").lower()
                if "gif" in mime or "video" in mime or fname.endswith(".gif") or fname.endswith(".webm") or fname.endswith(".mp4"):
                    f = await replied.document.get_file()
                    buf = io.BytesIO()
                    await f.download_to_memory(buf)
                    input_bytes = buf.getvalue()
                    input_type = "animated"
                    is_animated_input = True
                else:
                    # Treat as static image
                    f = await replied.document.get_file()
                    buf = io.BytesIO()
                    await f.download_to_memory(buf)
                    input_bytes = buf.getvalue()
                    input_type = "static"

            # URL in replied text
            else:
                text = replied.text or replied.caption or ""
                url = _extract_url(text)
                if url:
                    resp = req.head(url, timeout=10, allow_redirects=True)
                    content_type = resp.headers.get("content-type", "")
                    if "gif" in content_type or "video" in content_type or "webm" in content_type:
                        input_type = "animated"
                        is_animated_input = True
                    input_bytes = None  # Will download in URL handler below
                else:
                    await reply_text_safe(
                        message, "Responde a uma imagem, GIF, sticker ou URL.",
                        message_type="error", save_to_db=False,
                    )
                    return

        # 2. Foto/Animation/Video na mesma mensagem
        elif message.photo:
            photo = message.photo[-1]
            f = await photo.get_file()
            buf = io.BytesIO()
            await f.download_to_memory(buf)
            input_bytes = buf.getvalue()
            input_type = "static"

        elif message.animation or message.video:
            media = message.animation or message.video
            f = await media.get_file()
            buf = io.BytesIO()
            await f.download_to_memory(buf)
            input_bytes = buf.getvalue()
            input_type = "animated"
            is_animated_input = True

        elif message.document:
            mime = message.document.mime_type or ""
            fname = (message.document.file_name or "").lower()
            if "gif" in mime or "video" in mime or fname.endswith(".gif") or fname.endswith(".webm") or fname.endswith(".mp4"):
                f = await message.document.get_file()
                buf = io.BytesIO()
                await f.download_to_memory(buf)
                input_bytes = buf.getvalue()
                input_type = "animated"
                is_animated_input = True

        # 3. URL no texto do comando
        else:
            text_parts = []
            if context.args:
                text_parts.extend(context.args)
            if message.caption:
                text_parts.append(message.caption)
            text = " ".join(text_parts)
            url = _extract_url(text)
            if url:
                resp = req.head(url, timeout=10, allow_redirects=True)
                content_type = resp.headers.get("content-type", "")
                if "gif" in content_type or "video" in content_type or "webm" in content_type:
                    input_type = "animated"
                    is_animated_input = True
                else:
                    input_type = "url"
            else:
                await reply_text_safe(
                    message,
                    "Usa assim:\n• `/sticker` + imagem\n• `/sticker` + GIF\n• `/sticker` + URL\n• `/sticker --bg` pra remover fundo\n• `/sticker --anim` pra sticker animado\n• Responde imagem/GIF com `/sticker`",
                    message_type="error",
                    parse_mode="markdown",
                    save_to_db=False,
                )
                return

        status = await reply_text_safe(
            message, "Criando sticker... 🎨", message_type="status", save_to_db=False,
        )

        log.info(f"sticker: type={input_type}, animated={is_animated_input}, bg={args['remove_bg']}, emoji={args['emoji']}")

        result = None

        if is_animated_input:
            # Download if needed
            if not input_bytes and input_type == "url":
                url = _extract_url(" ".join(context.args or []))
                if url:
                    resp = req.get(url, timeout=30)
                    input_bytes = resp.content
                    input_type = "animated"

            if not input_bytes:
                await status.edit_text("❌ Não consegui baixar o arquivo.")
                return

            # Save to temp file for ffmpeg
            with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
                tmp.write(input_bytes)
                tmp_path = tmp.name

            try:
                webm_bytes = _process_animated(tmp_path, remove_bg=args["remove_bg"])
                if webm_bytes:
                    result = _upload_animated_sticker(webm_bytes, user_id, args["emoji"])
                else:
                    await status.edit_text("❌ Não consegui processar o vídeo/GIF.")
                    return
            finally:
                os.unlink(tmp_path)
                # Clean up ffmpeg output
                output_path = tmp_path + ".webm"
                if os.path.exists(output_path):
                    os.unlink(output_path)
        else:
            # Static sticker
            if not input_bytes and input_type == "url":
                url = _extract_url(" ".join(context.args or []))
                if url:
                    png_bytes = _download_image(url)
                else:
                    png_bytes = None
            else:
                png_bytes = _process_static_image(input_bytes, remove_bg=args["remove_bg"])

            if not png_bytes:
                await status.edit_text("❌ Não consegui processar a imagem.")
                return

            result = _upload_static_sticker(png_bytes, user_id, args["emoji"])

        if result and not result.startswith("Erro"):
            if is_animated_input:
                await status.edit_text(
                    f"✅ Sticker animado adicionado!\n📁 [FakeGrok Animados]({result}) {args['emoji']}",
                    parse_mode="markdown"
                )
            else:
                suffix = " (sem fundo)" if args["remove_bg"] else ""
                await status.edit_text(
                    f"✅ Sticker adicionado{suffix}!\n📁 [FakeGrok Pack]({result}) {args['emoji']}",
                    parse_mode="markdown"
                )
        else:
            await status.edit_text(f"❌ {result}")

    except Exception as e:
        log.error(f"sticker handler error: {e}", exc_info=True)
        await reply_text_safe(
            message, f"❌ Erro: {str(e)}", message_type="error", save_to_db=False,
        )


def _delete_sticker_from_set(sticker_file_id: str) -> str:
    """Deleta um sticker do pack via file_id."""
    url = f"{TELEGRAM_API}/bot{FAKEGROK_TOKEN}/deleteStickerFromSet"
    data = {"sticker": sticker_file_id}
    resp = req.post(url, data=data, timeout=15).json()
    if resp.get("ok"):
        return "✅ Sticker removido do pack!"
    return f"❌ Erro: {resp.get('description', 'desconhecido')}"


async def delete_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove sticker do pack. Responde a um sticker com /delsticker."""
    message = update.message

    if not message.reply_to_message or not message.reply_to_message.sticker:
        await reply_text_safe(
            message, "Responde a um sticker com /delsticker pra remover do pack.",
            message_type="error", save_to_db=False,
        )
        return

    sticker = message.reply_to_message.sticker
    if not sticker.file_id:
        await reply_text_safe(
            message, "❌ Não consegui identificar o sticker.",
            message_type="error", save_to_db=False,
        )
        return

    status = await reply_text_safe(
        message, "Removendo sticker... 🗑️", message_type="status", save_to_db=False,
    )

    result = _delete_sticker_from_set(sticker.file_id)
    await status.edit_text(result)

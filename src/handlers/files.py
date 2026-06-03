from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from aiogram import F
from aiogram.types import Message

from src.logging_config import get_logger
from src.utils.file_utils import save_file_direct_streaming, save_file_gzip_streaming

logger = get_logger(__name__)

# File buffer storage: {user_id: [{"file_id": str, "filename": str, "file_size": int, "type": str}]}
file_buffer = defaultdict(list)

# Image format detection by magic bytes
IMAGE_MAGIC_BYTES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",  # WEBP starts with RIFF....WEBP
    b"\x00\x00\x00\x0cJXR ": ".jxr",
    b"\x00\x00\x00 ftypavif": ".avif",
    b"\x00\x00\x00 ftypheic": ".heic",
}


def detect_image_format(file_path: Path) -> str:
    """Detect image format by reading magic bytes."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
        for magic, ext in IMAGE_MAGIC_BYTES.items():
            if header.startswith(magic):
                return ext
        # Default to jpg if unknown
        return ".jpg"
    except Exception:
        return ".jpg"


COMPRESSED_EXTENSIONS = {
    ".gz",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".bz2",
    ".xz",
    ".tgz",
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".deb",
    ".rpm",
    ".apk",
    ".iso",
}


def is_already_compressed(filename: str) -> bool:
    """Check if file has a compressed extension."""
    filename_lower = filename.lower()
    for ext in COMPRESSED_EXTENSIONS:
        if filename_lower.endswith(ext):
            return True
    return False


async def process_file_in_background(
    message: Message,
    source_path: Path,
    prefix: str,
    original_filename: str,
    user_id: int,
    download_dir: Path,
    max_file_size: int,
) -> None:
    """Background task to compress and save file using streaming."""
    try:
        if is_already_compressed(original_filename):
            logger.info("File already compressed", filename=original_filename)
            filename = await save_file_direct_streaming(
                source_path, prefix, download_dir, original_filename
            )
        else:
            filename = await save_file_gzip_streaming(
                source_path, prefix, download_dir, original_filename
            )
        await message.reply(f"✅ File saved: {filename}")
        logger.info("File saved", user_id=user_id, filename=filename)
    except Exception as e:
        logger.error("Background processing failed", user_id=user_id, error=str(e))
        await message.reply("❌ Failed to save file")
    finally:
        # Clean up temp file
        if source_path.exists():
            source_path.unlink()


async def handle_file(
    message: Message,
    user_data: tuple[str, ...],
    download_dir: Path,
    max_file_size: int,
) -> None:
    """Handle incoming files - add to buffer instead of immediate save."""
    file_id: str | None = None
    original_filename: str = ""
    file_size: int | None = None
    file_type: str = ""

    if message.document:
        file_id = message.document.file_id
        original_filename = message.document.file_name or "document"
        file_size = message.document.file_size
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        original_filename = "photo.jpg"  # Will be updated after download
        file_size = message.photo[-1].file_size
        file_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        original_filename = message.video.file_name or "video.mp4"
        file_size = message.video.file_size
        file_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        original_filename = message.audio.file_name or "audio.mp3"
        file_size = message.audio.file_size
        file_type = "audio"
    elif message.voice:
        file_id = message.voice.file_id
        original_filename = "voice.ogg"  # Voice messages don't have names
        file_size = message.voice.file_size
        file_type = "voice"
    elif message.animation:
        file_id = message.animation.file_id
        original_filename = message.animation.file_name or "animation.gif"
        file_size = message.animation.file_size
        file_type = "animation"

    if file_id:
        # Check file size limit
        if file_size and file_size > max_file_size:
            logger.info(
                "File too large",
                user_id=message.from_user.id,
                file_size=file_size,
            )
            await message.reply(
                f"❌ File too large. Maximum size is {max_file_size / (1024 * 1024 * 1024):.1f}GB."
            )
            return

        # Add to buffer instead of immediate save
        user_id = message.from_user.id
        file_buffer[user_id].append(
            {
                "file_id": file_id,
                "filename": original_filename,
                "file_size": file_size,
                "type": file_type,
            }
        )

        buffer_count = len(file_buffer[user_id])
        await message.reply(
            f"📎 Added to buffer ({buffer_count} file(s)). Use /drop to save all or /buffer to view."
        )
        logger.info(
            "File added to buffer",
            user_id=user_id,
            filename=original_filename,
            buffer_count=buffer_count,
        )


def register_file_handlers(dp: Any, download_dir: Path, max_file_size: int) -> None:
    """Register file handlers with the dispatcher."""

    async def file_handler(message: Message, **kwargs) -> None:
        """Wrapper to extract data from kwargs and pass to handle_file."""
        user_data = kwargs.get("user_data", ("", False))
        await handle_file(message, user_data, download_dir, max_file_size)

    dp.message.register(
        file_handler,
        F.document | F.photo | F.video | F.audio | F.voice | F.animation,
    )

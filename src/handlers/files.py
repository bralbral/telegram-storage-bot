from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from src.utils.file_utils import save_file_direct, save_file_gzip

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def register_file_handlers(dp: Any, download_dir: Path) -> None:
    """Register file handlers with the dispatcher."""

    def is_already_compressed(filename: str) -> bool:
        """Check if file has a compressed extension."""
        filename_lower = filename.lower()
        for ext in COMPRESSED_EXTENSIONS:
            if filename_lower.endswith(ext):
                return True
        return False

    async def process_file_in_background(
        message: Message,
        file_bytes: bytes,
        prefix: str,
        original_filename: str,
        user_id: int,
    ) -> None:
        """Background task to compress and save file."""
        try:
            if is_already_compressed(original_filename):
                logger.info(f"File already compressed: {original_filename}")
                filename = await save_file_direct(
                    file_bytes, prefix, download_dir, original_filename
                )
            else:
                filename = await save_file_gzip(
                    file_bytes, prefix, download_dir, original_filename
                )
            await message.reply(f"✅ File saved: {filename}")
            logger.info(f"File saved by user {user_id}: {filename}")
        except Exception as e:
            logger.error(f"Background processing failed for user {user_id}: {e}")
            await message.reply("❌ Failed to save file")

    async def handle_file(message: Message, user_data: tuple[str, ...]) -> None:
        """Handle incoming files - compress and save as gzip in background."""
        prefix = user_data[0] or ""
        file_id: str | None = None
        original_filename: str = ""
        file_size: int | None = None

        if message.document:
            file_id = message.document.file_id
            original_filename = message.document.file_name or "document"
            file_size = message.document.file_size
        elif message.photo:
            file_id = message.photo[-1].file_id
            original_filename = "photo.jpg"  # Photos don't have original names
            file_size = message.photo[-1].file_size
        elif message.video:
            file_id = message.video.file_id
            original_filename = message.video.file_name or "video.mp4"
            file_size = message.video.file_size
        elif message.audio:
            file_id = message.audio.file_id
            original_filename = message.audio.file_name or "audio.mp3"
            file_size = message.audio.file_size
        elif message.voice:
            file_id = message.voice.file_id
            original_filename = "voice.ogg"  # Voice messages don't have names
            file_size = message.voice.file_size
        elif message.animation:
            file_id = message.animation.file_id
            original_filename = message.animation.file_name or "animation.gif"
            file_size = message.animation.file_size

        if file_id:
            # Check file size limit (2GB)
            if file_size and file_size > MAX_FILE_SIZE:
                logger.info(
                    f"File too large for user {message.from_user.id}: {file_size} bytes"
                )
                await message.reply("❌ File too large. Maximum size is 2GB.")
                return
            try:
                file_info = await message.bot.get_file(file_id)
                file_path = file_info.file_path

                # Download file using the correct aiogram 3.x method
                destination = download_dir / f"temp_{file_id}"
                await message.bot.download_file(file_path, destination)

                # Read the downloaded file
                with open(destination, "rb") as f:
                    file_bytes = f.read()

                # Clean up temp file
                destination.unlink()

                # Send initial message
                await message.reply("⏳ Saving file...")

                # Process in background to not block the bot
                asyncio.create_task(
                    process_file_in_background(
                        message,
                        file_bytes,
                        prefix,
                        original_filename,
                        message.from_user.id,
                    )
                )
            except TelegramBadRequest as e:
                logger.error(
                    f"Telegram API error for file {file_id} from user {message.from_user.id}: {e}"
                )
                await message.reply("❌ File not available or too large")
            except FileNotFoundError as e:
                logger.error(
                    f"File not found after download for user {message.from_user.id}: {e}"
                )
                await message.reply("❌ Failed to process downloaded file")
            except Exception as e:
                logger.error(
                    f"Error handling file from user {message.from_user.id}: {e}"
                )
                await message.reply("❌ Failed to process file")

    dp.message.register(
        handle_file, F.document | F.photo | F.video | F.audio | F.voice | F.animation
    )

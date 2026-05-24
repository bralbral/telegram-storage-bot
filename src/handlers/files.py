from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiogram import F
from aiogram.types import Message

from utils.file_utils import save_file_gzip

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def register_file_handlers(dp: Any, download_dir: Path) -> None:
    """Register file handlers with the dispatcher."""

    async def handle_file(message: Message, user_data: tuple[str, ...]) -> None:
        """Handle incoming files - compress and save as gzip."""
        prefix = user_data[0] or ""
        file_id: str | None = None

        if message.document:
            file_id = message.document.file_id
        elif message.photo:
            file_id = message.photo[-1].file_id
        elif message.video:
            file_id = message.video.file_id
        elif message.audio:
            file_id = message.audio.file_id
        elif message.voice:
            file_id = message.voice.file_id
        elif message.animation:
            file_id = message.animation.file_id

        if file_id:
            try:
                file_info = await message.bot.get_file(file_id)
                file_bytes = await message.bot.download(file_info)

                if isinstance(file_bytes, bytes):
                    filename = await save_file_gzip(file_bytes, prefix, download_dir)
                    await message.answer(f"✅ File saved: {filename}")
                    logger.info(
                        f"File saved by user {message.from_user.id}: {filename}"
                    )
                else:
                    await message.answer("❌ Failed to download file")
                    logger.warning(
                        f"Failed to download file for user {message.from_user.id}"
                    )
            except Exception as e:
                logger.error(
                    f"Error handling file from user {message.from_user.id}: {e}"
                )
                await message.answer("❌ Failed to process file")

    dp.message.register(
        handle_file, F.document | F.photo | F.video | F.audio | F.voice | F.animation
    )

from __future__ import annotations

from pathlib import Path

from aiogram import F
from aiogram.types import Message

from utils.file_utils import save_file_gzip


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
            file_info = await message.bot.get_file(file_id)
            file_bytes = await message.bot.download(file_info)

            if isinstance(file_bytes, bytes):
                filename = await save_file_gzip(file_bytes, prefix, download_dir)
                await message.answer(f"✅ File saved: {filename}")
            else:
                await message.answer("❌ Failed to download file")

    dp.message.register(handle_file, F.document | F.photo | F.video | F.audio | F.voice | F.animation)
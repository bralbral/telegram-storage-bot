from pathlib import Path

from aiogram import F
from aiogram.types import Message

from utils.file_utils import save_file_gzip


async def handle_file(message: Message, user_data: tuple, download_dir: Path):
    """Handle incoming files - compress and save as gzip with prefix_timestamp_hash.gz format."""
    prefix = user_data[0] or ""

    file_id = None

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
        file = await message.bot.get_file(file_id)
        file_bytes = await message.bot.download(file)

        if isinstance(file_bytes, bytes):
            filename = await save_file_gzip(file_bytes, prefix, download_dir)
            await message.answer(f"✅ File saved: {filename}")
        else:
            await message.answer("❌ Failed to download file")


def register_file_handlers(dp, download_dir: Path):
    """Register file handlers with the dispatcher."""
    async def handler(message: Message, user_data: tuple):
        await handle_file(message, user_data, download_dir)

    dp.message.register(handler, F.document | F.photo | F.video | F.audio | F.voice | F.animation)
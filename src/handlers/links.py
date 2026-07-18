from __future__ import annotations

import asyncio
import re
from typing import Any

from aiogram import F
from aiogram.types import Message

from src.logging_config import get_logger
from src.services.file_service import FileService
from src.services.web_snapshot_service import WebSnapshotService

logger = get_logger(__name__)

URL_PATTERN = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


async def handle_link(
    message: Message,
    file_service: FileService,
    web_snapshot_service: WebSnapshotService,
) -> None:
    url = (message.text or "").strip()
    await message.reply("🌐 Opening page and creating a snapshot…")
    files = []
    try:
        files = await web_snapshot_service.snapshot(url)
        buffer_count = await file_service.add_files_to_buffer(
            message.from_user.id, files
        )
    except asyncio.CancelledError:
        raise
    except (ValueError, RuntimeError) as error:
        file_service.remove_local_files(files)
        await message.reply(f"❌ Could not save page: {error}")
        return

    names = ", ".join(file.filename for file in files)
    await message.reply(
        f"✅ Added to buffer: {names} ({buffer_count} file(s)).\n"
        "Use /drop to save all, /buffer to view, or /clear to empty the queue."
    )
    logger.info("Web page added to buffer", user_id=message.from_user.id, url=url)


def register_link_handlers(dp: Any) -> None:
    async def link_handler(message: Message, **kwargs) -> None:
        file_service = kwargs.get("file_service")
        web_snapshot_service = kwargs.get("web_snapshot_service")
        if file_service is None or web_snapshot_service is None:
            raise RuntimeError("Required services were not provided")
        task = asyncio.create_task(
            handle_link(message, file_service, web_snapshot_service)
        )
        file_service._running_tasks.add(task)
        task.add_done_callback(file_service._running_tasks.discard)

    dp.message.register(
        link_handler,
        F.text.func(lambda text: bool(text and URL_PATTERN.fullmatch(text.strip()))),
    )

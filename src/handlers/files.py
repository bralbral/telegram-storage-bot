from __future__ import annotations

from typing import Any

from aiogram import F
from aiogram.types import Message

from src.handlers.user import send_start_help
from src.logging_config import get_logger
from src.services.file_service import FileService
from src.utils.size_utils import bytes_to_gb

logger = get_logger(__name__)


async def handle_text_message(
    message: Message, file_service: FileService, prefix: str
) -> None:
    """Append a collected message or show help for ordinary text."""
    text = message.text
    if text is None:
        return

    try:
        if await file_service.append_text_collection(message.from_user.id, text):
            return
    except ValueError as e:
        await message.reply(f"❌ {e}")
        return

    await send_start_help(message, prefix)


async def handle_file(
    message: Message,
    user_data: tuple[str, ...],
    file_service: FileService,
    max_file_size: int,
) -> None:
    """Handle incoming files - add to buffer instead of immediate save."""
    file_info = file_service.extract_file_info(message)

    if file_info:
        # Check file size limit
        if file_info.file_size and file_info.file_size > max_file_size:
            logger.info(
                "File too large",
                user_id=message.from_user.id,
                file_size=file_info.file_size,
            )
            await message.reply(
                f"❌ File too large. Maximum size is {bytes_to_gb(max_file_size):.1f}GB."
            )
            return

        # Add to buffer
        user_id = message.from_user.id
        file_info_with_prefix = file_info.model_copy()
        try:
            buffer_count = await file_service.add_to_buffer(
                user_id, file_info_with_prefix
            )
        except (ValueError, RuntimeError) as e:
            await message.reply(f"❌ {e}")
            return

        await message.reply(
            f"📎 Added to buffer ({buffer_count} file(s)).\n"
            "Use /drop to save all, /buffer to view, or /clear to empty the queue."
        )
        logger.info(
            "File added to buffer",
            user_id=user_id,
            filename=file_info.filename,
            buffer_count=buffer_count,
        )


def register_file_handlers(
    dp: Any, file_service: FileService, max_file_size: int
) -> None:
    """Register file handlers with the dispatcher."""

    async def file_handler(message: Message, **kwargs) -> None:
        """Wrapper to extract data from kwargs and pass to handle_file."""
        user_data = kwargs.get("user_data", ("", False))
        file_service = kwargs.get("file_service")
        if file_service is None:
            raise RuntimeError("file_service not provided in kwargs")
        await handle_file(message, user_data, file_service, max_file_size)

    dp.message.register(
        file_handler,
        F.document | F.photo | F.video | F.audio | F.voice | F.animation,
    )

    async def text_file_handler(message: Message, **kwargs) -> None:
        file_service = kwargs.get("file_service")
        if file_service is None:
            raise RuntimeError("file_service not provided in kwargs")
        user_data = kwargs.get("user_data", ("", False))
        await handle_text_message(message, file_service, user_data[0] or "")

    dp.message.register(
        text_file_handler,
        F.text.func(
            lambda text: text is not None
            and not text.lstrip().startswith("/")
            and not text.strip().lower().startswith("docker pull ")
        ),
    )

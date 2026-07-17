from __future__ import annotations

import asyncio
import shlex
from typing import Any

from aiogram import F
from aiogram.types import Message
from pydantic import ValidationError

from src.logging_config import get_logger
from src.models.pip import PipDownloadInfo
from src.services.pip_service import PipService

logger = get_logger(__name__)

USAGE = (
    "Usage: <code>pip download --python 3.12 [--no-deps] [--only-binary] "
    "&lt;package&gt; [package...]</code>"
)


def parse_pip_download(text: str, prefix: str) -> PipDownloadInfo:
    """Parse a restricted pip-download message without executing shell input."""
    parts = shlex.split(text)
    if len(parts) < 5 or parts[:2] != ["pip", "download"]:
        raise ValueError(USAGE)
    try:
        python_index = parts.index("--python", 2)
    except ValueError as error:
        raise ValueError(USAGE) from error
    if python_index + 1 >= len(parts):
        raise ValueError(USAGE)
    no_deps = "--no-deps" in parts[2:]
    only_binary = "--only-binary" in parts[2:]
    option_indexes = {python_index, python_index + 1}
    requirements = [
        part
        for index, part in enumerate(parts[2:], start=2)
        if index not in option_indexes and part not in {"--no-deps", "--only-binary"}
    ]
    if any(requirement.startswith("--") for requirement in requirements):
        raise ValueError(USAGE)
    return PipDownloadInfo(
        python_version=parts[python_index + 1],
        requirements=requirements,
        include_dependencies=not no_deps,
        only_binary=only_binary,
        prefix=prefix,
    )


def register_pip_handlers(dp: Any, pip_service: PipService) -> None:
    """Register messages that download Python packages and dependencies."""

    async def handle_pip_download(
        message: Message, user_data: tuple[str, ...], pip_service: PipService
    ) -> None:
        try:
            request = parse_pip_download(message.text or "", user_data[0] or "")
        except (ValueError, ValidationError) as error:
            await message.reply(f"❌ {error}")
            return

        await message.reply(
            f"🐍 Downloading packages for Python {request.python_version}..."
        )
        try:
            archive_name = await pip_service.download_and_archive(request)
            await message.reply(f"✅ Python packages saved: {archive_name}")
        except asyncio.CancelledError:
            logger.info("Pip download cancelled", user_id=message.from_user.id)
            raise
        except Exception as error:
            logger.error(
                "Pip download failed",
                user_id=message.from_user.id,
                error=str(error),
                exc_info=True,
            )
            await message.reply(f"❌ Failed to download packages: {error}")

    async def text_handler(message: Message, **kwargs) -> None:
        pip_service = kwargs.get("pip_service")
        if pip_service is None:
            raise RuntimeError("pip_service not provided in kwargs")
        task = asyncio.create_task(
            handle_pip_download(message, kwargs.get("user_data", ("",)), pip_service)
        )
        pip_service._running_tasks.add(task)
        task.add_done_callback(pip_service._running_tasks.discard)

    dp.message.register(
        text_handler,
        F.text.func(
            lambda text: (
                text is not None and text.strip().lower().startswith("pip download ")
            )
        ),
    )

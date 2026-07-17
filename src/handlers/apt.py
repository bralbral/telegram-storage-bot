from __future__ import annotations

import asyncio
import shlex
from typing import Any

from aiogram import F
from aiogram.types import Message
from pydantic import ValidationError

from src.logging_config import get_logger
from src.models.apt import AptDownloadInfo
from src.services.apt_service import AptService

logger = get_logger(__name__)

USAGE = (
    "Usage: <code>apt download [--debian 10|11|12|13|10.x.y] "
    "[--snapshot YYYYMMDDTHHMMSSZ] [--no-deps] &lt;package&gt; [package...]</code>"
)


def _normalise_option_dashes(text: str) -> str:
    """Accept common typographic dashes pasted before command options."""
    return text.replace("—", "--").replace("–", "--").replace("−", "--")


def parse_apt_download(text: str, prefix: str) -> AptDownloadInfo:
    """Parse a restricted apt-download message without executing shell input."""
    parts = shlex.split(_normalise_option_dashes(text))
    if len(parts) < 3 or parts[:2] != ["apt", "download"]:
        raise ValueError(USAGE)

    def option_value(option: str) -> tuple[int | None, str | None]:
        if option not in parts[2:]:
            return None, None
        option_index = parts.index(option, 2)
        if option_index + 1 >= len(parts):
            raise ValueError(USAGE)
        return option_index, parts[option_index + 1]

    debian_index, debian_version = option_value("--debian")
    snapshot_index, snapshot = option_value("--snapshot")
    no_deps = "--no-deps" in parts[2:]
    option_indexes = {
        index
        for option_index in (debian_index, snapshot_index)
        if option_index is not None
        for index in (option_index, option_index + 1)
    }
    packages = [
        part
        for index, part in enumerate(parts[2:], start=2)
        if index not in option_indexes and part != "--no-deps"
    ]
    if any(package.startswith("--") for package in packages):
        raise ValueError(USAGE)
    return AptDownloadInfo(
        debian_version=debian_version or "12",
        snapshot=snapshot,
        packages=packages,
        include_dependencies=not no_deps,
        prefix=prefix,
    )


def register_apt_handlers(dp: Any, apt_service: AptService) -> None:
    """Register messages that download Debian packages."""

    async def handle_apt_download(
        message: Message, user_data: tuple[str, ...], apt_service: AptService
    ) -> None:
        try:
            request = parse_apt_download(message.text or "", user_data[0] or "")
        except (ValueError, ValidationError) as error:
            await message.reply(f"❌ {error}")
            return

        await message.reply(
            f"📦 Downloading Debian {request.debian_version} packages..."
        )
        try:
            archive_name = await apt_service.download_and_archive(request)
            await message.reply(f"✅ Debian packages saved: {archive_name}")
        except asyncio.CancelledError:
            logger.info("Apt download cancelled", user_id=message.from_user.id)
            raise
        except Exception as error:
            logger.error(
                "Apt download failed",
                user_id=message.from_user.id,
                error=str(error),
                exc_info=True,
            )
            await message.reply(f"❌ Failed to download Debian packages: {error}")

    async def text_handler(message: Message, **kwargs) -> None:
        apt_service = kwargs.get("apt_service")
        if apt_service is None:
            raise RuntimeError("apt_service not provided in kwargs")
        task = asyncio.create_task(
            handle_apt_download(message, kwargs.get("user_data", ("",)), apt_service)
        )
        apt_service._running_tasks.add(task)
        task.add_done_callback(apt_service._running_tasks.discard)

    dp.message.register(
        text_handler,
        F.text.func(
            lambda text: (
                text is not None and text.strip().lower().startswith("apt download ")
            )
        ),
    )

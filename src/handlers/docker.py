from __future__ import annotations

import aiofiles
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiogram import F
from aiogram.types import Message

if TYPE_CHECKING:
    pass


def register_text_handlers(dp: Any, download_dir: Path) -> None:
    """Register text message handlers with the dispatcher."""

    async def handle_text(
        message: Message,
        user_data: tuple[str, ...],
        has_prefix: bool,
    ) -> None:
        """Handle text messages - detect and save Docker image links with prefix."""
        text = message.text.strip()

        docker_patterns = [
            "docker.io",
            "ghcr.io",
            "gcr.io",
            "quay.io",
            ".dkr.ecr.",
            "registry.gitlab.com",
            "docker pull",
        ]

        is_docker_link = any(p in text.lower() for p in docker_patterns)

        if is_docker_link:
            if not has_prefix:
                await message.answer("❌ Set your prefix first with /set_prefix")
                return

            prefix = user_data[0] or ""
            docker_file = download_dir / "docker_images.txt"

            async with aiofiles.open(docker_file, "a") as f:
                await f.write(f"{prefix}_{text}\n")
            await message.answer(f"🐳 Docker image saved: {text[:50]}...")
        else:
            await message.answer("📄 Please send a file or Docker image link.")

    dp.message.register(handle_text, F.text)
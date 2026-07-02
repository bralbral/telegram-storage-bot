from __future__ import annotations

import asyncio
import re
from typing import Any

from aiogram import F
from aiogram.types import Message

from src.logging_config import get_logger
from src.models.docker import DockerImageInfo
from src.services.docker_service import DockerService

logger = get_logger(__name__)

# Maximum Docker image name length
MAX_DOCKER_IMAGE_NAME_LENGTH = 128


def register_text_handlers(dp: Any, docker_service: DockerService) -> None:
    """Register text message handlers with the dispatcher."""

    async def handle_docker_pull(
        message: Message,
        docker_service: DockerService,
        image_info: DockerImageInfo,
    ) -> None:
        """Handle docker pull command."""
        try:
            # Cleanup before pull
            await docker_service.cleanup_before_pull(image_info.image_name)

            await message.reply(f"🐳 Downloading {image_info.image_name}...")
            gz_filename = await docker_service.pull_and_save_image(image_info)
            await message.reply(f"✅ Docker image saved: {gz_filename}")
            await logger.ainfo(
                "Docker image saved successfully",
                image_name=image_info.image_name,
                user_id=message.from_user.id,
                filename=gz_filename,
            )
        except Exception as e:
            await logger.aerror(
                "Error in docker pull",
                image_name=image_info.image_name,
                user_id=message.from_user.id,
                error=str(e),
                exc_info=True,
            )
            await message.reply(f"❌ Failed to download image: {e}")

    async def handle_text(
        message: Message,
        user_data: tuple[str, ...],
        docker_service: DockerService,
    ) -> None:
        """Handle text messages - detect docker pull commands."""
        text = message.text.strip()

        # Check for docker pull command
        docker_pull_pattern = r"^docker\s+pull\s+(.+)$"
        match = re.match(docker_pull_pattern, text, re.IGNORECASE)

        if match:
            image_name = match.group(1).strip()
            prefix = user_data[0] or ""

            # Validate image name (basic validation)
            if not image_name or len(image_name) > MAX_DOCKER_IMAGE_NAME_LENGTH:
                await message.answer("❌ Invalid Docker image name")
                return

            logger.info(
                "Processing docker pull",
                image_name=image_name,
            )

            # Create DockerImageInfo
            image_info = DockerImageInfo(image_name=image_name, prefix=prefix)

            # Process in background with task tracking
            task = asyncio.create_task(
                handle_docker_pull(message, docker_service, image_info)
            )
            docker_service._running_tasks.add(task)
            task.add_done_callback(lambda t: docker_service._running_tasks.discard(t))
        else:
            # Not a docker pull command, ignore
            pass

    async def text_handler(message: Message, **kwargs) -> None:
        """Wrapper to extract data from kwargs and pass to handle_text."""
        user_data = kwargs.get("user_data", ("", False))
        docker_service = kwargs.get("docker_service")
        if docker_service is None:
            raise RuntimeError("docker_service not provided in kwargs")
        await handle_text(message, user_data, docker_service)

    dp.message.register(text_handler, F.text)

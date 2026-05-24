from __future__ import annotations

import asyncio
import gzip
import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import docker
from aiogram import F
from aiogram.types import Message

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def register_text_handlers(dp: Any, download_dir: Path) -> None:
    """Register text message handlers with the dispatcher."""

    async def process_docker_pull(
        message: Message,
        image_name: str,
        prefix: str,
        user_id: int,
        download_dir: Path,
    ) -> None:
        """Background task to download Docker image using Docker SDK."""
        try:
            await message.reply(f"🐳 Downloading {image_name}...")

            # Ensure download directory exists
            download_dir.mkdir(parents=True, exist_ok=True)

            # Connect to Docker daemon
            client = docker.from_env()

            # Pull image
            logger.info(f"Pulling Docker image: {image_name}")
            await asyncio.to_thread(client.images.pull, image_name)
            logger.info(f"Image pulled successfully: {image_name}")

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            hash_part = hashlib.sha256(image_name.encode()).hexdigest()[:8]

            safe_image_name = image_name.replace("/", "_").replace(":", "_")
            tar_filename = (
                f"docker_{safe_image_name}_{prefix}_{timestamp}_{hash_part}.tar"
            )
            tar_filepath = download_dir / tar_filename

            # Save image as tar
            logger.info(f"Saving image to tar: {tar_filepath}")
            await asyncio.to_thread(
                save_with_dir_check, client, image_name, tar_filepath, download_dir
            )

            # Verify tar file exists
            if not tar_filepath.exists():
                logger.error(f"Tar file was not created: {tar_filepath}")
                await message.reply("❌ Failed to save image")
                return

            # Compress to gz using gzip.compress
            logger.info("Compressing tar file to gzip")
            gz_filename = f"{tar_filename}.gz"
            gz_filepath: Path = download_dir / gz_filename

            def compress_tar():
                with open(tar_filepath, "rb") as f_in:
                    tar_bytes = f_in.read()
                compressed = gzip.compress(tar_bytes)
                with open(gz_filepath, "wb") as f_out:
                    f_out.write(compressed)

            await asyncio.to_thread(compress_tar)

            # Clean up original tar file
            tar_filepath.unlink()
            logger.info("Original tar file deleted")

            # Remove Docker image to save space
            logger.info(f"Removing Docker image: {image_name}")
            try:
                await asyncio.to_thread(client.images.remove, image_name, force=True)
                logger.info(f"Image removed successfully: {image_name}")
            except Exception as e:
                logger.warning(f"Failed to remove image {image_name}: {e}")

            await message.reply(f"✅ Docker image saved: {gz_filename}")
            logger.info(f"Docker image saved by user {user_id}: {gz_filename}")

            # Close client
            client.close()
        except Exception as e:
            logger.error(f"Error processing docker pull for user {user_id}: {e}")
            await message.reply(f"❌ Failed to download image: {e}")

    def save_with_dir_check(
        client: docker.DockerClient,
        image_name: str,
        output_path: Path,
        download_dir: Path,
    ) -> None:
        """Save Docker image as tar with directory creation check."""
        # Ensure directory exists (same thread as file operation)
        download_dir.mkdir(parents=True, exist_ok=True)
        # Save the image
        image = client.images.get(image_name)
        with open(output_path, "wb") as f:
            for chunk in image.save():
                f.write(chunk)

    async def handle_text(
        message: Message,
        user_data: tuple[str, ...],
        has_prefix: bool,
    ) -> None:
        """Handle text messages - detect docker pull commands."""
        text = message.text.strip()

        # Check for docker pull command
        docker_pull_pattern = r"^docker\s+pull\s+(.+)$"
        match = re.match(docker_pull_pattern, text, re.IGNORECASE)

        if match:
            is_admin = user_data[1] if len(user_data) > 1 else False
            if not has_prefix and not is_admin:
                await message.answer("❌ Set your prefix first with /set_prefix")
                return

            image_name = match.group(1).strip()
            prefix = user_data[0] or ""

            # Validate image name (basic validation)
            if not image_name or len(image_name) > 128:
                await message.answer("❌ Invalid Docker image name")
                return

            # Process in background
            asyncio.create_task(
                process_docker_pull(
                    message, image_name, prefix, message.from_user.id, download_dir
                )
            )
        else:
            await message.answer("� Please send a file or docker pull command.")

    dp.message.register(handle_text, F.text)

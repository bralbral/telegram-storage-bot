from __future__ import annotations

import asyncio
import gzip
import logging
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import docker
from aiogram import F
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> Any:
    """Execute function with exponential backoff retry.

    Args:
        func: Function to execute (should be awaitable or sync)
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry

    Returns:
        Result of function execution

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = initial_delay * (backoff_factor**attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {max_retries} attempts failed")
                raise last_exception from None


def register_text_handlers(dp: Any, download_dir: Path, docker_host: str) -> None:
    """Register text message handlers with the dispatcher."""

    async def process_docker_pull(
        message: Message,
        image_name: str,
        prefix: str,
        user_id: int,
        download_dir: Path,
        docker_host: str,
    ) -> None:
        """Background task to download Docker image using Docker SDK."""
        client = None
        try:
            logger.info(f"Starting Docker image download for {image_name}")
            await message.reply(f"🐳 Downloading {image_name}...")

            # Ensure download directory exists
            download_dir.mkdir(parents=True, exist_ok=True)

            # Pull image with retry
            logger.info(
                f"Pulling Docker image: {image_name} using Docker host: {docker_host}"
            )

            # Use explicit base_url for reliable connection
            client = docker.DockerClient(base_url=docker_host)
            client.ping()
            logger.info("Successfully connected to Docker daemon")

            async def pull_with_retry():
                return await asyncio.to_thread(client.images.pull, image_name)

            await retry_with_backoff(pull_with_retry, max_retries=3)
            logger.info(f"Image pulled successfully: {image_name}")

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            uuid_part = uuid.uuid4().hex[:8]

            safe_image_name = image_name.replace("/", "_").replace(":", "_")
            tar_filename = f"{prefix}_{safe_image_name}_{timestamp}_{uuid_part}.tar"
            tar_filepath = download_dir / tar_filename

            # Save image as tar with retry
            logger.info(f"Saving image to tar: {tar_filepath}")

            async def save_with_retry():
                download_dir.mkdir(parents=True, exist_ok=True)
                image = client.images.get(image_name)
                with open(tar_filepath, "wb") as f:
                    for chunk in image.save():
                        f.write(chunk)

            await retry_with_backoff(save_with_retry, max_retries=2)
            logger.info(f"Image saved to tar: {tar_filepath}")

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

            # Remove Docker image to save space with retry
            logger.info(f"Removing Docker image: {image_name}")

            async def remove_with_retry():
                await asyncio.to_thread(client.images.remove, image_name, force=True)

            try:
                await retry_with_backoff(remove_with_retry, max_retries=2)
                logger.info(f"Image removed successfully: {image_name}")
            except Exception as e:
                logger.warning(
                    f"Failed to remove image {image_name} after retries: {e}"
                )

            await message.reply(f"✅ Docker image saved: {gz_filename}")
            logger.info(f"Docker image saved by user {user_id}: {gz_filename}")
        except Exception as e:
            logger.error(
                f"Error processing docker pull for user {user_id}: {e}", exc_info=True
            )
            await message.reply(f"❌ Failed to download image: {e}")
        finally:
            if client:
                client.close()

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
            image_name = match.group(1).strip()
            prefix = user_data[0] or ""

            # Validate image name (basic validation)
            if not image_name or len(image_name) > 128:
                await message.answer("❌ Invalid Docker image name")
                return

            # Process in background without task queue
            asyncio.create_task(
                process_docker_pull(
                    message,
                    image_name,
                    prefix,
                    message.from_user.id,
                    download_dir,
                    docker_host,
                )
            )
        else:
            await message.answer("❓ Please send a file or docker pull command.")

    dp.message.register(handle_text, F.text)

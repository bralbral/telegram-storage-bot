from __future__ import annotations

import asyncio
import gzip
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import docker
from aiogram import F
from aiogram.types import Message

from src.logging_config import get_logger

logger = get_logger(__name__)


def register_text_handlers(dp: Any, download_dir: Path, docker_host: str) -> None:
    """Register text message handlers with the dispatcher."""

    def process_docker_pull_sync(
        message: Message,
        image_name: str,
        prefix: str,
        user_id: int,
        download_dir: Path,
        docker_host: str,
    ) -> str:
        """Synchronous function to download Docker image using Docker SDK.

        Returns:
            The filename of the saved gz file

        Raises:
            Exception: If docker pull or processing fails
        """
        client = None
        try:
            logger.info(
                "Starting Docker image download",
                image_name=image_name,
                user_id=user_id,
            )

            # Ensure download directory exists
            download_dir.mkdir(parents=True, exist_ok=True)

            # Use explicit base_url for reliable connection
            client = docker.DockerClient(base_url=docker_host)
            client.ping()
            logger.info(
                "Successfully connected to Docker daemon", docker_host=docker_host
            )

            # Pull image with retry
            logger.info("Pulling Docker image", image=image_name)
            client.images.pull(image_name)
            logger.info("Image pulled successfully", image=image_name)

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            uuid_part = uuid.uuid4().hex[:8]

            safe_image_name = image_name.replace("/", "_").replace(":", "_")
            tar_filename = f"{prefix}_{safe_image_name}_{timestamp}_{uuid_part}.tar"
            tar_filepath = download_dir / tar_filename

            # Save image as tar
            logger.info("Saving image to tar", tar_filename=tar_filename)
            download_dir.mkdir(parents=True, exist_ok=True)
            image = client.images.get(image_name)
            with open(tar_filepath, "wb") as f:
                for chunk in image.save():
                    f.write(chunk)
            logger.info("Image saved to tar", tar_filepath=str(tar_filepath))

            # Verify tar file exists
            if not tar_filepath.exists():
                logger.error("Tar file was not created", tar_filepath=str(tar_filepath))
                raise RuntimeError(f"Tar file was not created: {tar_filepath}")

            # Compress to gz using gzip.compress
            logger.info("Compressing tar file to gzip", tar_filename=tar_filename)
            gz_filename = f"{tar_filename}.gz"
            gz_filepath: Path = download_dir / gz_filename

            with open(tar_filepath, "rb") as f_in:
                tar_bytes = f_in.read()
            compressed = gzip.compress(tar_bytes)
            with open(gz_filepath, "wb") as f_out:
                f_out.write(compressed)

            # Clean up original tar file
            tar_filepath.unlink()
            logger.info("Original tar file deleted", tar_filename=tar_filename)

            # Remove Docker image to save space
            logger.info("Removing Docker image", image_name=image_name)
            try:
                client.images.remove(image_name, force=True)
                logger.info("Image removed successfully", image=image_name)
            except Exception as e:
                logger.warning("Failed to remove image", image=image_name, error=str(e))

            logger.info(
                "Docker image saved successfully",
                user_id=user_id,
                filename=gz_filename,
            )
            return gz_filename
        except Exception as e:
            logger.error(
                "Error processing docker pull",
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            raise
        finally:
            if client:
                client.close()

    async def process_docker_pull(
        message: Message,
        image_name: str,
        prefix: str,
        user_id: int,
        download_dir: Path,
        docker_host: str,
    ) -> None:
        """Async wrapper that runs sync function in thread pool."""
        try:
            await message.reply(f"🐳 Downloading {image_name}...")
            gz_filename = await asyncio.to_thread(
                process_docker_pull_sync,
                message,
                image_name,
                prefix,
                user_id,
                download_dir,
                docker_host,
            )
            await message.reply(f"✅ Docker image saved: {gz_filename}")
            await logger.ainfo(
                "Docker image saved successfully",
                image_name=image_name,
                user_id=user_id,
                filename=gz_filename,
            )
        except Exception as e:
            await logger.aerror(
                "Error in async wrapper for docker pull",
                image_name=image_name,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            await message.reply(f"❌ Failed to download image: {e}")
        finally:
            return None

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

            logger.info(
                "Processing docker pull",
                image_name=image_name,
                docker_host=docker_host,
            )

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

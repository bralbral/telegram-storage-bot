from __future__ import annotations

import asyncio
import gzip
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import docker

from src.logging_config import get_logger
from src.models.docker import DockerImageInfo

logger = get_logger(__name__)

# Chunk size for streaming operations (1MB)
DEFAULT_CHUNK_SIZE = 1024 * 1024


class DockerService:
    """Service for Docker image operations."""

    def __init__(
        self, docker_host: str, download_dir: Path, max_concurrent_operations: int = 1
    ) -> None:
        """Initialize Docker service.

        Args:
            docker_host: Docker daemon socket URL
            download_dir: Directory to save downloaded images
        """
        self.docker_host = docker_host
        self.download_dir = download_dir
        self._running_tasks: set[asyncio.Task] = set()
        self._image_locks: dict[str, asyncio.Lock] = {}
        self._operation_semaphore = asyncio.Semaphore(max_concurrent_operations)

    async def _run_tracked_task(self, sync_func, *args) -> Any:
        """Run a synchronous function in a tracked task.

        Args:
            sync_func: Synchronous function to run
            *args: Arguments to pass to the function

        Returns:
            Result of the function

        Raises:
            asyncio.CancelledError: If operation is cancelled during shutdown
        """
        task = asyncio.create_task(asyncio.to_thread(sync_func, *args))
        self._running_tasks.add(task)
        try:
            return await task
        finally:
            self._running_tasks.discard(task)

    def _pull_image_sync(self, image_name: str) -> None:
        """Synchronously pull Docker image.

        Args:
            image_name: Docker image name to pull

        Raises:
            docker.errors.APIError: If pull fails
        """
        client = docker.DockerClient(base_url=self.docker_host)
        try:
            logger.info("Pulling Docker image", image=image_name)
            client.images.pull(image_name)
            logger.info("Image pulled successfully", image=image_name)
        except docker.errors.APIError as e:
            logger.error("Docker pull API error", image=image_name, error=str(e))
            raise
        finally:
            client.close()

    def _save_image_sync(self, image_name: str, prefix: str) -> str:
        """Synchronously save Docker image as gz file.

        Args:
            image_name: Docker image name
            prefix: User prefix for filename

        Returns:
            Filename of the saved gz file

        Raises:
            Exception: If save fails
        """
        client = docker.DockerClient(base_url=self.docker_host)
        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)

            safe_image_name = image_name.replace("/", "_").replace(":", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            gz_filename = f"{prefix}_{timestamp}_{safe_image_name}.tar.gz"
            gz_filepath = Path(os.path.join(self.download_dir, gz_filename))
            temporary_path = gz_filepath.with_suffix(gz_filepath.suffix + ".part")

            # Stream the Docker tar straight into gzip: no full temporary tar on disk.
            logger.info("Saving and compressing Docker image", filename=gz_filename)
            image = client.images.get(image_name)
            try:
                with open(temporary_path, "wb") as f_out:
                    with gzip.GzipFile(fileobj=f_out, mode="wb") as gzip_file:
                        for chunk in image.save(named=True):
                            gzip_file.write(chunk)
                os.replace(temporary_path, gz_filepath)
            finally:
                temporary_path.unlink(missing_ok=True)

            return gz_filename
        except Exception as e:
            logger.error("Error saving Docker image", image=image_name, error=str(e))
            raise
        finally:
            client.close()

    def _cleanup_image_sync(self, image_name: str) -> None:
        """Synchronously remove Docker image.

        Args:
            image_name: Docker image name to remove
        """
        client = docker.DockerClient(base_url=self.docker_host)
        try:
            logger.info("Removing Docker image", image_name=image_name)
            client.images.remove(image_name, force=True)
            logger.info("Image removed successfully", image=image_name)
        except docker.errors.ImageNotFound:
            logger.debug("Docker image was not present", image=image_name)
        except Exception as e:
            logger.warning("Failed to remove image", image=image_name, error=str(e))
        finally:
            client.close()

    async def pull_and_save_image(self, image_info: DockerImageInfo) -> str:
        """Pull Docker image, save as gz, and cleanup.

        Args:
            image_info: Docker image information

        Returns:
            Filename of the saved gz file

        Raises:
            docker.errors.APIError: If pull fails
            Exception: If save fails
            asyncio.CancelledError: If operation is cancelled during shutdown
        """
        image_name = image_info.image_name
        prefix = image_info.prefix

        try:
            image_lock = self._image_locks.setdefault(image_name, asyncio.Lock())
            async with image_lock, self._operation_semaphore:
                await self._run_tracked_task(self._cleanup_image_sync, image_name)
                try:
                    await self._run_tracked_task(self._pull_image_sync, image_name)
                    gz_filename = await self._run_tracked_task(
                        self._save_image_sync, image_name, prefix
                    )
                finally:
                    await self._run_tracked_task(self._cleanup_image_sync, image_name)

            logger.info(
                "Docker image saved successfully",
                image_name=image_name,
                filename=gz_filename,
            )
            return gz_filename
        except asyncio.CancelledError:
            logger.info(
                "Docker operation cancelled during shutdown",
                image_name=image_name,
            )
            raise
        except Exception as e:
            logger.error(
                "Error processing docker pull",
                image_name=image_name,
                error=str(e),
                exc_info=True,
            )
            raise

    async def cancel_all_operations(self) -> None:
        """Cancel all running Docker operations for graceful shutdown."""
        if not self._running_tasks:
            return

        logger.info(f"Cancelling {len(self._running_tasks)} running Docker operations")
        for task in self._running_tasks:
            task.cancel()

        # Wait for tasks to be cancelled
        await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self._running_tasks.clear()
        logger.info("All Docker operations cancelled")

    async def ping(self) -> bool:
        """Check if Docker daemon is accessible.

        Returns:
            True if Docker daemon is accessible, False otherwise
        """

        def ping_sync() -> bool:
            client = docker.DockerClient(base_url=self.docker_host)
            try:
                client.ping()
                return True
            finally:
                client.close()

        try:
            return await asyncio.wait_for(asyncio.to_thread(ping_sync), timeout=2)
        except Exception:
            return False

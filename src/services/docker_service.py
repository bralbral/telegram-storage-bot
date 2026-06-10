from __future__ import annotations

import asyncio
import gzip
from pathlib import Path

import docker

from src.logging_config import get_logger
from src.models.docker import DockerImageInfo

logger = get_logger(__name__)


class DockerService:
    """Service for Docker image operations."""

    def __init__(self, docker_host: str, download_dir: Path) -> None:
        """Initialize Docker service.

        Args:
            docker_host: Docker daemon socket URL
            download_dir: Directory to save downloaded images
        """
        self.docker_host = docker_host
        self.download_dir = download_dir

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

            # Generate filename
            safe_image_name = image_name.replace("/", "_").replace(":", "_")
            tar_filename = f"{prefix}_{safe_image_name}.tar"
            tar_filepath = self.download_dir / tar_filename

            # Save image as tar
            logger.info("Saving image to tar", tar_filename=tar_filename)
            image = client.images.get(image_name)
            with open(tar_filepath, "wb") as f:
                for chunk in image.save():
                    f.write(chunk)
            logger.info("Image saved to tar", tar_filepath=str(tar_filepath))

            # Verify tar file exists
            if not tar_filepath.exists():
                logger.error("Tar file was not created", tar_filepath=str(tar_filepath))
                raise RuntimeError(f"Tar file was not created: {tar_filepath}")

            # Compress to gz using streaming to avoid OOM
            logger.info("Compressing tar file to gzip", tar_filename=tar_filename)
            gz_filename = f"{tar_filename}.gz"
            gz_filepath = self.download_dir / gz_filename

            chunk_size = 1024 * 1024  # 1MB chunks
            with open(tar_filepath, "rb") as f_in:
                with open(gz_filepath, "wb") as f_out:
                    gzip_file = gzip.GzipFile(fileobj=f_out, mode="wb")
                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break
                        gzip_file.write(chunk)
                    gzip_file.close()

            # Clean up original tar file
            tar_filepath.unlink()
            logger.info("Original tar file deleted", tar_filename=tar_filename)

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
        """
        image_name = image_info.image_name
        prefix = image_info.prefix

        try:
            # Pull image
            await asyncio.to_thread(self._pull_image_sync, image_name)

            # Save image
            gz_filename = await asyncio.to_thread(
                self._save_image_sync, image_name, prefix
            )

            # Cleanup image
            await asyncio.to_thread(self._cleanup_image_sync, image_name)

            logger.info(
                "Docker image saved successfully",
                image_name=image_name,
                filename=gz_filename,
            )
            return gz_filename
        except Exception as e:
            logger.error(
                "Error processing docker pull",
                image_name=image_name,
                error=str(e),
                exc_info=True,
            )
            raise

    async def cleanup_before_pull(self, image_name: str) -> None:
        """Clean up existing image before pull.

        Args:
            image_name: Docker image name to clean up
        """
        client = docker.DockerClient(base_url=self.docker_host)
        try:
            try:
                client.images.remove(image_name, force=True)
                logger.info("Cleaned up existing image before pull", image=image_name)
            except docker.errors.ImageNotFound:
                pass  # Image doesn't exist, that's fine
            except Exception as e:
                logger.warning(
                    "Failed to clean up existing image",
                    image=image_name,
                    error=str(e),
                )
        finally:
            client.close()

    async def ping(self) -> bool:
        """Check if Docker daemon is accessible.

        Returns:
            True if Docker daemon is accessible, False otherwise
        """
        try:
            client = docker.DockerClient(base_url=self.docker_host)
            client.ping()
            client.close()
            return True
        except Exception:
            return False

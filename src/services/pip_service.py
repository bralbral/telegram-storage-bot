from __future__ import annotations

import asyncio
import os
import re
import shutil
import tarfile
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import docker

from src.logging_config import get_logger
from src.models.pip import PipDownloadInfo

logger = get_logger(__name__)


class PipService:
    """Download Python wheels in an isolated, versioned Python container."""

    def __init__(
        self, docker_host: str, download_dir: Path, max_concurrent_operations: int = 1
    ) -> None:
        self.docker_host = docker_host
        self.download_dir = download_dir
        self._operation_semaphore = asyncio.Semaphore(max_concurrent_operations)
        self._image_locks: dict[str, asyncio.Lock] = {}
        self._running_tasks: set[asyncio.Task] = set()

    async def _run_tracked_task(self, sync_func, *args):
        task = asyncio.create_task(asyncio.to_thread(sync_func, *args))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)
        return await task

    @staticmethod
    def _archive_name(prefix: str, python_version: str, first_requirement: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        package_name, _, version = first_requirement.partition("==")
        package_name = package_name.split("[", maxsplit=1)[0]
        package_name = re.sub(r"[^A-Za-z0-9._-]+", "_", package_name)
        package_label = package_name
        if version:
            package_label = f"{package_name}-{version}"
        return (
            f"{prefix}_{timestamp}_python{python_version}_{package_label}_"
            f"{unique_id}.tar.gz"
        )

    def _download_and_archive_sync(self, request: PipDownloadInfo) -> str:
        image_name = f"python:{request.python_version}-slim"
        container = None
        job_dir: Path | None = None
        archive_path: Path | None = None
        client = docker.DockerClient(base_url=self.docker_host)

        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            job_dir = Path(
                tempfile.mkdtemp(prefix=".pip-download-", dir=self.download_dir)
            )
            os.chmod(job_dir, 0o777)
            temporary_download_dir = job_dir / "tmp"
            temporary_download_dir.mkdir()
            os.chmod(temporary_download_dir, 0o777)
            archive_name = self._archive_name(
                request.prefix, request.python_version, request.requirements[0]
            )
            archive_path = self.download_dir / archive_name

            logger.info(
                "Pulling Python image for package download",
                image=image_name,
                python_version=request.python_version,
            )
            try:
                client.images.remove(image_name, force=True)
            except docker.errors.ImageNotFound:
                pass
            client.images.pull(image_name)

            container = client.containers.create(
                image=image_name,
                command=[
                    "python",
                    "-m",
                    "pip",
                    "download",
                    "--dest",
                    "/output",
                    "--no-cache-dir",
                    *([] if request.include_dependencies else ["--no-deps"]),
                    *(["--only-binary=:all:"] if request.only_binary else []),
                    *request.requirements,
                ],
                name=f"storage-bot-pip-{uuid.uuid4().hex[:12]}",
                volumes={str(job_dir): {"bind": "/output", "mode": "rw"}},
                network_mode="bridge",
                read_only=True,
                environment={"TMPDIR": "/output/tmp"},
                labels={"storage-bot.operation": "pip-download"},
            )
            container.start()
            result = container.wait(timeout=300)
            if result["StatusCode"] != 0:
                output = container.logs(tail=30).decode(errors="replace").strip()
                raise RuntimeError(output or "pip download failed")

            wheel_files = [path for path in job_dir.iterdir() if path.is_file()]
            if not wheel_files:
                raise RuntimeError("pip download completed without creating files")

            temporary_archive_path = archive_path.with_suffix(
                archive_path.suffix + ".part"
            )
            try:
                with tarfile.open(temporary_archive_path, "w:gz") as archive:
                    for wheel_file in wheel_files:
                        archive.add(wheel_file, arcname=wheel_file.name)
                os.replace(temporary_archive_path, archive_path)
            finally:
                temporary_archive_path.unlink(missing_ok=True)

            logger.info(
                "Python packages downloaded",
                archive=archive_name,
                python_version=request.python_version,
                package_count=len(wheel_files),
            )
            return archive_name
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except docker.errors.NotFound:
                    pass
                except Exception as error:
                    logger.warning("Failed to remove pip container", error=str(error))
            try:
                client.images.remove(image_name, force=True)
            except docker.errors.ImageNotFound:
                pass
            except Exception as error:
                logger.warning("Failed to remove Python image", error=str(error))
            if job_dir is not None:
                shutil.rmtree(job_dir, ignore_errors=True)
            client.close()

    async def download_and_archive(self, request: PipDownloadInfo) -> str:
        """Download a package and dependencies as wheels, then archive them."""
        image_name = f"python:{request.python_version}-slim"
        image_lock = self._image_locks.setdefault(image_name, asyncio.Lock())
        async with image_lock, self._operation_semaphore:
            return await self._run_tracked_task(
                self._download_and_archive_sync, request
            )

    async def cancel_all_operations(self) -> None:
        for task in self._running_tasks:
            task.cancel()
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)

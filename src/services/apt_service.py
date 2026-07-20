from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import docker

from src.logging_config import get_logger
from src.models.apt import AptDownloadInfo

logger = get_logger(__name__)


@dataclass(frozen=True)
class AptTarget:
    """APT suite and repository selected for a requested Debian version."""

    image: str
    suite: str
    repository: str


DEBIAN_RELEASES = {
    "10": ("debian/eol:buster-slim", "buster"),
    "11": ("debian/eol:bullseye-slim", "bullseye"),
    "12": ("debian:bookworm-slim", "bookworm"),
    "13": ("debian:trixie-slim", "trixie"),
}
DEBIAN_POINT_RELEASE_SNAPSHOTS = {
    "10.0.0": "20190707T000000Z",
    "10.2.0": "20191117T000000Z",
}


class AptService:
    """Download Debian packages in a temporary, snapshot-pinned container."""

    def __init__(
        self,
        docker_host: str,
        download_dir: Path,
        max_concurrent_operations: int = 1,
        download_timeout: int = 86_400,
    ) -> None:
        self.docker_host = docker_host
        self.download_dir = download_dir
        self._operation_semaphore = asyncio.Semaphore(max_concurrent_operations)
        self.download_timeout = download_timeout
        self._image_locks: dict[str, asyncio.Lock] = {}
        self._running_tasks: set[asyncio.Task] = set()

    async def _run_tracked_task(self, sync_func, *args):
        task = asyncio.create_task(asyncio.to_thread(sync_func, *args))
        self._running_tasks.add(task)
        task.add_done_callback(self._running_tasks.discard)
        return await task

    @staticmethod
    def _archive_name(prefix: str, debian_version: str, first_package: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        package_name, _, version = first_package.partition("=")
        package_label = re.sub(r"[^A-Za-z0-9._-]+", "_", package_name)
        if version:
            version_label = re.sub(r"[^A-Za-z0-9._+:-]+", "_", version)
            package_label = f"{package_label}-{version_label}"
        return (
            f"{prefix}_{timestamp}_debian{debian_version}_{package_label}_"
            f"{unique_id}.tar.gz"
        )

    @staticmethod
    def _target(request: AptDownloadInfo) -> AptTarget:
        major_version = request.debian_version.split(".", maxsplit=1)[0]
        image, suite = DEBIAN_RELEASES[major_version]
        snapshot = request.snapshot or DEBIAN_POINT_RELEASE_SNAPSHOTS.get(
            request.debian_version
        )
        if request.debian_version.count(".") == 2 and snapshot is None:
            raise ValueError(
                f"Debian {request.debian_version} is not in the point-release catalog"
            )
        if snapshot:
            repository = f"http://snapshot.debian.org/archive/debian/{snapshot}/"
        elif major_version in {"10", "11"}:
            repository = "http://archive.debian.org/debian/"
        else:
            repository = "http://deb.debian.org/debian/"
        return AptTarget(image=image, suite=suite, repository=repository)

    @staticmethod
    def _command(request: AptDownloadInfo, target: AptTarget) -> list[str]:
        packages = " ".join(shlex.quote(package) for package in request.packages)
        source = (
            "deb [check-valid-until=no] "
            f"{target.repository} {target.suite} main contrib non-free"
        )
        apt_options = (
            "-o Dir::State::status=/tmp/apt-state/status "
            "-o Dir::State::lists=/tmp/apt-state/lists "
            "-o Dir::Cache::archives=/tmp/apt-packages"
        )
        download_command = (
            "apt-get -y --download-only --no-install-recommends"
            f" {apt_options} install {packages}"
            if request.include_dependencies
            else f"cd /tmp/apt-packages && apt-get {apt_options} download {packages}"
        )
        script = (
            "set -eu\n"
            f"printf '%s\\n' {shlex.quote(source)} > /etc/apt/sources.list\n"
            "rm -f /etc/apt/sources.list.d/*\n"
            "mkdir -p /tmp/apt-packages/partial /tmp/apt-state/lists/partial\n"
            ": > /tmp/apt-state/status\n"
            f"apt-get {apt_options} -o Acquire::Check-Valid-Until=false update\n"
            f"{download_command}\n"
            "cp /tmp/apt-packages/*.deb /output/\n"
        )
        return ["/bin/sh", "-ec", script]

    def _download_and_archive_sync(self, request: AptDownloadInfo) -> str:
        target = self._target(request)
        container = None
        job_dir: Path | None = None
        client = docker.DockerClient(base_url=self.docker_host)

        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            job_dir = Path(
                tempfile.mkdtemp(prefix=".apt-download-", dir=self.download_dir)
            )
            os.chmod(job_dir, 0o777)
            archive_name = self._archive_name(
                request.prefix, request.debian_version, request.packages[0]
            )
            archive_path = self.download_dir / archive_name

            try:
                client.images.remove(target.image, force=True)
            except docker.errors.ImageNotFound:
                pass
            logger.info(
                "Pulling Debian image for package download",
                image=target.image,
                debian_version=request.debian_version,
                snapshot=request.snapshot
                or DEBIAN_POINT_RELEASE_SNAPSHOTS.get(request.debian_version),
            )
            client.images.pull(target.image)

            container = client.containers.create(
                image=target.image,
                command=self._command(request, target),
                name=f"storage-bot-apt-{uuid.uuid4().hex[:12]}",
                volumes={str(job_dir): {"bind": "/output", "mode": "rw"}},
                network_mode="bridge",
                labels={"storage-bot.operation": "apt-download"},
            )
            container.start()
            result = container.wait(timeout=self.download_timeout)
            if result["StatusCode"] != 0:
                output = container.logs(tail=30).decode(errors="replace").strip()
                raise RuntimeError(output or "apt download failed")

            deb_files = sorted(job_dir.glob("*.deb"))
            if not deb_files:
                raise RuntimeError("apt download completed without creating .deb files")

            temporary_archive_path = archive_path.with_suffix(
                archive_path.suffix + ".part"
            )
            try:
                with tarfile.open(temporary_archive_path, "w:gz") as archive:
                    for deb_file in deb_files:
                        archive.add(deb_file, arcname=deb_file.name)
                os.replace(temporary_archive_path, archive_path)
            finally:
                temporary_archive_path.unlink(missing_ok=True)

            logger.info(
                "Debian packages downloaded",
                archive=archive_name,
                debian_version=request.debian_version,
                package_count=len(deb_files),
            )
            return archive_name
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except docker.errors.NotFound:
                    pass
                except Exception as error:
                    logger.warning("Failed to remove apt container", error=str(error))
            try:
                client.images.remove(target.image, force=True)
            except docker.errors.ImageNotFound:
                pass
            except Exception as error:
                logger.warning("Failed to remove Debian image", error=str(error))
            if job_dir is not None:
                shutil.rmtree(job_dir, ignore_errors=True)
            client.close()

    async def download_and_archive(self, request: AptDownloadInfo) -> str:
        """Download Debian packages and optionally their dependencies."""
        target = self._target(request)
        image_lock = self._image_locks.setdefault(target.image, asyncio.Lock())
        async with image_lock, self._operation_semaphore:
            return await self._run_tracked_task(
                self._download_and_archive_sync, request
            )

    async def cancel_all_operations(self) -> None:
        for task in self._running_tasks:
            task.cancel()
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)

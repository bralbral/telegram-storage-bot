from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

import aiofiles
import aiohttp

from src.logging_config import get_logger
from src.models.file_info import FileInfo

logger = get_logger(__name__)


@dataclass(frozen=True)
class WebSnapshotService:
    """Request rendered page snapshots from the isolated Playwright sidecar."""

    playwright_url: str
    snapshot_dir: Path
    timeout: int

    async def snapshot(self, url: str) -> list[FileInfo]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Send a complete http:// or https:// URL")

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{self.playwright_url.rstrip('/')}/snapshot", json={"url": url}
                ) as response:
                    payload = await response.json(content_type=None)
                    if response.status >= 400:
                        raise ValueError(
                            payload.get("error", "Could not save this page")
                        )
                job_id = payload.get("jobId")
                if not isinstance(job_id, str):
                    raise RuntimeError("Snapshot service returned no job ID")
                destination_dir = (self.snapshot_dir / job_id).resolve()
                if not destination_dir.is_relative_to(self.snapshot_dir.resolve()):
                    raise RuntimeError("Snapshot service returned an invalid job ID")
                destination_dir.mkdir(parents=True, exist_ok=True)
                try:
                    files = await self._download_artifacts(
                        session, payload, job_id, destination_dir
                    )
                except Exception:
                    await asyncio.to_thread(shutil.rmtree, destination_dir, True)
                    raise
                finally:
                    async with session.delete(
                        f"{self.playwright_url.rstrip('/')}/snapshots/{job_id}"
                    ) as cleanup_response:
                        await cleanup_response.read()
        except aiohttp.ClientError as error:
            logger.warning("Playwright sidecar unavailable", error=str(error))
            raise RuntimeError("Page snapshot service is unavailable") from error
        except asyncio.TimeoutError as error:
            raise RuntimeError("Page snapshot timed out") from error

        return files

    async def _download_artifacts(
        self,
        session: aiohttp.ClientSession,
        payload: dict,
        job_id: str,
        destination_dir: Path,
    ) -> list[FileInfo]:
        files: list[FileInfo] = []
        for artifact in payload.get("artifacts", []):
            filename = artifact.get("filename")
            if not isinstance(filename, str) or Path(filename).name != filename:
                raise RuntimeError("Snapshot service returned an invalid file path")
            path = (destination_dir / filename).resolve()
            if not path.is_relative_to(destination_dir):
                raise RuntimeError("Snapshot service returned an invalid file path")
            artifact_url = (
                f"{self.playwright_url.rstrip('/')}/artifacts/{job_id}/"
                f"{quote(filename)}"
            )
            async with session.get(artifact_url) as response:
                if response.status != 200:
                    raise RuntimeError("Snapshot service could not provide a file")
                async with aiofiles.open(path, "wb") as output:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await output.write(chunk)
            files.append(
                FileInfo(
                    file_id=str(path),
                    filename=filename,
                    file_size=path.stat().st_size,
                    file_type=artifact["file_type"],
                    source="local",
                )
            )
        if not files:
            raise RuntimeError("Page snapshot service returned no files")
        return files

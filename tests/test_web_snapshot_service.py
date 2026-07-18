from pathlib import Path
from types import SimpleNamespace

import pytest

import src.services.web_snapshot_service as web_snapshot_service
from src.handlers.links import handle_link
from src.models.file_info import FileInfo
from src.services.web_snapshot_service import WebSnapshotService

JOB_ID = "11111111-1111-1111-1111-111111111111"


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, body: bytes = b""):
        self.status = status
        self._payload = payload or {}
        self._body = body
        self.content = self

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def json(self, **_: object) -> dict:
        return self._payload

    async def read(self) -> bytes:
        return self._body

    async def iter_chunked(self, _: int):
        yield self._body


class FakeSession:
    def __init__(self, artifact_status: int = 200) -> None:
        self.artifact_status = artifact_status
        self.cleanup_urls: list[str] = []

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    def post(self, *_: object, **__: object) -> FakeResponse:
        return FakeResponse(
            200,
            {
                "jobId": JOB_ID,
                "artifacts": [{"filename": "page.html", "file_type": "web_html"}],
            },
        )

    def get(self, *_: object, **__: object) -> FakeResponse:
        return FakeResponse(self.artifact_status, body=b"<h1>Saved page</h1>")

    def delete(self, url: str, **_: object) -> FakeResponse:
        self.cleanup_urls.append(url)
        return FakeResponse(204)


class FakeOutputFile:
    def __init__(self, path: Path):
        self.path = path

    async def __aenter__(self) -> "FakeOutputFile":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def write(self, chunk: bytes) -> None:
        self.path.write_bytes(chunk)


@pytest.mark.asyncio
async def test_snapshot_downloads_html_and_deletes_remote_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = FakeSession()
    monkeypatch.setattr(
        web_snapshot_service.aiohttp, "ClientSession", lambda *_args, **_kwargs: session
    )
    monkeypatch.setattr(
        web_snapshot_service.aiofiles, "open", lambda path, _mode: FakeOutputFile(path)
    )
    service = WebSnapshotService("http://playwright", tmp_path / "snapshots", 5)

    files = await service.snapshot("https://example.com")

    assert len(files) == 1
    assert files[0].source == "local"
    assert Path(files[0].file_id).read_bytes() == b"<h1>Saved page</h1>"
    assert session.cleanup_urls == [f"http://playwright/snapshots/{JOB_ID}"]


@pytest.mark.asyncio
async def test_snapshot_removes_partial_files_when_artifact_download_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot_dir = tmp_path / "snapshots"
    session = FakeSession(artifact_status=500)
    monkeypatch.setattr(
        web_snapshot_service.aiohttp, "ClientSession", lambda *_args, **_kwargs: session
    )
    monkeypatch.setattr(
        web_snapshot_service.aiofiles, "open", lambda path, _mode: FakeOutputFile(path)
    )
    service = WebSnapshotService("http://playwright", snapshot_dir, 5)

    with pytest.raises(RuntimeError, match="could not provide a file"):
        await service.snapshot("https://example.com")

    assert not (snapshot_dir / JOB_ID).exists()
    assert session.cleanup_urls == [f"http://playwright/snapshots/{JOB_ID}"]


class FakeMessage:
    def __init__(self) -> None:
        self.text = "https://example.com"
        self.from_user = SimpleNamespace(id=100)
        self.replies: list[str] = []

    async def reply(self, text: str) -> None:
        self.replies.append(text)


class FakeFileService:
    def __init__(self) -> None:
        self.files: list[FileInfo] = []

    async def add_files_to_buffer(self, user_id: int, files: list[FileInfo]) -> int:
        assert user_id == 100
        self.files = files
        return len(files)

    def remove_local_files(self, files: list[FileInfo]) -> None:
        raise AssertionError(f"Unexpected cleanup: {files}")


class FakeSnapshotService:
    async def snapshot(self, url: str) -> list[FileInfo]:
        assert url == "https://example.com"
        return [
            FileInfo(
                file_id="/snapshots/job/page.html",
                filename="page.html",
                file_size=10,
                file_type="web_html",
                source="local",
            )
        ]


@pytest.mark.asyncio
async def test_link_handler_queues_snapshot_files() -> None:
    message = FakeMessage()
    file_service = FakeFileService()

    await handle_link(message, file_service, FakeSnapshotService())  # type: ignore[arg-type]

    assert [file.filename for file in file_service.files] == ["page.html"]
    assert message.replies[0].startswith("🌐")
    assert message.replies[-1].startswith("✅ Added to buffer: page.html")

import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.db.database import Database
from src.models.file_info import FileInfo
from src.services.compression_service import CompressionService
from src.services.file_service import FileService


class FakeBot:
    async def get_file(self, file_id: str) -> SimpleNamespace:
        return SimpleNamespace(file_path=file_id)

    async def download_file(self, file_path: str, destination: Path) -> None:
        Path(destination).write_text(file_path)


@pytest.mark.asyncio
async def test_only_one_archive_can_reserve_a_user_buffer(tmp_path: Path) -> None:
    database = Database(tmp_path / "storage.db")
    await database.init()
    service = FileService(
        CompressionService(),
        tmp_path,
        database,
        max_buffer_files=10,
        max_buffer_size=100,
    )
    await service.add_to_buffer(
        100,
        FileInfo(
            file_id="telegram-file",
            filename="file.txt",
            file_size=10,
            file_type="document",
        ),
    )

    assert len(await service.begin_archive(100)) == 1
    with pytest.raises(RuntimeError, match="already in progress"):
        await service.begin_archive(100)

    (
        archive_name,
        archived_count,
        failed_count,
    ) = await service.create_archive_from_buffer(
        100, "prefix", FakeBot(), await service.get_buffer(100)
    )
    assert archive_name.endswith(".tar.gz")
    assert (archived_count, failed_count) == (1, 0)
    assert await service.get_buffer(100) == []
    await database.close()


@pytest.mark.asyncio
async def test_buffer_limits_are_enforced(tmp_path: Path) -> None:
    database = Database(tmp_path / "storage.db")
    await database.init()
    service = FileService(
        CompressionService(),
        tmp_path,
        database,
        max_buffer_files=1,
        max_buffer_size=10,
    )
    file = FileInfo(file_id="a", filename="a.txt", file_size=10, file_type="document")
    await service.add_to_buffer(100, file)

    with pytest.raises(ValueError, match="Buffer limit"):
        await service.add_to_buffer(100, file)
    await database.close()


@pytest.mark.asyncio
async def test_text_message_is_archived_without_telegram_download(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "storage.db")
    await database.init()
    service = FileService(
        CompressionService(),
        tmp_path,
        database,
        max_buffer_files=10,
        max_buffer_size=1_000,
    )
    text = "Привет, это текст для архива."
    file_info = service.create_text_file_info(text)

    assert file_info.filename.startswith("text_")
    assert file_info.filename.endswith(".txt")
    assert file_info.file_size == len(text.encode("utf-8"))
    await service.add_text_to_buffer(100, file_info)

    buffer = await service.begin_archive(100)
    (
        archive_name,
        archived_count,
        failed_count,
    ) = await service.create_archive_from_buffer(100, "prefix", FakeBot(), buffer)

    assert (archived_count, failed_count) == (1, 0)
    with tarfile.open(tmp_path / archive_name, "r:gz") as archive:
        member = archive.getmember(file_info.filename)
        extracted_file = archive.extractfile(member)
        assert extracted_file is not None
        assert extracted_file.read().decode("utf-8") == text
    await database.close()


@pytest.mark.asyncio
async def test_text_collection_is_memory_only_and_has_a_size_limit(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "storage.db")
    await database.init()
    service = FileService(
        CompressionService(),
        tmp_path,
        database,
        max_buffer_files=10,
        max_buffer_size=1_000,
        max_text_collection_size=10,
    )

    await service.start_text_collection(100)
    assert await service.append_text_collection(100, "12345")
    with pytest.raises(ValueError, match="10 byte limit"):
        await service.append_text_collection(100, "123456")

    file_info, buffer_count = await service.finish_text_collection(100)
    assert file_info.content == "12345"
    assert buffer_count == 1
    assert len(await service.get_buffer(100)) == 1
    await database.close()


@pytest.mark.asyncio
async def test_local_snapshot_is_archived_and_removed(tmp_path: Path) -> None:
    database = Database(tmp_path / "storage.db")
    await database.init()
    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    snapshot = snapshot_dir / "page.html"
    snapshot.write_text("<h1>Saved page</h1>")
    service = FileService(
        CompressionService(), tmp_path, database, 10, 1_000, snapshot_dir=snapshot_dir
    )
    await service.add_to_buffer(
        100,
        FileInfo(
            file_id=str(snapshot),
            filename="page.html",
            file_size=snapshot.stat().st_size,
            file_type="web_html",
            source="local",
        ),
    )

    buffer = await service.begin_archive(100)
    (
        archive_name,
        archived_count,
        failed_count,
    ) = await service.create_archive_from_buffer(100, "prefix", FakeBot(), buffer)

    assert (archived_count, failed_count) == (1, 0)
    assert not snapshot.exists()
    with tarfile.open(tmp_path / archive_name, "r:gz") as archive:
        extracted = archive.extractfile("page.html")
        assert extracted is not None
        assert extracted.read() == b"<h1>Saved page</h1>"
    await database.close()

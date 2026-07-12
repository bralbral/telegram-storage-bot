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

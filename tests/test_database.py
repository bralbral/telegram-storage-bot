from pathlib import Path

import pytest

from src.db.database import Database


@pytest.mark.asyncio
async def test_buffered_files_persist_and_delete_selectively(tmp_path: Path) -> None:
    database = Database(tmp_path / "storage.db")
    await database.init()

    first_id = await database.add_buffered_file(100, "a", "first.txt", 10, "document")
    await database.add_buffered_file(100, "b", "second.txt", 20, "document")

    assert await database.get_buffer_stats(100) == (2, 30)
    await database.delete_buffered_files(100, [first_id])

    queued = await database.get_buffered_files(100)
    assert [(row[1], row[2]) for row in queued] == [("b", "second.txt")]
    await database.close()

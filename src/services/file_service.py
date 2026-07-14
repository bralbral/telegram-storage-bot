from __future__ import annotations

import asyncio
import os
import tarfile
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import Message

from src.db.database import Database
from src.logging_config import get_logger
from src.models.file_info import FileInfo
from src.services.compression_service import CompressionService
from src.utils.file_utils import detect_image_format
from src.utils.naming import generate_filename

logger = get_logger(__name__)


@dataclass(frozen=True)
class BufferedFile:
    """A persisted file queued for archive creation."""

    id: int | None
    file_info: FileInfo


class FileService:
    """Service for file operations including buffer management and archive creation."""

    def __init__(
        self,
        compression_service: CompressionService,
        download_dir: Path,
        database: Database,
        max_buffer_files: int,
        max_buffer_size: int,
        max_text_collection_size: int = 10 * 1024 * 1024,
    ) -> None:
        """Initialize file service.

        Args:
            compression_service: Compression service instance
            download_dir: Directory for saving files
        """
        self.compression_service = compression_service
        self.download_dir = download_dir
        self.database = database
        self.max_buffer_files = max_buffer_files
        self.max_buffer_size = max_buffer_size
        self.max_text_collection_size = max_text_collection_size
        self._user_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._archiving_users: set[int] = set()
        self._text_collections: dict[int, list[str]] = {}
        self._text_collection_sizes: dict[int, int] = {}
        self._text_files: defaultdict[int, list[FileInfo]] = defaultdict(list)
        # Track running archive tasks for graceful shutdown
        self._running_tasks: set[asyncio.Task] = set()

    async def add_to_buffer(self, user_id: int, file_info: FileInfo) -> int:
        """Add file to user's buffer.

        Args:
            user_id: User Telegram ID
            file_info: File information

        Returns:
            Number of files in buffer after adding
        """
        async with self._user_locks[user_id]:
            if user_id in self._archiving_users:
                raise RuntimeError("Archive creation is already in progress")
            buffer_count, buffer_size = await self.database.get_buffer_stats(user_id)
            if buffer_count >= self.max_buffer_files:
                raise ValueError(f"Buffer limit is {self.max_buffer_files} files")
            if buffer_size + (file_info.file_size or 0) > self.max_buffer_size:
                raise ValueError("Buffer size limit would be exceeded")
            await self.database.add_buffered_file(
                user_id,
                file_info.file_id,
                file_info.filename,
                file_info.file_size,
                file_info.file_type,
            )
            buffer_count += 1
        logger.info(
            "File added to buffer",
            user_id=user_id,
            filename=file_info.filename,
            buffer_count=buffer_count,
        )
        return buffer_count

    async def get_buffer(self, user_id: int) -> list[BufferedFile]:
        """Get user's buffer contents.

        Args:
            user_id: User Telegram ID

        Returns:
            List of files in buffer
        """
        rows = await self.database.get_buffered_files(user_id)
        buffered_files = [
            BufferedFile(
                id=row_id,
                file_info=FileInfo(
                    file_id=file_id,
                    filename=filename,
                    file_size=file_size,
                    file_type=file_type,
                ),
            )
            for row_id, file_id, filename, file_size, file_type in rows
        ]
        buffered_files.extend(
            BufferedFile(id=None, file_info=file_info)
            for file_info in self._text_files[user_id]
        )
        return buffered_files

    @staticmethod
    def create_text_file_info(text: str) -> FileInfo:
        """Create a buffered UTF-8 text file from a message body."""
        return FileInfo(
            file_id=uuid.uuid4().hex,
            filename=generate_filename("text", "txt"),
            file_size=len(text.encode("utf-8")),
            file_type="text",
            content=text,
        )

    async def add_text_to_buffer(self, user_id: int, file_info: FileInfo) -> int:
        """Queue a text file in memory only until the next archive is made."""
        if file_info.file_type != "text" or file_info.content is None:
            raise ValueError("Expected a text file with content")
        async with self._user_locks[user_id]:
            if user_id in self._archiving_users:
                raise RuntimeError("Archive creation is already in progress")
            buffer_count, buffer_size = await self.database.get_buffer_stats(user_id)
            text_files = self._text_files[user_id]
            text_size = sum(item.file_size or 0 for item in text_files)
            if buffer_count + len(text_files) >= self.max_buffer_files:
                raise ValueError(f"Buffer limit is {self.max_buffer_files} files")
            if (
                buffer_size + text_size + (file_info.file_size or 0)
                > self.max_buffer_size
            ):
                raise ValueError("Buffer size limit would be exceeded")
            text_files.append(file_info)
            return buffer_count + len(text_files)

    async def start_text_collection(self, user_id: int) -> None:
        """Start collecting consecutive messages into one text file."""
        async with self._user_locks[user_id]:
            if user_id in self._archiving_users:
                raise RuntimeError("Archive creation is already in progress")
            if user_id in self._text_collections:
                raise ValueError(
                    "Text collection is already active; use /endtext or /canceltext"
                )
            self._text_collections[user_id] = []
            self._text_collection_sizes[user_id] = 0

    async def append_text_collection(self, user_id: int, text: str) -> bool:
        """Append text to an active collection; return False when none is active."""
        text_size = len(text.encode("utf-8"))
        async with self._user_locks[user_id]:
            if user_id not in self._text_collections:
                return False
            separator_size = 1 if self._text_collections[user_id] else 0
            new_size = self._text_collection_sizes[user_id] + separator_size + text_size
            if new_size > self.max_text_collection_size:
                raise ValueError(
                    "Text collection would exceed the "
                    f"{self.max_text_collection_size} byte limit"
                )
            self._text_collections[user_id].append(text)
            self._text_collection_sizes[user_id] = new_size
            return True

    async def finish_text_collection(self, user_id: int) -> tuple[FileInfo, int]:
        """Turn an active text collection into one queued text file."""
        async with self._user_locks[user_id]:
            if user_id in self._archiving_users:
                raise RuntimeError("Archive creation is already in progress")
            parts = self._text_collections.get(user_id)
            if parts is None:
                raise ValueError("No active text collection. Use /text first")
            if not parts:
                raise ValueError("Text collection is empty")
            text = "\n".join(parts)
            del self._text_collections[user_id]
            del self._text_collection_sizes[user_id]

        file_info = self.create_text_file_info(text)
        try:
            buffer_count = await self.add_text_to_buffer(user_id, file_info)
        except (ValueError, RuntimeError):
            async with self._user_locks[user_id]:
                self._text_collections.setdefault(user_id, parts)
                self._text_collection_sizes.setdefault(
                    user_id, len(text.encode("utf-8"))
                )
            raise
        return file_info, buffer_count

    async def cancel_text_collection(self, user_id: int) -> int:
        """Discard an active text collection and return its part count."""
        async with self._user_locks[user_id]:
            parts = self._text_collections.pop(user_id, None)
            self._text_collection_sizes.pop(user_id, None)
            return len(parts) if parts is not None else 0

    async def clear_buffer(self, user_id: int) -> int:
        """Clear user's buffer.

        Args:
            user_id: User Telegram ID

        Returns:
            Number of files removed
        """
        async with self._user_locks[user_id]:
            if user_id in self._archiving_users:
                raise RuntimeError("Archive creation is already in progress")
            count = await self.database.clear_buffered_files(user_id)
            text_count = len(self._text_files.pop(user_id, []))
        logger.info("Buffer cleared", user_id=user_id, removed=count + text_count)
        return count + text_count

    @staticmethod
    def get_buffer_size(buffer: list[BufferedFile]) -> int:
        """Get total size of files in user's buffer.

        Args:
            user_id: User Telegram ID

        Returns:
            Total size in bytes
        """
        return sum(int(item.file_info.file_size or 0) for item in buffer)

    async def begin_archive(self, user_id: int) -> list[BufferedFile]:
        """Reserve a user's buffer so concurrent /drop and /clear cannot race."""
        async with self._user_locks[user_id]:
            if user_id in self._archiving_users:
                raise RuntimeError("Archive creation is already in progress")
            buffer = await self.get_buffer(user_id)
            if not buffer:
                raise ValueError("Buffer is empty")
            self._archiving_users.add(user_id)
            return buffer

    async def create_archive_from_buffer(
        self, user_id: int, prefix: str, bot: Bot, buffer: list[BufferedFile]
    ) -> tuple[str, int, int]:
        """Create tar.gz archive from user's buffer.

        Args:
            user_id: User Telegram ID
            prefix: User prefix for archive filename
            bot: Bot instance for downloading files

        Returns:
            Archive filename

        Raises:
            Exception: If archive creation fails
            asyncio.CancelledError: If operation is cancelled during shutdown
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uuid_part = uuid.uuid4().hex[:8]
        archive_name = f"{prefix}_{timestamp}_{uuid_part}.tar.gz"
        archive_path = Path(os.path.join(self.download_dir, archive_name))
        temporary_archive_path = archive_path.with_suffix(".tar.gz.part")
        successful_ids: list[int] = []
        successful_text_file_ids: list[str] = []
        successful_count = 0
        failed_count = 0

        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(temporary_archive_path, "w:gz") as tar:
                for buffered_file in buffer:
                    file_info = buffered_file.file_info
                    temp_path: Path | None = None
                    try:
                        if file_info.file_type == "text":
                            content = file_info.content
                            if content is None:
                                raise RuntimeError(
                                    "Text content is no longer available"
                                )
                            with tempfile.NamedTemporaryFile(
                                mode="w", encoding="utf-8", delete=False
                            ) as temp_file:
                                temp_file.write(content)
                                temp_path = Path(temp_file.name)
                        else:
                            tg_file = await bot.get_file(file_info.file_id)
                            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                                temp_path = Path(temp_file.name)
                            await bot.download_file(tg_file.file_path, temp_path)

                        filename = file_info.filename
                        if file_info.file_type == "photo":
                            filename = f"photo{detect_image_format(temp_path)}"
                        else:
                            filename = Path(filename).name or "file"

                        await asyncio.to_thread(tar.add, temp_path, arcname=filename)
                        successful_count += 1
                        if buffered_file.id is not None:
                            successful_ids.append(buffered_file.id)
                        if file_info.file_type == "text":
                            successful_text_file_ids.append(file_info.file_id)

                    except Exception as e:
                        failed_count += 1
                        logger.error(
                            "Failed to process file in buffer",
                            file_id=file_info.file_id,
                            error=str(e),
                        )
                    finally:
                        if temp_path is not None:
                            temp_path.unlink(missing_ok=True)

            if not successful_count:
                raise RuntimeError("None of the queued files could be archived")

            os.replace(temporary_archive_path, archive_path)
            await self.database.delete_buffered_files(user_id, successful_ids)
            if successful_text_file_ids:
                successful_text_ids = set(successful_text_file_ids)
                self._text_files[user_id] = [
                    file_info
                    for file_info in self._text_files[user_id]
                    if file_info.file_id not in successful_text_ids
                ]

            logger.info(
                "Archive created from buffer",
                user_id=user_id,
                archive=archive_name,
                count=successful_count,
            )
            return archive_name, successful_count, failed_count

        except Exception as e:
            logger.error(
                "Failed to create archive from buffer",
                user_id=user_id,
                error=str(e),
            )
            raise
        finally:
            temporary_archive_path.unlink(missing_ok=True)
            self._archiving_users.discard(user_id)

    def extract_file_info(self, message: Message) -> FileInfo | None:
        """Extract file information from Telegram message.

        Args:
            message: Telegram message

        Returns:
            FileInfo if message contains a file, None otherwise
        """
        # File type mapping: (attribute_name, default_filename, file_type)
        file_types = [
            ("document", "document", "document"),
            ("photo", "photo.jpg", "photo"),
            ("video", "video.mp4", "video"),
            ("audio", "audio.mp3", "audio"),
            ("voice", "voice.ogg", "voice"),
            ("animation", "animation.gif", "animation"),
        ]

        for attr_name, default_filename, file_type in file_types:
            attr = getattr(message, attr_name, None)
            if not attr:
                continue

            # Handle photo array
            if attr_name == "photo":
                attr = attr[-1]

            file_id = attr.file_id
            file_size = attr.file_size

            # Get filename if available
            if hasattr(attr, "file_name") and attr.file_name:
                original_filename = attr.file_name
            else:
                original_filename = default_filename

            return FileInfo(
                file_id=file_id,
                filename=original_filename,
                file_size=file_size,
                file_type=file_type,
            )

        return None

    async def process_file(
        self,
        source_path: Path,
        prefix: str,
        original_filename: str,
        download_dir: Path,
    ) -> str:
        """Process and save file (compress or direct save).

        Args:
            source_path: Path to the source file
            prefix: User prefix for filename
            original_filename: Original filename
            download_dir: Directory to save file

        Returns:
            Saved filename
        """
        try:
            if self.compression_service.is_already_compressed(original_filename):
                logger.info("File already compressed", filename=original_filename)
                filename = await self.compression_service.save_direct_streaming(
                    source_path, prefix, download_dir, original_filename
                )
            else:
                filename = await self.compression_service.compress_gzip_streaming(
                    source_path, prefix, download_dir, original_filename
                )
            logger.info("File saved", filename=filename)
            return filename
        except Exception as e:
            logger.error("File processing failed", error=str(e))
            raise
        finally:
            # Clean up temp file
            if source_path.exists():
                source_path.unlink()

    async def cancel_all_operations(self) -> None:
        """Cancel all running archive operations for graceful shutdown."""
        self._text_collections.clear()
        self._text_collection_sizes.clear()
        self._text_files.clear()
        if not self._running_tasks:
            return

        logger.info(f"Cancelling {len(self._running_tasks)} running archive operations")
        for task in self._running_tasks:
            task.cancel()

        # Wait for tasks to be cancelled
        await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self._running_tasks.clear()
        logger.info("All archive operations cancelled")

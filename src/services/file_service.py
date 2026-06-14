from __future__ import annotations

import os
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path

from aiogram import Bot
from aiogram.types import Message

from src.logging_config import get_logger
from src.models.file_info import FileInfo
from src.services.compression_service import CompressionService
from src.utils.file_utils import detect_image_format

logger = get_logger(__name__)


class FileService:
    """Service for file operations including buffer management and archive creation."""

    def __init__(
        self,
        compression_service: CompressionService,
        download_dir: Path,
    ) -> None:
        """Initialize file service.

        Args:
            compression_service: Compression service instance
            download_dir: Directory for saving files
        """
        self.compression_service = compression_service
        self.download_dir = download_dir
        # File buffer storage: {user_id: [FileInfo]}
        self.file_buffer: dict[int, list[FileInfo]] = defaultdict(list)

    def add_to_buffer(self, user_id: int, file_info: FileInfo) -> int:
        """Add file to user's buffer.

        Args:
            user_id: User Telegram ID
            file_info: File information

        Returns:
            Number of files in buffer after adding
        """
        self.file_buffer[user_id].append(file_info)
        buffer_count = len(self.file_buffer[user_id])
        logger.info(
            "File added to buffer",
            user_id=user_id,
            filename=file_info.filename,
            buffer_count=buffer_count,
        )
        return buffer_count

    def get_buffer(self, user_id: int) -> list[FileInfo]:
        """Get user's buffer contents.

        Args:
            user_id: User Telegram ID

        Returns:
            List of files in buffer
        """
        return self.file_buffer.get(user_id, [])

    def clear_buffer(self, user_id: int) -> int:
        """Clear user's buffer.

        Args:
            user_id: User Telegram ID

        Returns:
            Number of files removed
        """
        count = len(self.file_buffer.get(user_id, []))
        self.file_buffer[user_id] = []
        logger.info("Buffer cleared", user_id=user_id, removed=count)
        return count

    def get_buffer_size(self, user_id: int) -> int:
        """Get total size of files in user's buffer.

        Args:
            user_id: User Telegram ID

        Returns:
            Total size in bytes
        """
        buffer = self.file_buffer.get(user_id, [])
        return sum(int(f.file_size or 0) for f in buffer)

    async def create_archive_from_buffer(
        self, user_id: int, prefix: str, bot: Bot
    ) -> str:
        """Create tar.gz archive from user's buffer.

        Args:
            user_id: User Telegram ID
            prefix: User prefix for archive filename
            bot: Bot instance for downloading files

        Returns:
            Archive filename

        Raises:
            Exception: If archive creation fails
        """
        import uuid
        from datetime import datetime

        buffer = self.file_buffer.get(user_id, [])

        if not buffer:
            raise ValueError("Buffer is empty")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uuid_part = uuid.uuid4().hex[:8]
        archive_name = f"{prefix}_{timestamp}_{uuid_part}.tar.gz"
        archive_path = Path(os.path.join(self.download_dir, archive_name))

        try:
            # Create tar.gz archive
            with tarfile.open(archive_path, "w:gz") as tar:
                for file_info in buffer:
                    try:
                        tg_file = await bot.get_file(file_info.file_id)
                        # Download to temp file
                        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                            await bot.download_file(tg_file.file_path, temp_file.name)

                            # Detect image format for photos
                            filename = file_info.filename
                            if file_info.file_type == "photo":
                                ext = detect_image_format(Path(temp_file.name))
                                filename = f"photo{ext}"

                            # Add to archive
                            tar.add(temp_file.name, arcname=filename)
                            Path(temp_file.name).unlink()  # Clean up temp file

                    except Exception as e:
                        logger.error(
                            "Failed to process file in buffer",
                            file_id=file_info.file_id,
                            error=str(e),
                        )

            # Clear buffer
            self.file_buffer[user_id] = []

            logger.info(
                "Archive created from buffer",
                user_id=user_id,
                archive=archive_name,
                count=len(buffer),
            )
            return archive_name

        except Exception as e:
            logger.error(
                "Failed to create archive from buffer",
                user_id=user_id,
                error=str(e),
            )
            raise

    def extract_file_info(self, message: Message) -> FileInfo | None:
        """Extract file information from Telegram message.

        Args:
            message: Telegram message

        Returns:
            FileInfo if message contains a file, None otherwise
        """
        file_id: str | None = None
        original_filename: str = ""
        file_size: int | None = None
        file_type: str = ""

        if message.document:
            file_id = message.document.file_id
            original_filename = message.document.file_name or "document"
            file_size = message.document.file_size
            file_type = "document"
        elif message.photo:
            file_id = message.photo[-1].file_id
            original_filename = "photo.jpg"
            file_size = message.photo[-1].file_size
            file_type = "photo"
        elif message.video:
            file_id = message.video.file_id
            original_filename = message.video.file_name or "video.mp4"
            file_size = message.video.file_size
            file_type = "video"
        elif message.audio:
            file_id = message.audio.file_id
            original_filename = message.audio.file_name or "audio.mp3"
            file_size = message.audio.file_size
            file_type = "audio"
        elif message.voice:
            file_id = message.voice.file_id
            original_filename = "voice.ogg"
            file_size = message.voice.file_size
            file_type = "voice"
        elif message.animation:
            file_id = message.animation.file_id
            original_filename = message.animation.file_name or "animation.gif"
            file_size = message.animation.file_size
            file_type = "animation"

        if file_id:
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

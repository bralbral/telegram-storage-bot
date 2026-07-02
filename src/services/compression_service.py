from __future__ import annotations

import gzip
import os
from pathlib import Path

from src.logging_config import get_logger
from src.utils.naming import extract_extension, generate_filename

logger = get_logger(__name__)

# Chunk size for streaming operations (1MB)
DEFAULT_CHUNK_SIZE = 1024 * 1024

# Already compressed file extensions
COMPRESSED_EXTENSIONS = {
    ".gz",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".bz2",
    ".xz",
    ".tgz",
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".deb",
    ".rpm",
    ".apk",
    ".iso",
}


class CompressionService:
    """Service for file compression operations."""

    @staticmethod
    def _stream_copy(
        source_path: Path,
        dest_path: Path,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        """Stream copy file in chunks to avoid loading entire file into memory.

        Args:
            source_path: Path to the source file
            dest_path: Path to the destination file
            chunk_size: Size of chunks to read/write (default: 1MB)
        """
        with open(source_path, "rb") as f_in:
            with open(dest_path, "wb") as f_out:
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)

    @staticmethod
    def is_already_compressed(filename: str) -> bool:
        """Check if file has a compressed extension.

        Args:
            filename: Filename to check

        Returns:
            True if file has compressed extension, False otherwise
        """
        filename_lower = filename.lower()
        for ext in COMPRESSED_EXTENSIONS:
            if filename_lower.endswith(ext):
                return True
        return False

    async def compress_gzip_streaming(
        self,
        source_path: Path,
        prefix: str,
        download_dir: Path,
        original_filename: str = "",
    ) -> str:
        """Compress file with streaming to avoid loading entire file into memory.

        Reads file in chunks (1MB) and compresses on-the-fly to avoid OOM.
        Preserves original filename inside gzip archive.

        Args:
            source_path: Path to the source file
            prefix: User-defined prefix for the archive filename
            download_dir: Directory to save the compressed file
            original_filename: Original filename to preserve inside gzip

        Returns:
            The filename of the saved compressed file

        Raises:
            OSError: If file writing fails
        """
        filename = generate_filename(prefix, "gz")
        filepath = Path(os.path.join(download_dir, filename))

        try:
            with open(source_path, "rb") as f_in:
                with open(filepath, "wb") as f_out:
                    with gzip.GzipFile(
                        fileobj=f_out, mode="wb", filename=original_filename or "file"
                    ) as gzip_file:
                        while True:
                            chunk = f_in.read(DEFAULT_CHUNK_SIZE)
                            if not chunk:
                                break
                            gzip_file.write(chunk)
            logger.info(
                "File compressed",
                filename=filename,
                original_filename=original_filename,
            )
            return filename
        except OSError as e:
            logger.error("Failed to compress file", filename=filename, error=str(e))
            raise

    async def save_direct_streaming(
        self,
        source_path: Path,
        prefix: str,
        download_dir: Path,
        original_filename: str = "",
    ) -> str:
        """Save file directly without compression using streaming.

        Args:
            source_path: Path to the source file
            prefix: User-defined prefix for the filename
            download_dir: Directory to save the file
            original_filename: Original filename to use as base

        Returns:
            The filename of the saved file

        Raises:
            OSError: If file writing fails
        """
        ext = extract_extension(original_filename)
        filename = generate_filename(prefix, ext)
        filepath = Path(os.path.join(download_dir, filename))

        try:
            # Copy file in chunks to avoid loading entire file into memory
            CompressionService._stream_copy(source_path, filepath)
            logger.info(
                "File saved",
                filename=filename,
                original_filename=original_filename,
            )
            return filename
        except OSError as e:
            logger.error("Failed to save file", filename=filename, error=str(e))
            raise

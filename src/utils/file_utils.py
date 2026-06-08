from __future__ import annotations

import gzip
from pathlib import Path

from src.logging_config import get_logger
from src.utils.naming import generate_filename

logger = get_logger(__name__)

# Backward compatibility: re-export functions that are now in services
# These functions are deprecated in favor of using services


async def save_file_gzip(
    file_content: bytes,
    prefix: str,
    download_dir: Path,
    original_filename: str = "",
) -> str:
    """Compress file content with gzip and save.

    Deprecated: Use CompressionService instead.

    Args:
        file_content: The file content as bytes
        prefix: User-defined prefix for the archive filename
        download_dir: Directory to save the compressed file
        original_filename: Original filename to preserve inside gzip

    Returns:
        The filename of the saved compressed file

    Raises:
        OSError: If file writing fails
    """
    filename = generate_filename(prefix, "gz")
    filepath = download_dir / filename

    try:
        with open(filepath, "wb") as f:
            gzip_file = gzip.GzipFile(
                fileobj=f, mode="wb", filename=original_filename or "file"
            )
            gzip_file.write(file_content)
            gzip_file.close()
        logger.info(
            "File saved", filename=filename, original_filename=original_filename
        )
        return filename
    except OSError as e:
        logger.error("Failed to save file", filename=filename, error=str(e))
        raise


async def save_file_direct(
    file_content: bytes,
    prefix: str,
    download_dir: Path,
    original_filename: str = "",
) -> str:
    """Save file content directly without compression.

    Deprecated: Use CompressionService instead.

    Args:
        file_content: The file content as bytes
        prefix: User-defined prefix for the filename
        download_dir: Directory to save the file
        original_filename: Original filename to use as base

    Returns:
        The filename of the saved file

    Raises:
        OSError: If file writing fails
    """
    from src.utils.naming import extract_extension

    ext = extract_extension(original_filename)
    filename = generate_filename(prefix, ext)
    filepath = download_dir / filename

    try:
        with open(filepath, "wb") as f:
            f.write(file_content)
        logger.info(
            "File saved", filename=filename, original_filename=original_filename
        )
        return filename
    except OSError as e:
        logger.error("Failed to save file", filename=filename, error=str(e))
        raise


# Image format detection by magic bytes
IMAGE_MAGIC_BYTES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"RIFF": ".webp",  # WEBP starts with RIFF....WEBP
    b"\x00\x00\x00\x0cJXR ": ".jxr",
    b"\x00\x00\x00 ftypavif": ".avif",
    b"\x00\x00\x00 ftypheic": ".heic",
}


def detect_image_format(file_path: Path) -> str:
    """Detect image format by reading magic bytes."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(12)
        for magic, ext in IMAGE_MAGIC_BYTES.items():
            if header.startswith(magic):
                return ext
        # Default to jpg if unknown
        return ".jpg"
    except Exception:
        return ".jpg"

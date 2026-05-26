import gzip
import uuid
from datetime import datetime
from pathlib import Path

from src.logging_config import get_logger

logger = get_logger(__name__)


async def save_file_gzip(
    file_content: bytes,
    prefix: str,
    download_dir: Path,
    original_filename: str = "",
) -> str:
    """Compress file content with gzip and save as prefix_timestamp_uuid.gz.

    Archive filename includes prefix, original filename preserved inside gzip.

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_part = uuid.uuid4().hex[:8]

    # Archive filename with prefix
    filename = f"{prefix}_{timestamp}_{uuid_part}.gz"
    filepath = download_dir / filename

    try:
        # Use sync operations for gzip (in-memory content)
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


async def save_file_gzip_streaming(
    source_path: Path,
    prefix: str,
    download_dir: Path,
    original_filename: str = "",
) -> str:
    """Compress file with streaming to avoid loading entire file into memory.

    Reads file in chunks (1MB) and compresses on-the-fly to avoid OOM.

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_part = uuid.uuid4().hex[:8]

    # Archive filename with prefix
    filename = f"{prefix}_{timestamp}_{uuid_part}.gz"
    filepath = download_dir / filename

    chunk_size = 1024 * 1024  # 1MB chunks

    try:
        with open(source_path, "rb") as f_in:
            with open(filepath, "wb") as f_out:
                with gzip.open(f_out, "wb") as gzip_file:
                    while True:
                        chunk = f_in.read(chunk_size)
                        if not chunk:
                            break
                        gzip_file.write(chunk)
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_part = uuid.uuid4().hex[:8]

    # Use original filename extension if available
    if original_filename:
        # Extract extension from original filename
        if "." in original_filename:
            ext = original_filename.rsplit(".", 1)[-1]
            filename = f"{prefix}_{timestamp}_{uuid_part}.{ext}"
        else:
            filename = f"{prefix}_{timestamp}_{uuid_part}"
    else:
        filename = f"{prefix}_{timestamp}_{uuid_part}"

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


async def save_file_direct_streaming(
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_part = uuid.uuid4().hex[:8]

    # Use original filename extension if available
    if original_filename:
        # Extract extension from original filename
        if "." in original_filename:
            ext = original_filename.rsplit(".", 1)[-1]
            filename = f"{prefix}_{timestamp}_{uuid_part}.{ext}"
        else:
            filename = f"{prefix}_{timestamp}_{uuid_part}"
    else:
        filename = f"{prefix}_{timestamp}_{uuid_part}"

    filepath = download_dir / filename

    try:
        # Copy file in chunks to avoid loading entire file into memory
        chunk_size = 1024 * 1024  # 1MB chunks
        with open(source_path, "rb") as f_in:
            with open(filepath, "wb") as f_out:
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
        logger.info(
            "File saved", filename=filename, original_filename=original_filename
        )
        return filename
    except OSError as e:
        logger.error("Failed to save file", filename=filename, error=str(e))
        raise

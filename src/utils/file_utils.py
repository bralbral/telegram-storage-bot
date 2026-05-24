import gzip
import hashlib
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


async def save_file_gzip(
    file_content: bytes,
    prefix: str,
    download_dir: Path,
    original_filename: str = "",
) -> str:
    """Compress file content with gzip and save as prefix_timestamp_hash.gz.

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
    hash_part = hashlib.sha256(file_content).hexdigest()[:8]

    # Archive filename with prefix
    filename = f"{prefix}_{timestamp}_{hash_part}.gz"
    filepath = download_dir / filename

    try:
        # Use sync operations for gzip (in-memory content)
        with open(filepath, "wb") as f:
            gzip_file = gzip.GzipFile(
                fileobj=f, mode="wb", filename=original_filename or "file"
            )
            gzip_file.write(file_content)
            gzip_file.close()
        logger.info(f"File saved: {filename} (inside: {original_filename})")
        return filename
    except OSError as e:
        logger.error(f"Failed to save file {filename}: {e}")
        raise

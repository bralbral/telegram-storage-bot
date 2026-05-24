import gzip
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)


async def save_file_gzip(file_content: bytes, prefix: str, download_dir: Path) -> str:
    """Compress file content with gzip and save as prefix_timestamp_hash.gz.

    Args:
        file_content: The file content as bytes
        prefix: User-defined prefix for the filename
        download_dir: Directory to save the compressed file

    Returns:
        The filename of the saved compressed file

    Raises:
        OSError: If file writing fails
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_part = hashlib.sha256(file_content).hexdigest()[:8]
    filename = f"{prefix}_{timestamp}_{hash_part}.gz"
    filepath = download_dir / filename

    try:
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(gzip.compress(file_content))
        logger.info(f"File saved: {filename}")
        return filename
    except OSError as e:
        logger.error(f"Failed to save file {filename}: {e}")
        raise

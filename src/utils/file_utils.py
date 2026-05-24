import gzip
import hashlib
from datetime import datetime
from pathlib import Path

import aiofiles


async def save_file_gzip(file_content: bytes, prefix: str, download_dir: Path) -> str:
    """Compress file content with gzip and save as prefix_timestamp_hash.gz."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hash_part = hashlib.md5(file_content).hexdigest()[:8]
    filename = f"{prefix}_{timestamp}_{hash_part}.gz"
    filepath = download_dir / filename

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(gzip.compress(file_content))

    return filename
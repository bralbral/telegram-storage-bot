from __future__ import annotations

import uuid
from datetime import datetime


def generate_filename(prefix: str, extension: str = "") -> str:
    """Generate a unique filename with timestamp and UUID.

    Args:
        prefix: User-defined prefix for the filename
        extension: File extension (with or without leading dot)

    Returns:
        Generated filename in format: {prefix}_{timestamp}_{uuid}.{extension}

    Example:
        >>> generate_filename("user", "gz")
        "user_20260107_123456_a1b2c3d4.gz"
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_part = uuid.uuid4().hex[:8]

    # Ensure extension starts with dot
    if extension and not extension.startswith("."):
        extension = f".{extension}"

    if extension:
        return f"{prefix}_{timestamp}_{uuid_part}{extension}"
    return f"{prefix}_{timestamp}_{uuid_part}"


def extract_extension(filename: str) -> str:
    """Extract file extension from filename.

    Args:
        filename: Original filename

    Returns:
        File extension without leading dot, or empty string if no extension

    Example:
        >>> extract_extension("document.pdf")
        "pdf"
        >>> extract_extension("archive.tar.gz")
        "gz"
        >>> extract_extension("no_extension")
        ""
    """
    if "." in filename:
        return filename.rsplit(".", 1)[-1]
    return ""

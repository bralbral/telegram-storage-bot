from __future__ import annotations


def bytes_to_mb(bytes_size: int | None) -> float:
    """Convert bytes to megabytes.

    Args:
        bytes_size: Size in bytes

    Returns:
        Size in megabytes (0 if bytes_size is None)
    """
    if bytes_size is None:
        return 0.0
    return bytes_size / (1024 * 1024)


def bytes_to_gb(bytes_size: int | None) -> float:
    """Convert bytes to gigabytes.

    Args:
        bytes_size: Size in bytes

    Returns:
        Size in gigabytes (0 if bytes_size is None)
    """
    if bytes_size is None:
        return 0.0
    return bytes_size / (1024 * 1024 * 1024)

from __future__ import annotations

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """Data transfer object for file information in buffer."""

    file_id: str = Field(..., description="Telegram file ID")
    filename: str = Field(..., description="Original filename")
    file_size: int | None = Field(None, description="File size in bytes")
    file_type: str = Field(..., description="File type (document, photo, video, etc.)")
    source: str = Field(
        default="telegram", description="Where the file is stored: telegram or local"
    )
    content: str | None = Field(None, description="Transient in-memory text content")

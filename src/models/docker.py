from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DockerImageInfo(BaseModel):
    """Data transfer object for Docker image information."""

    image_name: str = Field(
        ..., min_length=1, max_length=128, description="Docker image name"
    )
    prefix: str = Field(default="", description="User prefix for filename")

    @field_validator("image_name")
    @classmethod
    def validate_image_name(cls, v: str) -> str:
        """Basic validation for Docker image name."""
        if not v or len(v) > 128:
            raise ValueError("Docker image name must be 1-128 characters")
        return v.strip()

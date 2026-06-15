from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class User(BaseModel):
    """Data transfer object for user information."""

    telegram_id: int = Field(..., gt=0, description="Telegram user ID")
    prefix: str = Field(
        default="", min_length=0, max_length=10, description="User prefix"
    )

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, v: str) -> str:
        """Validate prefix contains only latin alphanumeric characters and underscore."""
        import re

        if v and not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "Prefix must contain only latin letters, numbers, and underscores"
            )
        return v

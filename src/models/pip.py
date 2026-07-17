from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PipDownloadInfo(BaseModel):
    """Validated request for downloading Python package wheels."""

    python_version: str = Field(..., pattern=r"^3\.(?:[7-9]|1[0-4])$")
    requirements: list[str] = Field(..., min_length=1, max_length=20)
    include_dependencies: bool = True
    only_binary: bool = False
    prefix: str = Field(default="")

    @field_validator("requirements")
    @classmethod
    def validate_requirements(cls, requirements: list[str]) -> list[str]:
        allowed_characters = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.[]<>=,!~"
        )
        for requirement in requirements:
            if not requirement or len(requirement) > 200:
                raise ValueError("Each package specification must be 1-200 characters")
            if requirement.startswith("-") or any(
                char not in allowed_characters for char in requirement
            ):
                raise ValueError("Unsupported package specification")
        return requirements

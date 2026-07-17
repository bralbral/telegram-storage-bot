from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AptDownloadInfo(BaseModel):
    """Validated request for downloading Debian packages."""

    debian_version: str = Field(default="12", pattern=r"^1[0-3](?:\.\d+\.\d+)?$")
    snapshot: str | None = Field(default=None, pattern=r"^\d{8}T\d{6}Z$")
    packages: list[str] = Field(..., min_length=1, max_length=20)
    include_dependencies: bool = True
    prefix: str = Field(default="")

    @field_validator("packages")
    @classmethod
    def validate_packages(cls, packages: list[str]) -> list[str]:
        allowed_characters = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.+=:~"
        )
        for package in packages:
            if not package or len(package) > 200:
                raise ValueError("Each package specification must be 1-200 characters")
            if package.startswith("-") or any(
                character not in allowed_characters for character in package
            ):
                raise ValueError("Unsupported package specification")
        return packages

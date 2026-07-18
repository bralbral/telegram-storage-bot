from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuration class that collects all environment variables with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., min_length=1, description="Bot token from @BotFather")
    admin_ids: str = Field(..., description="Comma-separated admin Telegram IDs")

    download_dir: Path = Field(
        default=Path("./downloads"), description="Directory for downloaded files"
    )
    db_path: str = Field(default="./users.db", description="Database file path")

    max_file_size: int = Field(
        default=2 * 1024 * 1024 * 1024,
        gt=0,
        description="Maximum file size in bytes",
    )
    max_buffer_files: int = Field(default=100, gt=0)
    max_buffer_size: int = Field(default=10 * 1024 * 1024 * 1024, gt=0)
    max_text_collection_size: int = Field(default=10 * 1024 * 1024, gt=0)
    snapshot_dir: Path = Field(
        default=Path("./snapshots"), description="Directory shared with Playwright"
    )
    playwright_url: str = Field(
        default="http://playwright:3000", description="Internal Playwright sidecar URL"
    )
    playwright_timeout: int = Field(default=60, gt=0, description="Snapshot timeout")
    max_docker_operations: int = Field(default=1, gt=0)
    max_pip_operations: int = Field(default=1, gt=0)
    max_apt_operations: int = Field(default=1, gt=0)
    apt_download_timeout: int = Field(default=86_400, gt=0)

    throttle_rate: float = Field(
        default=3.0, gt=0, description="Throttle rate in seconds"
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    health_port: int = Field(
        default=8080, ge=1, le=65535, description="Health check server port"
    )

    docker_host: str = Field(
        default="unix:///var/run/docker.sock",
        description="Docker daemon socket URL",
    )

    telegram_api_id: str | None = Field(
        default=None, description="Telegram API ID from https://my.telegram.org"
    )
    telegram_api_hash: str | None = Field(
        default=None, description="Telegram API Hash from https://my.telegram.org"
    )

    use_local_api: bool = Field(
        default=True, description="Enable local Bot API for large files (>20MB)"
    )

    local_api_url: str = Field(
        default="http://127.0.0.1:8081",
        description="Local Bot API server URL (internal Docker network)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate that log_level is a valid value."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}, got '{v}'")
        return v.upper()

    @field_validator("admin_ids")
    @classmethod
    def validate_admin_ids(cls, value: str) -> str:
        """Reject a malformed admin list instead of silently disabling admins."""
        try:
            ids = [int(item.strip()) for item in value.split(",")]
        except (AttributeError, ValueError) as e:
            raise ValueError(
                "admin_ids must be comma-separated positive integers"
            ) from e
        if not ids or any(admin_id <= 0 for admin_id in ids):
            raise ValueError("admin_ids must contain at least one positive integer")
        return value

    @property
    def admin_ids_list(self) -> list[int]:
        """Parse admin IDs from comma-separated string."""
        return [int(id_.strip()) for id_ in self.admin_ids.split(",")]

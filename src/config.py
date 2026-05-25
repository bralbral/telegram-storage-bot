from __future__ import annotations

import os
from pathlib import Path


class Config:
    """Configuration class that collects all environment variables."""

    def __init__(self) -> None:
        self._bot_token = os.getenv("BOT_TOKEN")
        self._admin_ids = self._parse_admin_ids()
        self._download_dir = Path(
            os.getenv("DOWNLOAD_DIR", str(Path(__file__).parent.parent / "downloads"))
        )
        self._db_path = os.getenv(
            "DB_PATH", str(Path(__file__).parent.parent / "users.db")
        )
        self._max_file_size = int(
            os.getenv("MAX_FILE_SIZE", str(2 * 1024 * 1024 * 1024))
        )
        self._throttle_rate = float(os.getenv("THROTTLE_RATE", "3.0"))
        self._health_port = int(os.getenv("HEALTH_PORT", "8080"))
        self._docker_host = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
        self._use_local_api = os.getenv("USE_LOCAL_API", "false").lower() == "true"
        self._local_api_url = os.getenv("LOCAL_API_URL", "http://127.0.0.1:8081")

    def _parse_admin_ids(self) -> list[int]:
        """Parse admin IDs from environment variable."""
        admin_ids_env = os.getenv("ADMIN_IDS")
        if admin_ids_env:
            try:
                return [int(id.strip()) for id in admin_ids_env.split(",")]
            except ValueError:
                return []
        return []

    @property
    def bot_token(self) -> str | None:
        return self._bot_token

    @property
    def admin_ids(self) -> list[int]:
        return self._admin_ids

    @property
    def download_dir(self) -> Path:
        return self._download_dir

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def max_file_size(self) -> int:
        return self._max_file_size

    @property
    def throttle_rate(self) -> float:
        return self._throttle_rate

    @property
    def health_port(self) -> int:
        return self._health_port

    @property
    def docker_host(self) -> str:
        return self._docker_host

    @property
    def use_local_api(self) -> bool:
        return self._use_local_api

    @property
    def local_api_url(self) -> str:
        return self._local_api_url

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from src.logging_config import get_logger
from src.services.apt_service import AptService
from src.services.docker_service import DockerService
from src.services.file_service import FileService
from src.services.pip_service import PipService
from src.services.user_service import UserService

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = get_logger(__name__)


class ServiceInjectionMiddleware(BaseMiddleware):
    """Middleware that injects services into handler data."""

    __slots__ = (
        "bot",
        "admin_ids",
        "download_dir",
        "file_service",
        "apt_service",
        "docker_service",
        "pip_service",
        "user_service",
    )

    def __init__(
        self,
        bot=None,
        admin_ids: list[int] | None = None,
        download_dir: Path | None = None,
        file_service: FileService | None = None,
        apt_service: AptService | None = None,
        docker_service: DockerService | None = None,
        pip_service: PipService | None = None,
        user_service: UserService | None = None,
    ):
        self.bot = bot
        self.admin_ids = admin_ids or []
        self.download_dir = download_dir
        self.file_service = file_service
        self.apt_service = apt_service
        self.docker_service = docker_service
        self.pip_service = pip_service
        self.user_service = user_service

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """Inject services into handler data."""
        # Inject services
        if self.file_service:
            data["file_service"] = self.file_service
        if self.apt_service:
            data["apt_service"] = self.apt_service
        if self.docker_service:
            data["docker_service"] = self.docker_service
        if self.pip_service:
            data["pip_service"] = self.pip_service
        if self.user_service:
            data["user_service"] = self.user_service

        # Add bot, admin_ids, and download_dir for handlers that need them
        data["bot"] = self.bot
        data["admin_ids"] = self.admin_ids
        data["download_dir"] = self.download_dir

        return await handler(event, data)

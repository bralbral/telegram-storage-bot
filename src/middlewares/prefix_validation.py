from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from src.logging_config import get_logger

logger = get_logger(__name__)


class PrefixValidationMiddleware(BaseMiddleware):
    """Middleware that validates prefix requirement for file and docker operations."""

    __slots__ = ()

    def __init__(self) -> None:
        pass

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """Validate that user has prefix for file and docker operations."""
        # Check if this is a file or docker pull operation
        has_file = any(
            [
                event.document,
                event.photo,
                event.video,
                event.audio,
                event.voice,
                event.animation,
            ],
        )

        is_docker_pull = False
        if event.text and event.text.strip().lower().startswith("docker pull"):
            is_docker_pull = True

        # All users need prefix for files and docker pull
        if (has_file or is_docker_pull) and not data.get("has_prefix", False):
            logger.info(
                "Action denied because prefix is not set",
                action="file_upload" if has_file else "docker_pull",
                user_id=event.from_user.id,
            )
            await event.answer("❌ Set your prefix first with /set_prefix")
            return

        return await handler(event, data)

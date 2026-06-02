from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from src.db.database import Database
from src.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = get_logger(__name__)


class AccessMiddleware(BaseMiddleware):
    """Middleware that checks user access - admins from config have automatic access."""

    __slots__ = ("db", "admin_ids", "download_dir", "bot")

    def __init__(
        self,
        db: Database,
        admin_ids: list[int] | None = None,
        download_dir: Path | None = None,
        bot=None,
    ):
        self.db = db
        self.admin_ids = admin_ids or []
        self.download_dir = download_dir
        self.bot = bot

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """Check if user has access - admins auto-granted and added to DB."""
        user_id = event.from_user.id
        is_admin = user_id in self.admin_ids

        try:
            prefix = await self.db.get_user(user_id)

            # Auto-add admins to DB if not present
            if is_admin and prefix is None:
                await self.db.add_user(user_id, "")
                logger.info("Admin auto-added to database", user_id=user_id)
                prefix = ""

            # Regular users must be in DB
            if not is_admin and prefix is None:
                logger.debug("Access denied: user not in database", user_id=user_id)
                return

            # If prefix is still None (shouldn't happen), use empty string
            if prefix is None:
                prefix = ""

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

            data["user_data"] = (prefix, is_admin)
            data["has_prefix"] = bool(prefix)
            data["is_admin"] = is_admin
            data["db"] = self.db
            data["download_dir"] = self.download_dir
            data["bot"] = self.bot
            data["admin_ids"] = self.admin_ids

            # All users need prefix for files and docker pull
            if (has_file or is_docker_pull) and not data["has_prefix"]:
                await event.answer("❌ Set your prefix first with /set_prefix")
                return

            return await handler(event, data)
        except Exception as e:
            logger.error("Error in access middleware", user_id=user_id, error=str(e))
            return

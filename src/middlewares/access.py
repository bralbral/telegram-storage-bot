from __future__ import annotations

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

    __slots__ = ("db", "admin_ids")

    def __init__(
        self,
        db: Database,
        admin_ids: list[int] | None = None,
    ):
        self.db = db
        self.admin_ids = admin_ids or []

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

            # Regular users must be in DB, except for /start command
            if not is_admin and prefix is None:
                # Allow /start command for all users
                if event.text and event.text.strip() == "/start":
                    prefix = ""  # Allow start command
                    logger.debug("Allowing /start for new user", user_id=user_id)
                else:
                    logger.debug("Access denied: user not in database", user_id=user_id)
                    return

            # If prefix is still None (shouldn't happen), use empty string
            if prefix is None:
                prefix = ""

            data["user_data"] = (prefix, is_admin)
            data["has_prefix"] = bool(prefix)
            data["is_admin"] = is_admin
            data["db"] = self.db

            return await handler(event, data)
        except Exception as e:
            logger.error("Error in access middleware", user_id=user_id, error=str(e))
            return

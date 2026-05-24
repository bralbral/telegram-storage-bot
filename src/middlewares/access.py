from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from src.db.database import Database

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    """Middleware that checks user access - admins from config have automatic access."""

    __slots__ = ("db", "admin_ids")

    def __init__(self, db: Database, admin_ids: list[int] | None = None):
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
                logger.info(f"Admin {user_id} auto-added to database")
                prefix = ""

            # Regular users must be in DB
            if not is_admin and prefix is None:
                logger.debug(f"Access denied for user {user_id}: not in database")
                return

            # If prefix is still None (shouldn't happen), use empty string
            if prefix is None:
                prefix = ""

            data["user_data"] = (prefix, is_admin)
            data["has_prefix"] = bool(prefix)
            data["is_admin"] = is_admin

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

            # Only non-admins need prefix for files
            if has_file and not data["has_prefix"] and not is_admin:
                await event.answer("❌ Set your prefix first with /set_prefix")
                return

            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error in access middleware for user {user_id}: {e}")
            return

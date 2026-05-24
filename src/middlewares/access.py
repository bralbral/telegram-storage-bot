from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from db.database import Database

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    """Middleware that checks user access - only reacts if user exists in DB."""

    __slots__ = ("db",)

    def __init__(self, db: Database):
        self.db = db

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """Check if user exists in database. If not, silently ignore."""
        user_id = event.from_user.id

        try:
            prefix = await self.db.get_user(user_id)
            if prefix is None:
                logger.debug(f"Access denied for user {user_id}: not in database")
                return

            data["user_data"] = (prefix,)
            data["has_prefix"] = bool(prefix)

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

            if has_file and not data["has_prefix"]:
                await event.answer("❌ Set your prefix first with /set_prefix")
                return

            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error in access middleware for user {user_id}: {e}")
            return

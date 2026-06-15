from __future__ import annotations

import time
from collections.abc import Awaitable
from typing import Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from src.db.database import Database
from src.logging_config import get_logger

logger = get_logger(__name__)


class ThrottleMiddleware(BaseMiddleware):
    """Rate limiting middleware - limits actions only for users not in database."""

    __slots__ = ("rate", "user_last_action", "db")

    def __init__(self, rate: float, db: Database | None = None):
        self.rate = rate
        self.user_last_action: dict[int, float] = {}
        self.db = db

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """Enforce rate limiting only for users not in database."""
        user_id = event.from_user.id
        current_time = time.time()

        try:
            # Skip throttling if user is in database
            if self.db:
                try:
                    user_data = await self.db.get_user(user_id)
                    if user_data:
                        # User is in database, no throttling
                        return await handler(event, data)
                except Exception as e:
                    logger.warning(
                        "Failed to check user in database for throttling",
                        user_id=user_id,
                        error=str(e),
                    )
                    # On DB error, allow action to avoid blocking

            last_action = self.user_last_action.get(user_id, 0)
            time_since_last = current_time - last_action

            if time_since_last < self.rate:
                remaining_time = self.rate - time_since_last
                logger.debug(
                    "Rate limit exceeded",
                    user_id=user_id,
                    wait_time=f"{remaining_time:.1f}s",
                )
                # Inform user about rate limit
                await event.answer(
                    f"⏳ Please wait {remaining_time:.1f} seconds before next action"
                )
                return

            # Update last action time
            self.user_last_action[user_id] = current_time
            return await handler(event, data)
        except Exception as e:
            logger.error("Error in throttle middleware", user_id=user_id, error=str(e))
            # On error, allow the action to avoid blocking legitimate users
            return await handler(event, data)

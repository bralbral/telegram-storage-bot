from __future__ import annotations

import logging
import time
from collections.abc import Awaitable
from typing import Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class ThrottleMiddleware(BaseMiddleware):
    """Rate limiting middleware - limits actions per user."""

    __slots__ = ("rate", "user_last_action")

    def __init__(self, rate: float):
        self.rate = rate
        self.user_last_action: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """Enforce rate limiting per user."""
        user_id = event.from_user.id
        current_time = time.time()

        try:
            last_action = self.user_last_action.get(user_id, 0)
            time_since_last = current_time - last_action

            if time_since_last < self.rate:
                remaining_time = self.rate - time_since_last
                logger.debug(
                    f"Rate limit exceeded for user {user_id}. Wait {remaining_time:.1f}s"
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
            logger.error(f"Error in throttle middleware for user {user_id}: {e}")
            # On error, allow the action to avoid blocking legitimate users
            return await handler(event, data)

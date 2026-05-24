from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from utils.variables import THROTTLE_RATE

if TYPE_CHECKING:
    from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class ThrottleMiddleware(BaseMiddleware):
    """Middleware that limits users to 1 action per THROTTLE_RATE seconds."""

    __slots__ = ("rate", "user_timestamps")

    def __init__(self, rate: float | None = None):
        self.rate = rate or THROTTLE_RATE
        self.user_timestamps: dict[int, list[float]] = defaultdict(list)

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
            timestamps = self.user_timestamps[user_id]
            timestamps[:] = [t for t in timestamps if current_time - t < self.rate]

            if timestamps:
                logger.debug(f"Rate limit exceeded for user {user_id}")
                return

            timestamps.append(current_time)
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error in throttle middleware for user {user_id}: {e}")
            return await handler(event, data)

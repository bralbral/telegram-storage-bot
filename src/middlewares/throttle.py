from __future__ import annotations

import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from utils.variables import THROTTLE_RATE

if TYPE_CHECKING:
    from collections.abc import Awaitable


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

        timestamps = self.user_timestamps[user_id]
        timestamps[:] = [t for t in timestamps if current_time - t < self.rate]

        if timestamps:
            return

        timestamps.append(current_time)
        return await handler(event, data)
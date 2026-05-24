import time
from collections import defaultdict

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from utils.variables import THROTTLE_RATE


class ThrottleMiddleware(BaseMiddleware):
    """Middleware that limits users to 1 action per THROTTLE_RATE seconds."""

    def __init__(self, rate: float = None):
        self.rate = rate or THROTTLE_RATE
        self.user_timestamps = defaultdict(list)

    async def __call__(self, handler, event: Message, data: dict):
        """Enforce rate limiting per user."""
        user_id = event.from_user.id
        current_time = time.time()

        timestamps = self.user_timestamps[user_id]
        timestamps[:] = [t for t in timestamps if current_time - t < self.rate]

        if timestamps:
            return

        timestamps.append(current_time)
        return await handler(event, data)
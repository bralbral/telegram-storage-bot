import time
from collections import defaultdict

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message

from db.database import Database


class AccessMiddleware(BaseMiddleware):
    """Middleware that checks user access - only reacts if user exists in DB."""

    def __init__(self, db: Database):
        self.db = db

    async def __call__(self, handler, event: Message, data: dict):
        """Check if user exists in database. If not, silently ignore."""
        user_id = event.from_user.id

        prefix = await self.db.get_user(user_id)
        if prefix is None:
            return

        data["user_data"] = (prefix,)
        data["has_prefix"] = bool(prefix)

        has_file = any([
            event.document, event.photo, event.video, event.audio,
            event.voice, event.animation
        ])

        if has_file and not data["has_prefix"]:
            await event.answer("❌ Set your prefix first with /set_prefix")
            return

        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Middleware that limits users to 1 action per 3 seconds."""

    def __init__(self, rate: float = 0.33):
        self.rate = rate
        self.user_timestamps = defaultdict(list)

    async def __call__(self, handler, event: Message, data: dict):
        """Enforce rate limiting per user."""
        user_id = event.from_user.id
        current_time = time.time()

        timestamps = self.user_timestamps[user_id]
        timestamps[:] = [t for t in timestamps if current_time - t < 3.0]

        if timestamps:
            return

        timestamps.append(current_time)
        return await handler(event, data)
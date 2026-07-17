from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message
from structlog.contextvars import bound_contextvars

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

    @staticmethod
    def _get_action(event: Message) -> str:
        """Return a safe, compact description of the incoming user action."""
        text = (event.text or "").strip()
        if text.startswith("/"):
            return text.split(maxsplit=1)[0].split("@", maxsplit=1)[0]
        if any(
            (
                event.document,
                event.photo,
                event.video,
                event.audio,
                event.voice,
                event.animation,
            )
        ):
            return "file_upload"
        if text.lower().startswith("docker pull "):
            return "docker_pull"
        if text.lower().startswith("pip download "):
            return "pip_download"
        return "text_message"

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        """Check if user has access - admins auto-granted and added to DB."""
        user_id = event.from_user.id
        is_admin = user_id in self.admin_ids

        with bound_contextvars(
            user_id=user_id,
            chat_id=event.chat.id,
            message_id=event.message_id,
        ):
            try:
                is_registered, prefix = await self.db.get_user_state(user_id)

                # Auto-add admins to DB if not present
                if is_admin and not is_registered:
                    await self.db.add_user(user_id, "")
                    logger.info("Admin auto-added to database")
                    prefix = ""
                    is_registered = True

                # Regular users must be in DB, except for public help commands.
                if not is_admin and prefix is None:
                    # Allow /start and /help for all users.
                    if event.text and event.text.strip() in {"/start", "/help"}:
                        prefix = ""  # Allow start command
                        logger.debug("Allowing public help command for new user")
                    else:
                        logger.info("Access denied", action=self._get_action(event))
                        return

                # If prefix is still None (shouldn't happen), use empty string
                if prefix is None:
                    prefix = ""

                data["user_data"] = (prefix, is_admin)
                data["has_prefix"] = bool(prefix)
                data["is_admin"] = is_admin
                data["is_registered"] = is_registered
                data["db"] = self.db

                logger.info(
                    "User action received",
                    action=self._get_action(event),
                    is_admin=is_admin,
                )
                return await handler(event, data)
            except Exception as e:
                logger.error("Error in access middleware", error=str(e))
                return

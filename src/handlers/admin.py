from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable

from aiogram.filters import CommandObject
from aiogram.types import Message

from db.database import db

logger = logging.getLogger(__name__)


def is_valid_prefix(prefix: str) -> bool:
    """Validate prefix: only latin alphanumeric characters, max 5 chars."""
    if not prefix:
        return True  # Empty prefix is allowed
    return len(prefix) <= 5 and bool(re.match(r"^[a-zA-Z0-9_]+$", prefix))


def create_admin_handlers(
    admin_ids: list[int],
) -> tuple[
    Callable[[Message, CommandObject], Awaitable[None]],
    Callable[[Message, CommandObject], Awaitable[None]],
    Callable[[Message], Awaitable[None]],
]:
    """Create admin command handlers with admin_ids bound via closure."""

    async def cmd_add_user(message: Message, command: CommandObject) -> None:
        """Admin only: Add a user to the database with optional prefix."""
        if message.from_user.id not in admin_ids:
            logger.warning(
                f"Unauthorized admin command attempt by user {message.from_user.id}"
            )
            return

        if not command.args:
            await message.answer("Usage: /add_user <telegram_id> [prefix]")
            return

        try:
            parts = command.args.strip().split()
            telegram_id = int(parts[0])
            prefix = parts[1] if len(parts) > 1 else ""

            if not is_valid_prefix(prefix):
                await message.answer(
                    "❌ Invalid prefix. Must be 1-5 latin alphanumeric characters (a-z, A-Z, 0-9, _)."
                )
                return

            await db.add_user(telegram_id, prefix)
            await message.answer(
                f"✅ User {telegram_id} added. Prefix: `{prefix or 'none'}`"
            )
            logger.info(f"Admin {message.from_user.id} added user {telegram_id}")
        except (ValueError, IndexError) as e:
            await message.answer(
                "❌ Invalid format. Use: /add_user <telegram_id> [prefix]"
            )
            logger.error(f"Invalid add_user command format: {e}")
        except Exception as e:
            await message.answer("❌ Failed to add user")
            logger.error(f"Failed to add user: {e}")

    async def cmd_remove_user(message: Message, command: CommandObject) -> None:
        """Admin only: Remove a user from the database."""
        if message.from_user.id not in admin_ids:
            logger.warning(
                f"Unauthorized admin command attempt by user {message.from_user.id}"
            )
            return

        if not command.args:
            await message.answer("Usage: /remove_user <telegram_id>")
            return

        try:
            telegram_id = int(command.args.strip())
            await db.remove_user(telegram_id)
            await message.answer(f"✅ User {telegram_id} removed.")
            logger.info(f"Admin {message.from_user.id} removed user {telegram_id}")
        except ValueError as e:
            await message.answer("❌ Invalid telegram ID format")
            logger.error(f"Invalid remove_user command format: {e}")
        except Exception as e:
            await message.answer("❌ Failed to remove user")
            logger.error(f"Failed to remove user: {e}")

    async def cmd_list_users(message: Message) -> None:
        """Admin only: List all users with their prefixes."""
        if message.from_user.id not in admin_ids:
            logger.warning(
                f"Unauthorized admin command attempt by user {message.from_user.id}"
            )
            return

        try:
            users = await db.get_all_users()

            if not users:
                await message.answer("No users in database.")
                return

            text = "📋 Users:\n"
            for uid, prefix in users:
                text += f"✅ {uid} - prefix: `{prefix or 'none'}`\n"
            await message.answer(text)
            logger.info(f"Admin {message.from_user.id} listed users")
        except Exception as e:
            await message.answer("❌ Failed to list users")
            logger.error(f"Failed to list users: {e}")

    return cmd_add_user, cmd_remove_user, cmd_list_users

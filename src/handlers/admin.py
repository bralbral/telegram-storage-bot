from __future__ import annotations

import logging
import os
import platform
import re
from collections.abc import Awaitable, Callable
from datetime import datetime

from aiogram.filters import CommandObject
from aiogram.types import Message

from src.db.database import Database
from src.exceptions import ValidationError

logger = logging.getLogger(__name__)


def validate_prefix(prefix: str) -> None:
    """Validate prefix and raise ValidationError if invalid."""
    if not prefix:
        return  # Empty prefix is allowed for admin add
    if not (1 <= len(prefix) <= 10):
        raise ValidationError("Prefix must be 1-10 characters long")
    if not re.match(r"^[a-zA-Z0-9_]+$", prefix):
        raise ValidationError(
            "Prefix must contain only latin letters, numbers, and underscores"
        )


def create_admin_handlers(
    admin_ids: list[int],
) -> tuple[
    Callable[[Message, CommandObject, Database], Awaitable[None]],
    Callable[[Message, CommandObject, Database], Awaitable[None]],
    Callable[[Message, Database], Awaitable[None]],
    Callable[[Message, Database], Awaitable[None]],
]:
    """Create admin command handlers with dependencies injected via closure."""

    async def cmd_add_user(
        message: Message, command: CommandObject, db: Database
    ) -> None:
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

            try:
                validate_prefix(prefix)
            except ValidationError as e:
                await message.answer(f"❌ {e}")
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

    async def cmd_remove_user(
        message: Message, command: CommandObject, db: Database
    ) -> None:
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

    async def cmd_list_users(message: Message, db: Database) -> None:
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

    async def cmd_status(message: Message, db: Database) -> None:
        """Admin only: Show bot status and system information."""
        if message.from_user.id not in admin_ids:
            logger.warning(
                f"Unauthorized admin command attempt by user {message.from_user.id}"
            )
            return

        try:
            users = await db.get_all_users()
            uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            status_text = "📊 **Bot Status**\n\n"
            status_text += f"🕐 **Time**: {uptime}\n"
            status_text += f"👥 **Users**: {len(users)} registered\n"
            status_text += f"🤖 **Python**: {platform.python_version()}\n"
            status_text += f"💻 **System**: {platform.system()} {platform.release()}\n"
            status_text += f"🔧 **Admins**: {len(admin_ids)} configured\n"

            # Check if using local API
            use_local_api = os.getenv("USE_LOCAL_API", "false").lower() == "true"
            status_text += f"🌐 **API**: {'Local' if use_local_api else 'Standard'}\n"

            await message.answer(status_text, parse_mode="Markdown")
            logger.info(f"Admin {message.from_user.id} requested status")
        except Exception as e:
            await message.answer("❌ Failed to get status")
            logger.error(f"Failed to get status: {e}")

    return (cmd_add_user, cmd_remove_user, cmd_list_users, cmd_status)

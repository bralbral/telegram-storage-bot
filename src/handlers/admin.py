from __future__ import annotations

import platform
from collections.abc import Awaitable, Callable
from datetime import datetime

from aiogram.filters import CommandObject
from aiogram.types import Message

from src.logging_config import get_logger
from src.models.config import Config

logger = get_logger(__name__)


def create_admin_handlers(
    admin_ids: list[int], config: Config
) -> tuple[
    Callable[[Message, CommandObject], Awaitable[None]],
    Callable[[Message, CommandObject], Awaitable[None]],
    Callable[[Message], Awaitable[None]],
    Callable[[Message], Awaitable[None]],
]:
    """Create admin command handlers with dependencies injected."""

    async def cmd_add_user(message: Message, command: CommandObject, **kwargs) -> None:
        """Admin only: Add a user to the database with optional prefix."""
        user_service = kwargs.get("user_service")
        if not user_service:
            raise RuntimeError("user_service not provided in kwargs")

        if message.from_user.id not in admin_ids:
            logger.warning(
                "Unauthorized admin command attempt",
                user_id=message.from_user.id,
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
                user_service.validate_prefix(prefix, allow_empty=True)
            except Exception as e:
                await message.answer(f"❌ {e}")
                return

            await user_service.add_user(telegram_id, prefix)
            await message.answer(
                f"✅ User {telegram_id} added. Prefix: `{prefix or 'none'}`"
            )
            logger.info(
                "Admin added user",
                admin_id=message.from_user.id,
                user_id=telegram_id,
                prefix=prefix,
            )
        except (ValueError, IndexError) as e:
            await message.answer(
                "❌ Invalid format. Use: /add_user <telegram_id> [prefix]"
            )
            logger.error("Invalid add_user command format", error=str(e))
        except Exception as e:
            await message.answer("❌ Failed to add user")
            logger.error("Failed to add user", error=str(e))

    async def cmd_remove_user(
        message: Message, command: CommandObject, **kwargs
    ) -> None:
        """Admin only: Remove a user from the database."""
        user_service = kwargs.get("user_service")
        if not user_service:
            raise RuntimeError("user_service not provided in kwargs")

        if message.from_user.id not in admin_ids:
            logger.warning(
                "Unauthorized admin command attempt",
                user_id=message.from_user.id,
            )
            return

        if not command.args:
            await message.answer("Usage: /remove_user <telegram_id>")
            return

        try:
            telegram_id = int(command.args.strip())
            await user_service.remove_user(telegram_id)
            await message.answer(f"✅ User {telegram_id} removed.")
            logger.info(
                "Admin removed user",
                admin_id=message.from_user.id,
                user_id=telegram_id,
            )
        except ValueError as e:
            await message.answer("❌ Invalid telegram ID format")
            logger.error("Invalid remove_user command format", error=str(e))
        except Exception as e:
            await message.answer("❌ Failed to remove user")
            logger.error("Failed to remove user", error=str(e))

    async def cmd_list_users(message: Message, **kwargs) -> None:
        """Admin only: List all users with their prefixes."""
        user_service = kwargs.get("user_service")
        if not user_service:
            raise RuntimeError("user_service not provided in kwargs")

        if message.from_user.id not in admin_ids:
            logger.warning(
                "Unauthorized admin command attempt",
                user_id=message.from_user.id,
            )
            return

        try:
            users = await user_service.get_all_users()

            if not users:
                await message.answer("No users in database.")
                return

            text = "📋 Users:\n"
            for user in users:
                text += f"✅ {user.telegram_id} - prefix: `{user.prefix or 'none'}`\n"
            await message.answer(text)
            logger.info(
                "Admin listed users",
                admin_id=message.from_user.id,
                user_count=len(users),
            )
        except Exception as e:
            await message.answer("❌ Failed to list users")
            logger.error("Failed to list users", error=str(e))

    async def cmd_status(message: Message, **kwargs) -> None:
        """Admin only: Show bot status and system information."""
        user_service = kwargs.get("user_service")
        if not user_service:
            raise RuntimeError("user_service not provided in kwargs")

        if message.from_user.id not in admin_ids:
            logger.warning(
                "Unauthorized admin command attempt",
                user_id=message.from_user.id,
            )
            return

        try:
            users = await user_service.get_all_users()
            uptime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            status_text = "📊 **Bot Status**\n\n"
            status_text += f"🕐 **Time**: {uptime}\n"
            status_text += f"👥 **Users**: {len(users)} registered\n"
            status_text += f"🤖 **Python**: {platform.python_version()}\n"
            status_text += f"💻 **System**: {platform.system()} {platform.release()}\n"
            status_text += f"🔧 **Admins**: {len(admin_ids)} configured\n"

            # Check if using local API
            status_text += (
                f"🌐 **API**: {'Local' if config.use_local_api else 'Standard'}\n"
            )

            await message.answer(status_text, parse_mode="Markdown")
            logger.info(
                "Admin requested status",
                admin_id=message.from_user.id,
            )
        except Exception as e:
            await message.answer("❌ Failed to get status")
            logger.error("Failed to get status", error=str(e))

    return (cmd_add_user, cmd_remove_user, cmd_list_users, cmd_status)

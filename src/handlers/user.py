import re

from aiogram.filters import CommandObject
from aiogram.types import BotCommand, BotCommandScopeChat, Message

from src.db.database import Database
from src.exceptions import ValidationError
from src.logging_config import get_logger

logger = get_logger(__name__)


def is_valid_prefix(prefix: str) -> bool:
    """Validate prefix: only latin alphanumeric characters and underscore, 1-10 chars."""
    return (
        bool(prefix)
        and 1 <= len(prefix) <= 10
        and bool(re.match(r"^[a-zA-Z0-9_]+$", prefix))
    )


def validate_prefix(prefix: str) -> None:
    """Validate prefix and raise ValidationError if invalid."""
    if not prefix:
        raise ValidationError("Prefix cannot be empty")
    if not (1 <= len(prefix) <= 10):
        raise ValidationError("Prefix must be 1-10 characters long")
    if not re.match(r"^[a-zA-Z0-9_]+$", prefix):
        raise ValidationError(
            "Prefix must contain only latin letters, numbers, and underscores"
        )


async def cmd_start(
    message: Message, user_data: tuple, bot, admin_ids: list[int], **kwargs
) -> None:
    """Handle /start command - show greeting with current prefix and update commands."""
    prefix = user_data[0] or ""
    try:
        await message.answer(
            f"👋 Hello! Your prefix: `{prefix or 'not set'}`\n\n"
            "Send files to save them as gzip\n"
            "Use /set_prefix to set your file prefix"
        )
        logger.info("User started bot", user_id=message.from_user.id)

        # Update commands for this user based on their role
        await set_commands(bot, admin_ids=admin_ids, user_id=message.from_user.id)
    except Exception as e:
        logger.error(
            "Failed to send start message",
            user_id=message.from_user.id,
            error=str(e),
        )
        raise


async def cmd_my_prefix(message: Message, user_data: tuple) -> None:
    """Handle /my_prefix command - show current user prefix."""
    prefix = user_data[0] or ""
    try:
        if prefix:
            await message.answer(f"📝 Your prefix: `{prefix}`")
        else:
            await message.answer(
                "❌ You don't have a prefix set. Use /set_prefix to set one."
            )
        logger.info("User requested their prefix", user_id=message.from_user.id)
    except Exception as e:
        logger.error(
            "Failed to send prefix",
            user_id=message.from_user.id,
            error=str(e),
        )
        raise


async def cmd_set_prefix(
    message: Message, command: CommandObject, user_data: tuple, db: Database
) -> None:
    """Handle /set_prefix command - set user's file prefix (1-10 latin chars)."""
    if not command.args:
        await message.answer(
            "Usage: /set_prefix <prefix> (1-10 latin alphanumeric characters)"
        )
        return

    prefix = command.args.strip()
    try:
        validate_prefix(prefix)
    except ValidationError as e:
        await message.answer(f"❌ {e}")
        return

    try:
        await db.set_prefix(message.from_user.id, prefix)
        await message.answer(f"✅ Prefix set to: `{prefix}`")
        logger.info(
            "User set prefix",
            user_id=message.from_user.id,
            prefix=prefix,
        )
    except Exception as e:
        logger.error(
            "Failed to set prefix",
            user_id=message.from_user.id,
            error=str(e),
        )
        await message.answer("❌ Failed to set prefix. Please try again.")


async def set_commands(
    bot, admin_ids: list[int] | None = None, user_id: int | None = None
) -> None:
    """Set bot commands menu based on user role.

    Args:
        bot: Bot instance
        admin_ids: List of admin IDs
        user_id: Specific user ID to set commands for (for /start handler)
    """
    admin_ids = admin_ids or []

    # Basic commands for all users
    basic_commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="my_prefix", description="Show your prefix"),
        BotCommand(command="set_prefix", description="Set file prefix (1-10 chars)"),
    ]

    # Admin commands (only for admins)
    admin_commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="my_prefix", description="Show your prefix"),
        BotCommand(command="set_prefix", description="Set file prefix (1-10 chars)"),
        BotCommand(command="add_user", description="Add user"),
        BotCommand(command="remove_user", description="Remove user"),
        BotCommand(command="list_users", description="List all users"),
        BotCommand(command="status", description="Bot status"),
    ]

    # Set commands only for specific user (called from /start)
    if user_id:
        commands = admin_commands if user_id in admin_ids else basic_commands
        try:
            await bot.set_my_commands(
                commands, scope=BotCommandScopeChat(chat_id=user_id)
            )
            logger.info(
                "Commands set for user",
                user_id=user_id,
                is_admin=user_id in admin_ids,
            )
        except Exception as e:
            logger.warning(
                "Failed to set commands for user",
                user_id=user_id,
                error=str(e),
            )
        return

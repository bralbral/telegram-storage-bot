import logging
import re

from aiogram.filters import CommandObject
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    Message,
)

from src.db.database import Database
from src.exceptions import ValidationError

logger = logging.getLogger(__name__)


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


async def cmd_start(message: Message, user_data: tuple) -> None:
    """Handle /start command - show greeting with current prefix."""
    prefix = user_data[0] or ""
    try:
        await message.answer(
            f"👋 Hello! Your prefix: `{prefix or 'not set'}`\n\n"
            "Send files to save them as gzip\n"
            "Use /set_prefix to set your file prefix"
        )
        logger.info(f"User {message.from_user.id} started bot")
    except Exception as e:
        logger.error(
            f"Failed to send start message to user {message.from_user.id}: {e}"
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
        logger.info(f"User {message.from_user.id} requested their prefix")
    except Exception as e:
        logger.error(f"Failed to send prefix to user {message.from_user.id}: {e}")
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
        logger.info(f"User {message.from_user.id} set prefix to '{prefix}'")
    except Exception as e:
        logger.error(f"Failed to set prefix for user {message.from_user.id}: {e}")
        await message.answer("❌ Failed to set prefix. Please try again.")


async def set_commands(bot, admin_ids: list[int] | None = None) -> None:
    """Set bot commands menu based on user role."""
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

    try:
        # Set basic commands for all private chats
        await bot.set_my_commands(
            basic_commands, scope=BotCommandScopeAllPrivateChats()
        )
        logger.info("Basic commands set for all users")

        # Set admin commands for each admin
        for admin_id in admin_ids:
            await bot.set_my_commands(
                admin_commands, scope=BotCommandScopeChat(chat_id=admin_id)
            )
        logger.info(f"Admin commands set for {len(admin_ids)} admin(s)")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
        raise

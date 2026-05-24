import logging
import re

from aiogram.filters import CommandObject
from aiogram.types import BotCommand, Message

from db.database import db

logger = logging.getLogger(__name__)


def is_valid_prefix(prefix: str) -> bool:
    """Validate prefix: only latin alphanumeric characters, max 5 chars."""
    return (
        bool(prefix) and len(prefix) <= 5 and bool(re.match(r"^[a-zA-Z0-9_]+$", prefix))
    )


async def cmd_start(message: Message, user_data: tuple):
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


async def cmd_set_prefix(message: Message, command: CommandObject, user_data: tuple):
    """Handle /set_prefix command - set user's file prefix (max 5 latin chars)."""
    if not command.args:
        await message.answer(
            "Usage: /set_prefix <prefix> (max 5 latin alphanumeric characters)"
        )
        return

    prefix = command.args.strip()
    if not is_valid_prefix(prefix):
        await message.answer(
            "❌ Prefix must be 1-5 latin alphanumeric characters (a-z, A-Z, 0-9, _)."
        )
        return

    try:
        await db.set_prefix(message.from_user.id, prefix)
        await message.answer(f"✅ Prefix set to: `{prefix}`")
        logger.info(f"User {message.from_user.id} set prefix to '{prefix}'")
    except Exception as e:
        logger.error(f"Failed to set prefix for user {message.from_user.id}: {e}")
        await message.answer("❌ Failed to set prefix. Please try again.")


async def set_commands(bot):
    """Set bot commands menu in Telegram."""
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="set_prefix", description="Set file prefix (5 chars)"),
        BotCommand(command="add_user", description="[Admin] Add user"),
        BotCommand(command="remove_user", description="[Admin] Remove user"),
        BotCommand(command="list_users", description="[Admin] List all users"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
        raise

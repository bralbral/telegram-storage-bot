from aiogram.filters import Command, CommandObject
from aiogram.types import BotCommand, Message

from db.database import db


async def cmd_start(message: Message, user_data: tuple):
    """Handle /start command - show greeting with current prefix."""
    prefix = user_data[0] or ""
    await message.answer(
        f"👋 Hello! Your prefix: `{prefix or 'not set'}`\n\n"
        "Send files to save them as gzip\n"
        "Use /set_prefix to set your file prefix"
    )


async def cmd_set_prefix(message: Message, command: CommandObject, user_data: tuple):
    """Handle /set_prefix command - set user's file prefix (max 5 latin chars)."""
    if not command.args:
        await message.answer("Usage: /set_prefix <prefix> (max 5 latin characters)")
        return

    prefix = command.args.strip()[:5]
    if not prefix.isascii() or not prefix.isalnum():
        await message.answer("❌ Prefix must be latin alphanumeric characters only.")
        return

    await db.set_prefix(message.from_user.id, prefix)
    await message.answer(f"✅ Prefix set to: `{prefix}`")


async def set_commands(bot):
    """Set bot commands menu in Telegram."""
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="set_prefix", description="Set file prefix (5 chars)"),
        BotCommand(command="add_user", description="[Admin] Add user"),
        BotCommand(command="remove_user", description="[Admin] Remove user"),
        BotCommand(command="list_users", description="[Admin] List all users"),
    ]
    await bot.set_my_commands(commands)
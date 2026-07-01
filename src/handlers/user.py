from __future__ import annotations

import asyncio

from aiogram.filters import CommandObject
from aiogram.types import BotCommand, BotCommandScopeChat, Message

from src.logging_config import get_logger

logger = get_logger(__name__)


async def cmd_start(message: Message, **kwargs) -> None:
    """Handle /start command - show greeting with current prefix and update commands."""
    user_data = kwargs.get("user_data", ("", False))
    bot = kwargs.get("bot")
    admin_ids = kwargs.get("admin_ids", [])

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


async def cmd_my_prefix(message: Message, **kwargs) -> None:
    """Handle /my_prefix command - show current user prefix."""
    user_data = kwargs.get("user_data", ("", False))
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


async def cmd_set_prefix(message: Message, command: CommandObject, **kwargs) -> None:
    """Handle /set_prefix command - set user's file prefix (1-10 latin chars)."""
    user_service = kwargs.get("user_service")
    if not user_service:
        raise RuntimeError("user_service not provided in kwargs")

    if not command.args:
        await message.answer(
            "Usage: /set_prefix <prefix> (1-10 latin alphanumeric characters)"
        )
        return

    prefix = command.args.strip()
    try:
        await user_service.set_prefix(message.from_user.id, prefix)
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


async def cmd_buffer(message: Message, **kwargs) -> None:
    """Handle /buffer command - show files in buffer."""
    file_service = kwargs.get("file_service")
    if not file_service:
        raise RuntimeError("file_service not provided in kwargs")

    user_id = message.from_user.id
    buffer = file_service.get_buffer(user_id)

    if not buffer:
        await message.answer("📭 Buffer is empty. Send files to add them.")
        return

    total_size = file_service.get_buffer_size(user_id)
    size_mb = total_size / (1024 * 1024) if total_size else 0

    files_list = "\n".join(
        [
            f"• {f.file_type}: {f.filename} ({int(f.file_size or 0) / (1024 * 1024):.1f} MB)"
            if f.file_size
            else f"• {f.file_type}: {f.filename}"
            for f in buffer
        ]
    )

    await message.answer(
        f"📦 Buffer: {len(buffer)} file(s)\n"
        f"📊 Total size: {size_mb:.1f} MB\n\n"
        f"{files_list}\n\n"
        f"Use /drop to save all or /clear to empty buffer."
    )
    logger.info("User viewed buffer", user_id=user_id, count=len(buffer))


async def cmd_clear(message: Message, **kwargs) -> None:
    """Handle /clear command - clear buffer."""
    file_service = kwargs.get("file_service")
    if not file_service:
        raise RuntimeError("file_service not provided in kwargs")

    user_id = message.from_user.id
    count = file_service.clear_buffer(user_id)

    await message.answer(f"🗑️ Buffer cleared ({count} file(s) removed).")
    logger.info("User cleared buffer", user_id=user_id, removed=count)


async def cmd_drop(message: Message, **kwargs) -> None:
    """Handle /drop command - save all files from buffer as tar.gz archive."""
    user_data = kwargs.get("user_data", ("", False))
    bot = kwargs.get("bot")
    file_service = kwargs.get("file_service")

    if not file_service or not bot:
        raise RuntimeError("file_service or bot not provided in kwargs")

    user_id = message.from_user.id
    buffer = file_service.get_buffer(user_id)

    if not buffer:
        await message.answer("📭 Buffer is empty. Send files first.")
        return

    prefix = user_data[0] or ""
    await message.reply(f"⏳ Processing {len(buffer)} file(s)...")

    async def process_archive() -> None:
        """Process archive creation in background."""
        try:
            archive_name = await file_service.create_archive_from_buffer(
                user_id, prefix, bot
            )
            await message.reply(f"✅ Archive saved: {archive_name}")
            logger.info(
                "Buffer saved as archive",
                user_id=user_id,
                archive=archive_name,
                count=len(buffer),
            )
        except asyncio.CancelledError:
            logger.info(
                "Archive operation cancelled during shutdown",
                user_id=user_id,
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to save buffer as archive", user_id=user_id, error=str(e)
            )
            await message.reply("❌ Failed to save archive. Please try again.")

    task = asyncio.create_task(process_archive())
    file_service._running_tasks.add(task)
    task.add_done_callback(lambda t: file_service._running_tasks.discard(t))


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
        BotCommand(command="buffer", description="View file buffer"),
        BotCommand(command="clear", description="Clear file buffer"),
        BotCommand(command="drop", description="Save buffer as archive"),
    ]

    # Admin-only commands
    admin_commands = [
        BotCommand(command="add_user", description="Add user (admin only)"),
        BotCommand(command="remove_user", description="Remove user (admin only)"),
        BotCommand(command="list_users", description="List all users (admin only)"),
        BotCommand(command="status", description="Bot status (admin only)"),
    ]

    if user_id:
        # Set commands for specific user
        if user_id in admin_ids:
            await bot.set_my_commands(
                basic_commands + admin_commands,
                scope=BotCommandScopeChat(chat_id=user_id),
            )
        else:
            await bot.set_my_commands(
                basic_commands, scope=BotCommandScopeChat(chat_id=user_id)
            )
    else:
        # Set default commands for all users (no scope)
        await bot.set_my_commands(basic_commands)

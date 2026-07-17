from __future__ import annotations

import asyncio

from aiogram.filters import CommandObject
from aiogram.types import BotCommand, BotCommandScopeChat, Message

from src.logging_config import get_logger
from src.utils.size_utils import bytes_to_mb

logger = get_logger(__name__)


async def send_start_help(message: Message, prefix: str) -> None:
    """Send the common usage instructions shown by /start and /help."""
    await message.answer(
        f"👋 Hello! Your prefix: <code>{prefix or 'not set'}</code>\n\n"
        "<b>Files</b>\n"
        "• Send a file to add it to the queue.\n"
        "• <code>/buffer</code> — view the queue\n"
        "• <code>/drop</code> — create an archive\n"
        "• <code>/clear</code> — empty the queue\n\n"
        "<b>Text in one file</b>\n"
        "1. <code>/text</code> — start collecting text\n"
        "2. Send the text parts\n"
        "3. <code>/endtext</code> — add the .txt file to the queue\n"
        "<code>/canceltext</code> — cancel collection\n\n"
        "<b>Docker image</b>\n"
        "Send: <code>docker pull nginx:latest</code>\n\n"
        "<b>Python packages</b>\n"
        "Supported Python versions: 3.7–3.14\n"
        "With dependencies: <code>pip download --python 3.12 requests</code>\n"
        "Pinned package: <code>pip download --python 3.12 requests==2.32.3</code>\n"
        "Wheels only: <code>pip download --python 3.12 --only-binary requests</code>\n"
        "Package only: <code>pip download --python 3.11 --no-deps requests</code>\n\n"
        "<code>/set_prefix &lt;name&gt;</code> — change the file prefix.\n"
        "<code>/help</code> — show this help message again.",
        parse_mode="HTML",
    )


async def cmd_start(message: Message, **kwargs) -> None:
    """Show the greeting and help message for /start and /help."""
    user_data = kwargs.get("user_data", ("", False))
    bot = kwargs.get("bot")
    admin_ids = kwargs.get("admin_ids", [])

    prefix = user_data[0] or ""
    try:
        await send_start_help(message, prefix)
        logger.info("User requested help", user_id=message.from_user.id)

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
                "❌ You don't have a prefix set.\nUse /set_prefix to set one."
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
    buffer = await file_service.get_buffer(user_id)

    if not buffer:
        await message.answer("📭 Buffer is empty.\nSend files to add them.")
        return

    total_size = file_service.get_buffer_size(buffer)

    files_list = "\n".join(
        [
            f"• {item.file_info.file_type}: {item.file_info.filename} "
            f"({bytes_to_mb(item.file_info.file_size):.1f} MB)"
            if item.file_info.file_size
            else f"• {item.file_info.file_type}: {item.file_info.filename}"
            for item in buffer
        ]
    )

    await message.answer(
        f"📦 Buffer: {len(buffer)} file(s)\n"
        f"📊 Total size: {bytes_to_mb(total_size):.1f} MB\n\n"
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
    try:
        count = await file_service.clear_buffer(user_id)
    except RuntimeError as e:
        await message.answer(f"❌ {e}")
        return

    await message.answer(f"🗑️ Buffer cleared ({count} file(s) removed).")
    logger.info("User cleared buffer", user_id=user_id, removed=count)


async def cmd_text(message: Message, **kwargs) -> None:
    """Start collecting messages into one text file."""
    file_service = kwargs.get("file_service")
    if not file_service:
        raise RuntimeError("file_service not provided in kwargs")
    try:
        await file_service.start_text_collection(message.from_user.id)
    except (ValueError, RuntimeError) as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer("📝 Text collection started.\nSend parts, then use /endtext.")


async def cmd_endtext(message: Message, **kwargs) -> None:
    """Finish a text collection and queue its single text file."""
    file_service = kwargs.get("file_service")
    if not file_service:
        raise RuntimeError("file_service not provided in kwargs")
    try:
        file_info, buffer_count = await file_service.finish_text_collection(
            message.from_user.id
        )
    except (ValueError, RuntimeError) as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer(
        f"📝 Text saved as {file_info.filename} and added to buffer "
        f"({buffer_count} file(s)).\n"
        "Use /drop to save all, /buffer to view, or /clear to empty the queue."
    )


async def cmd_canceltext(message: Message, **kwargs) -> None:
    """Discard an unfinished text collection."""
    file_service = kwargs.get("file_service")
    if not file_service:
        raise RuntimeError("file_service not provided in kwargs")
    count = await file_service.cancel_text_collection(message.from_user.id)
    if count:
        await message.answer(f"🗑️ Text collection cancelled ({count} part(s) removed).")
    else:
        await message.answer("📭 No active text collection.")


async def cmd_drop(message: Message, **kwargs) -> None:
    """Handle /drop command - save all files from buffer as tar.gz archive."""
    user_data = kwargs.get("user_data", ("", False))
    bot = kwargs.get("bot")
    file_service = kwargs.get("file_service")

    if not file_service or not bot:
        raise RuntimeError("file_service or bot not provided in kwargs")

    user_id = message.from_user.id
    try:
        buffer = await file_service.begin_archive(user_id)
    except ValueError:
        await message.answer("📭 Buffer is empty. Send files first.")
        return
    except RuntimeError:
        await message.answer(
            "⏳ Archive creation is already in progress.\nPlease wait."
        )
        return

    prefix = user_data[0] or ""
    logger.info("Archive requested", user_id=user_id, file_count=len(buffer))
    await message.reply(f"⏳ Processing {len(buffer)} file(s)...")

    async def process_archive() -> None:
        """Process archive creation in background."""
        try:
            (
                archive_name,
                archived_count,
                failed_count,
            ) = await file_service.create_archive_from_buffer(
                user_id, prefix, bot, buffer
            )
            result = f"✅ Archive saved: {archive_name} ({archived_count} file(s))"
            if failed_count:
                result += f"\n⚠️ {failed_count} file(s) failed and remain in the buffer."
            await message.reply(result)
            logger.info(
                "Buffer saved as archive",
                user_id=user_id,
                archive=archive_name,
                count=archived_count,
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
            await message.reply("❌ Failed to save archive.\nPlease try again.")

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
        BotCommand(command="help", description="Show usage instructions"),
        BotCommand(command="my_prefix", description="Show your prefix"),
        BotCommand(command="set_prefix", description="Set file prefix (1-10 chars)"),
        BotCommand(command="buffer", description="View file buffer"),
        BotCommand(command="clear", description="Clear file buffer"),
        BotCommand(command="drop", description="Save buffer as archive"),
        BotCommand(command="text", description="Start collecting one text file"),
        BotCommand(command="endtext", description="Finish and queue collected text"),
        BotCommand(command="canceltext", description="Cancel collected text"),
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

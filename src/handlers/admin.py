from __future__ import annotations

from collections.abc import Awaitable, Callable

from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from db.database import db


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
            return

        if not command.args:
            return

        parts = command.args.strip().split()
        telegram_id = int(parts[0])
        prefix = parts[1] if len(parts) > 1 else ""

        await db.add_user(telegram_id, prefix)
        await message.answer(f"✅ User {telegram_id} added. Prefix: `{prefix or 'none'}`")

    async def cmd_remove_user(message: Message, command: CommandObject) -> None:
        """Admin only: Remove a user from the database."""
        if message.from_user.id not in admin_ids:
            return

        if not command.args:
            return

        telegram_id = int(command.args.strip())
        await db.remove_user(telegram_id)
        await message.answer(f"✅ User {telegram_id} removed.")

    async def cmd_list_users(message: Message) -> None:
        """Admin only: List all users with their prefixes."""
        if message.from_user.id not in admin_ids:
            return

        users = await db.get_all_users()

        if not users:
            await message.answer("No users in database.")
            return

        text = "📋 Users:\n"
        for uid, prefix in users:
            text += f"✅ {uid} - prefix: `{prefix or 'none'}`\n"
        await message.answer(text)

    return cmd_add_user, cmd_remove_user, cmd_list_users
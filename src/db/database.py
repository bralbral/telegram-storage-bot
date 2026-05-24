from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from utils.variables import DB_PATH

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager for user storage."""

    __slots__ = ("path",)

    def __init__(self, path: str | Path = DB_PATH) -> None:
        self.path = str(path)

    async def init(self) -> None:
        """Create users table if it doesn't exist."""
        try:
            async with aiosqlite.connect(self.path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER UNIQUE NOT NULL,
                        prefix TEXT
                    )
                    """
                )
                await db.commit()
            logger.info("Database initialized successfully")
        except aiosqlite.Error as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def get_user(self, telegram_id: int) -> str | None:
        """Get user by telegram_id, returns prefix string or None.

        Args:
            telegram_id: The Telegram user ID to look up

        Returns:
            The user's prefix if found, None otherwise
        """
        try:
            async with aiosqlite.connect(self.path) as db:
                cursor = await db.execute(
                    "SELECT prefix FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                )
                result = await cursor.fetchone()
                return result[0] if result else None
        except aiosqlite.Error as e:
            logger.error(f"Failed to get user {telegram_id}: {e}")
            return None

    async def add_user(self, telegram_id: int, prefix: str = "") -> None:
        """Add a user to the database.

        Args:
            telegram_id: The Telegram user ID to add
            prefix: Optional prefix for the user

        Raises:
            aiosqlite.Error: If database operation fails
        """
        try:
            async with aiosqlite.connect(self.path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO users (telegram_id, prefix) VALUES (?, ?)",
                    (telegram_id, prefix),
                )
                await db.commit()
            logger.info(f"User {telegram_id} added with prefix '{prefix}'")
        except aiosqlite.Error as e:
            logger.error(f"Failed to add user {telegram_id}: {e}")
            raise

    async def set_prefix(self, telegram_id: int, prefix: str) -> None:
        """Update user's prefix.

        Args:
            telegram_id: The Telegram user ID to update
            prefix: The new prefix to set

        Raises:
            aiosqlite.Error: If database operation fails
        """
        try:
            async with aiosqlite.connect(self.path) as db:
                await db.execute(
                    "UPDATE users SET prefix = ? WHERE telegram_id = ?",
                    (prefix, telegram_id),
                )
                await db.commit()
            logger.info(f"Prefix updated for user {telegram_id}: '{prefix}'")
        except aiosqlite.Error as e:
            logger.error(f"Failed to set prefix for user {telegram_id}: {e}")
            raise

    async def remove_user(self, telegram_id: int) -> None:
        """Remove user from the database.

        Args:
            telegram_id: The Telegram user ID to remove

        Raises:
            aiosqlite.Error: If database operation fails
        """
        try:
            async with aiosqlite.connect(self.path) as db:
                await db.execute(
                    "DELETE FROM users WHERE telegram_id = ?", (telegram_id,)
                )
                await db.commit()
            logger.info(f"User {telegram_id} removed")
        except aiosqlite.Error as e:
            logger.error(f"Failed to remove user {telegram_id}: {e}")
            raise

    async def get_all_users(self) -> list[tuple[int, str | None]]:
        """Get all users from database.

        Returns:
            List of tuples containing (telegram_id, prefix) for all users
        """
        try:
            async with aiosqlite.connect(self.path) as db:
                cursor = await db.execute("SELECT telegram_id, prefix FROM users")
                return await cursor.fetchall()
        except aiosqlite.Error as e:
            logger.error(f"Failed to get all users: {e}")
            return []


db = Database()

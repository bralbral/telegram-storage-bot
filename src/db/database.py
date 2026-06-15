from __future__ import annotations

from pathlib import Path

import aiosqlite

from src.exceptions import DatabaseError
from src.logging_config import get_logger

logger = get_logger(__name__)


class Database:
    """SQLite database manager for user storage with connection pooling."""

    __slots__ = ("path", "_connection")

    def __init__(self, path: str | Path) -> None:
        self.path = str(path) if isinstance(path, Path) else path
        self._connection: aiosqlite.Connection | None = None

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create a singleton database connection."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.path)
            await self._connection.execute("PRAGMA journal_mode=WAL")
            await self._connection.execute("PRAGMA synchronous=NORMAL")
        return self._connection

    async def init(self) -> None:
        """Create users table if it doesn't exist."""
        try:
            db = await self._get_connection()
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
            logger.error("Database initialization failed", error=str(e))
            raise DatabaseError(f"Failed to initialize database: {e}") from e

    async def get_user(self, telegram_id: int) -> str | None:
        """Get user by telegram_id, returns prefix string or None.

        Args:
            telegram_id: The Telegram user ID to look up

        Returns:
            The user's prefix if found, None otherwise
        """
        try:
            db = await self._get_connection()
            cursor = await db.execute(
                "SELECT prefix FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            result = await cursor.fetchone()
            return result[0] if result else None
        except aiosqlite.Error as e:
            logger.error("Failed to get user", telegram_id=telegram_id, error=str(e))
            raise DatabaseError(f"Failed to get user {telegram_id}: {e}") from e

    async def add_user(self, telegram_id: int, prefix: str = "") -> None:
        """Add a user to the database.

        Args:
            telegram_id: The Telegram user ID to add
            prefix: Optional prefix for the user

        Raises:
            aiosqlite.Error: If database operation fails
        """
        try:
            db = await self._get_connection()
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, prefix) VALUES (?, ?)",
                (telegram_id, prefix),
            )
            await db.commit()
            logger.info("User added", telegram_id=telegram_id, prefix=prefix)
        except aiosqlite.Error as e:
            logger.error("Failed to add user", telegram_id=telegram_id, error=str(e))
            raise DatabaseError(f"Failed to add user {telegram_id}: {e}") from e

    async def set_prefix(self, telegram_id: int, prefix: str) -> None:
        """Update user's prefix.

        Args:
            telegram_id: The Telegram user ID to update
            prefix: The new prefix to set

        Raises:
            aiosqlite.Error: If database operation fails
        """
        try:
            db = await self._get_connection()
            await db.execute(
                "UPDATE users SET prefix = ? WHERE telegram_id = ?",
                (prefix, telegram_id),
            )
            await db.commit()
            logger.info("Prefix updated", telegram_id=telegram_id, prefix=prefix)
        except aiosqlite.Error as e:
            logger.error("Failed to set prefix", telegram_id=telegram_id, error=str(e))
            raise DatabaseError(
                f"Failed to set prefix for user {telegram_id}: {e}"
            ) from e

    async def remove_user(self, telegram_id: int) -> None:
        """Remove user from database.

        Args:
            telegram_id: The Telegram user ID to remove

        Raises:
            aiosqlite.Error: If database operation fails
        """
        try:
            db = await self._get_connection()
            await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
            await db.commit()
            logger.info("User removed", telegram_id=telegram_id)
        except aiosqlite.Error as e:
            logger.error("Failed to remove user", telegram_id=telegram_id, error=str(e))
            raise DatabaseError(f"Failed to remove user {telegram_id}: {e}") from e

    async def get_all_users(self) -> list[tuple[int, str | None]]:
        """Get all users from database.

        Returns:
            List of tuples containing (telegram_id, prefix) for all users
        """
        try:
            db = await self._get_connection()
            cursor = await db.execute("SELECT telegram_id, prefix FROM users")
            return await cursor.fetchall()
        except aiosqlite.Error as e:
            logger.error("Failed to get all users", error=str(e))
            raise DatabaseError(f"Failed to get all users: {e}") from e

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

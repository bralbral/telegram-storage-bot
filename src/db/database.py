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
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS buffered_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    file_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_buffered_files_user "
                "ON buffered_files (telegram_id, id)"
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

    async def get_user_state(self, telegram_id: int) -> tuple[bool, str | None]:
        """Return registration state and prefix in one database query."""
        try:
            db = await self._get_connection()
            cursor = await db.execute(
                "SELECT prefix FROM users WHERE telegram_id = ?", (telegram_id,)
            )
            result = await cursor.fetchone()
            return (result is not None, result[0] if result else None)
        except aiosqlite.Error as e:
            logger.error(
                "Failed to get user state", telegram_id=telegram_id, error=str(e)
            )
            raise DatabaseError(f"Failed to get user state {telegram_id}: {e}") from e

    async def add_buffered_file(
        self,
        telegram_id: int,
        file_id: str,
        filename: str,
        file_size: int | None,
        file_type: str,
    ) -> int:
        """Persist a file queued by a user and return its row id."""
        try:
            db = await self._get_connection()
            cursor = await db.execute(
                """
                INSERT INTO buffered_files
                    (telegram_id, file_id, filename, file_size, file_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                (telegram_id, file_id, filename, file_size, file_type),
            )
            await db.commit()
            return int(cursor.lastrowid)
        except aiosqlite.Error as e:
            logger.error(
                "Failed to add buffered file", telegram_id=telegram_id, error=str(e)
            )
            raise DatabaseError(f"Failed to add buffered file: {e}") from e

    async def get_buffered_files(
        self, telegram_id: int
    ) -> list[tuple[int, str, str, int | None, str]]:
        """Return queued files in insertion order."""
        try:
            db = await self._get_connection()
            cursor = await db.execute(
                """
                SELECT id, file_id, filename, file_size, file_type
                FROM buffered_files WHERE telegram_id = ? ORDER BY id
                """,
                (telegram_id,),
            )
            return await cursor.fetchall()
        except aiosqlite.Error as e:
            logger.error(
                "Failed to get buffered files", telegram_id=telegram_id, error=str(e)
            )
            raise DatabaseError(f"Failed to get buffered files: {e}") from e

    async def get_buffer_stats(self, telegram_id: int) -> tuple[int, int]:
        """Return number and total size of a user's queued files."""
        try:
            db = await self._get_connection()
            cursor = await db.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(file_size), 0)
                FROM buffered_files WHERE telegram_id = ?
                """,
                (telegram_id,),
            )
            count, total_size = await cursor.fetchone()
            return int(count), int(total_size)
        except aiosqlite.Error as e:
            logger.error(
                "Failed to get buffer stats", telegram_id=telegram_id, error=str(e)
            )
            raise DatabaseError(f"Failed to get buffer stats: {e}") from e

    async def delete_buffered_files(self, telegram_id: int, ids: list[int]) -> None:
        """Delete successfully archived queued files only."""
        if not ids:
            return
        try:
            db = await self._get_connection()
            placeholders = ", ".join("?" for _ in ids)
            await db.execute(
                f"DELETE FROM buffered_files WHERE telegram_id = ? AND id IN ({placeholders})",
                (telegram_id, *ids),
            )
            await db.commit()
        except aiosqlite.Error as e:
            logger.error(
                "Failed to delete buffered files", telegram_id=telegram_id, error=str(e)
            )
            raise DatabaseError(f"Failed to delete buffered files: {e}") from e

    async def clear_buffered_files(self, telegram_id: int) -> int:
        """Remove all queued files and return the number removed."""
        try:
            db = await self._get_connection()
            cursor = await db.execute(
                "DELETE FROM buffered_files WHERE telegram_id = ?", (telegram_id,)
            )
            await db.commit()
            return cursor.rowcount
        except aiosqlite.Error as e:
            logger.error(
                "Failed to clear buffered files", telegram_id=telegram_id, error=str(e)
            )
            raise DatabaseError(f"Failed to clear buffered files: {e}") from e

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

import aiosqlite

from utils.variables import DB_PATH


class Database:
    """SQLite database manager for user storage."""

    def __init__(self, path: str = DB_PATH):
        self.path = str(path)

    async def init(self):
        """Create users table if it doesn't exist."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    prefix TEXT
                )
            ''')
            await db.commit()

    async def get_user(self, telegram_id: int):
        """Get user by telegram_id, returns prefix string or None."""
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT prefix FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else None

    async def add_user(self, telegram_id: int, prefix: str = ""):
        """Add a user to the database."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, prefix) VALUES (?, ?)",
                (telegram_id, prefix)
            )
            await db.commit()

    async def set_prefix(self, telegram_id: int, prefix: str):
        """Update user's prefix."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET prefix = ? WHERE telegram_id = ?",
                (prefix, telegram_id)
            )
            await db.commit()

    async def remove_user(self, telegram_id: int):
        """Remove user from the database."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
            await db.commit()

    async def get_all_users(self):
        """Get all users from database, returns list of (telegram_id, prefix)."""
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT telegram_id, prefix FROM users"
            )
            return await cursor.fetchall()

    async def has_access(self, telegram_id: int) -> bool:
        """Check if user exists in database."""
        return await self.get_user(telegram_id) is not None


db = Database()
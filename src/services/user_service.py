from __future__ import annotations

import re

from src.db.database import Database
from src.exceptions import ValidationError
from src.logging_config import get_logger
from src.models.user import User

logger = get_logger(__name__)


class UserService:
    """Service for user-related operations."""

    def __init__(self, db: Database) -> None:
        """Initialize user service.

        Args:
            db: Database instance
        """
        self.db = db

    @staticmethod
    def validate_prefix(prefix: str, allow_empty: bool = False) -> None:
        """Validate prefix and raise ValidationError if invalid.

        Args:
            prefix: Prefix to validate
            allow_empty: Whether empty prefix is allowed (for admin add)

        Raises:
            ValidationError: If prefix is invalid
        """
        if not prefix and not allow_empty:
            raise ValidationError("Prefix cannot be empty")
        if prefix and not (1 <= len(prefix) <= 10):
            raise ValidationError("Prefix must be 1-10 characters long")
        if prefix and not re.match(r"^[a-zA-Z0-9_]+$", prefix):
            raise ValidationError(
                "Prefix must contain only latin letters, numbers, and underscores"
            )

    async def get_user(self, telegram_id: int) -> User | None:
        """Get user by telegram_id.

        Args:
            telegram_id: The Telegram user ID to look up

        Returns:
            User object if found, None otherwise
        """
        try:
            prefix = await self.db.get_user(telegram_id)
            if prefix is not None:
                return User(telegram_id=telegram_id, prefix=prefix or "")
            return None
        except Exception as e:
            logger.error("Failed to get user", telegram_id=telegram_id, error=str(e))
            raise

    async def add_user(self, telegram_id: int, prefix: str = "") -> None:
        """Add a user to the database.

        Args:
            telegram_id: The Telegram user ID to add
            prefix: Optional prefix for the user

        Raises:
            ValidationError: If prefix is invalid
        """
        try:
            self.validate_prefix(prefix, allow_empty=True)
            await self.db.add_user(telegram_id, prefix)
            logger.info("User added", telegram_id=telegram_id, prefix=prefix)
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Failed to add user", telegram_id=telegram_id, error=str(e))
            raise

    async def set_prefix(self, telegram_id: int, prefix: str) -> None:
        """Update user's prefix.

        Args:
            telegram_id: The Telegram user ID to update
            prefix: The new prefix to set

        Raises:
            ValidationError: If prefix is invalid
        """
        try:
            self.validate_prefix(prefix, allow_empty=False)
            await self.db.set_prefix(telegram_id, prefix)
            logger.info("Prefix updated", telegram_id=telegram_id, prefix=prefix)
        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to set prefix",
                telegram_id=telegram_id,
                error=str(e),
            )
            raise

    async def remove_user(self, telegram_id: int) -> None:
        """Remove user from database.

        Args:
            telegram_id: The Telegram user ID to remove
        """
        try:
            await self.db.remove_user(telegram_id)
            logger.info("User removed", telegram_id=telegram_id)
        except Exception as e:
            logger.error("Failed to remove user", telegram_id=telegram_id, error=str(e))
            raise

    async def get_all_users(self) -> list[User]:
        """Get all users from database.

        Returns:
            List of User objects
        """
        try:
            users_data = await self.db.get_all_users()
            return [
                User(telegram_id=uid, prefix=prefix or "") for uid, prefix in users_data
            ]
        except Exception as e:
            logger.error("Failed to get all users", error=str(e))
            raise

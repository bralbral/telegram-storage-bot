from __future__ import annotations


class StorageBotError(Exception):
    """Base exception for storage bot errors."""

    pass


class DatabaseError(StorageBotError):
    """Database operation errors."""

    pass


class FileError(StorageBotError):
    """File operation errors."""

    pass


class DockerError(StorageBotError):
    """Docker operation errors."""

    pass


class ValidationError(StorageBotError):
    """Input validation errors."""

    pass


class AuthenticationError(StorageBotError):
    """Authentication and authorization errors."""

    pass

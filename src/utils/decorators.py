from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from aiogram.types import Message

from src.logging_config import get_logger

logger = get_logger(__name__)


def admin_only(admin_ids: list[int]):
    """Decorator to restrict handler to admin users only.

    Args:
        admin_ids: List of admin Telegram IDs

    Returns:
        Decorator function
    """

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(message: Message, *args: Any, **kwargs: Any) -> Any:
            if message.from_user.id not in admin_ids:
                logger.warning(
                    "Unauthorized admin command attempt",
                    user_id=message.from_user.id,
                )
                return
            return await handler(message, *args, **kwargs)

        return wrapper

    return decorator


def inject_service(service_name: str):
    """Decorator to extract service from kwargs and pass as named parameter.

    Args:
        service_name: Name of the service to extract from kwargs

    Returns:
        Decorator function
    """

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(message: Message, *args: Any, **kwargs: Any) -> Any:
            service = kwargs.get(service_name)
            if not service:
                raise RuntimeError(f"{service_name} not provided in kwargs")
            return await handler(message, service, *args, **kwargs)

        return wrapper

    return decorator

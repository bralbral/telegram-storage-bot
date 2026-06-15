from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with both console and file output.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure stdlib logging to output to stdout
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,  # Override any existing configuration
    )

    # Silence aiogram and other third-party library logs
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(
        logging.CRITICAL
    )  # Silence access logs
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Configure structlog with stdlib integration
    structlog.configure(
        processors=[
            # Add context from contextvars
            structlog.contextvars.merge_contextvars,
            # Add log level
            structlog.processors.add_log_level,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            # Handle exceptions
            structlog.processors.StackInfoRenderer(),
            # Use ConsoleRenderer for readable console output
            structlog.dev.ConsoleRenderer(),
        ],
        # Use stdlib integration for better compatibility
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        # Standard library logger factory
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Cache logger on first use for performance
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)

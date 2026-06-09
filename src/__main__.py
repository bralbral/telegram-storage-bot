from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.base import TelegramAPIServer
from aiogram.filters import Command

from src.db.database import Database
from src.handlers import docker, files, user
from src.handlers.admin import create_admin_handlers
from src.health import HealthServer
from src.logging_config import configure_logging, get_logger
from src.middlewares.access import AccessMiddleware
from src.middlewares.throttle import ThrottleMiddleware
from src.models.config import Config
from src.services.compression_service import CompressionService
from src.services.docker_service import DockerService
from src.services.file_service import FileService
from src.services.user_service import UserService


# Load environment variables from .env file if it exists (before logging setup)
def load_env_file() -> None:
    """Load environment variables from .env file if it exists."""
    env_file = Path(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
        )
    )
    if env_file.exists():
        try:
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")


load_env_file()

# Configure structlog
configure_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)


async def setup_bot() -> tuple[Bot, Dispatcher, HealthServer]:
    """Create and configure bot and dispatcher."""
    config = Config()

    # Create services directly
    database = Database(path=config.db_path)
    compression_service = CompressionService()
    download_dir = Path(config.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    user_service = UserService(database)
    file_service = FileService(
        compression_service=compression_service,
        download_dir=download_dir,
    )
    docker_service = DockerService(
        docker_host=config.docker_host,
        download_dir=download_dir,
    )

    bot_token = config.bot_token
    admin_ids = config.admin_ids_list

    if not bot_token:
        logger.error("Bot token is not configured")
        raise ValueError("Bot token is required")

    if config.use_local_api:
        bot = Bot(
            token=bot_token,
            session=AiohttpSession(
                api=TelegramAPIServer.from_base(config.local_api_url, is_local=True)
            ),
        )
        logger.info("Using local Bot API server")
    else:
        bot = Bot(token=bot_token)
        logger.info("Using standard Telegram Bot API")

    dp = Dispatcher()

    # Initialize database
    await database.init()
    await user.set_commands(bot, admin_ids)
    dp.message.outer_middleware(ThrottleMiddleware(config.throttle_rate, database))

    # Initialize access middleware with services
    dp.message.outer_middleware(
        AccessMiddleware(
            database,
            admin_ids,
            download_dir,
            bot,
            file_service=file_service,
            docker_service=docker_service,
            user_service=user_service,
        )
    )

    # Register user commands (services injected via middleware)
    dp.message.register(user.cmd_start, Command("start"))
    dp.message.register(user.cmd_my_prefix, Command("my_prefix"))
    dp.message.register(user.cmd_set_prefix, Command("set_prefix"))
    dp.message.register(user.cmd_buffer, Command("buffer"))
    dp.message.register(user.cmd_clear, Command("clear"))
    dp.message.register(user.cmd_drop, Command("drop"))

    # Register admin commands
    cmd_add_user, cmd_remove_user, cmd_list_users, cmd_status = create_admin_handlers(
        admin_ids, config
    )
    dp.message.register(cmd_add_user, Command("add_user"))
    dp.message.register(cmd_remove_user, Command("remove_user"))
    dp.message.register(cmd_list_users, Command("list_users"))
    dp.message.register(cmd_status, Command("status"))

    # Register file and docker handlers
    files.register_file_handlers(dp, file_service, config.max_file_size)
    docker.register_text_handlers(dp, docker_service)

    # Health check server
    health_server = HealthServer(port=config.health_port)

    logger.info(f"Bot configured with {len(admin_ids)} admin(s)")
    return bot, dp, health_server


async def run_bot() -> None:
    """Run the bot with graceful shutdown."""
    config = Config()
    bot, dp, health_server, database = (None, None, None, None)
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        bot, dp, health_server = await setup_bot()

        # Get database instance for cleanup
        database = Database(path=config.db_path)

        config.download_dir.mkdir(parents=True, exist_ok=True)

        # Start health check server
        await health_server.start()

        logger.info("Starting bot polling...")

        # Create tasks
        polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        # Wait for either polling to complete or shutdown signal
        done, pending = await asyncio.wait(
            [polling_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Stop polling if shutdown was triggered
        if shutdown_event.is_set():
            logger.info("Stopping bot polling...")
            await dp.stop_polling()
            logger.info("Bot polling stopped")

    except Exception as e:
        logger.error(f"Bot runtime error: {e}")
        raise
    finally:
        logger.info("Initiating cleanup...")
        try:
            # Close database
            if database:
                await database.close()
            if health_server:
                await health_server.stop()

            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(run_bot())

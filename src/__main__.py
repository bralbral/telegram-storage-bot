from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command

from src.config import Config
from src.db.database import Database
from src.handlers import docker, files, user
from src.handlers.admin import create_admin_handlers
from src.health import HealthServer
from src.middlewares.access import AccessMiddleware
from src.middlewares.throttle import ThrottleMiddleware
from src.task_manager import TaskManager


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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def setup_bot(
    config: Config,
) -> tuple[Bot, Dispatcher, HealthServer, Database, TaskManager]:
    """Create and configure bot and dispatcher."""
    bot_token = config.bot_token
    admin_ids = config.admin_ids

    if not bot_token:
        logger.error("Bot token is not configured")
        raise ValueError("Bot token is required")

    if config.use_local_api:
        bot = Bot(
            token=bot_token,
            api_server_url=config.local_api_url,
        )
        logger.info("Using local Bot API server")
    else:
        bot = Bot(token=bot_token)
        logger.info("Using standard Telegram Bot API")

    dp = Dispatcher()

    # Initialize database
    database = Database(config.db_path)
    await database.init()
    await user.set_commands(bot, admin_ids)
    dp.message.outer_middleware(ThrottleMiddleware(config.throttle_rate))

    # Initialize task manager
    task_manager_instance = TaskManager(config.max_concurrent_tasks)
    dp.message.outer_middleware(
        AccessMiddleware(
            database, admin_ids, task_manager_instance, config.download_dir
        )
    )

    dp.message.register(user.cmd_start, Command("start"))
    dp.message.register(user.cmd_set_prefix, Command("set_prefix"))

    cmd_add_user, cmd_remove_user, cmd_list_users, cmd_status = create_admin_handlers(
        admin_ids
    )
    dp.message.register(cmd_add_user, Command("add_user"))
    dp.message.register(cmd_remove_user, Command("remove_user"))
    dp.message.register(cmd_list_users, Command("list_users"))
    dp.message.register(cmd_status, Command("status"))

    files.register_file_handlers(dp, config.download_dir, config.max_file_size)
    docker.register_text_handlers(dp, config.download_dir)

    # Health check server
    health_server = HealthServer(port=config.health_port)

    logger.info(f"Bot configured with {len(admin_ids)} admin(s)")
    return bot, dp, health_server, database, task_manager_instance


async def run_bot() -> None:
    """Run the bot with graceful shutdown."""
    config = Config()
    bot, dp, health_server, database, task_manager_instance = (
        None,
        None,
        None,
        None,
        None,
    )
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        bot, dp, health_server, database, task_manager_instance = await setup_bot(
            config
        )
        config.download_dir.mkdir(parents=True, exist_ok=True)

        # Start health check server
        await health_server.start()

        logger.info("Starting bot polling...")

        # Create tasks
        polling_task = asyncio.create_task(dp.start_polling(bot))
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
            # Wait for background tasks to complete with TaskManager
            logger.info("Waiting for background tasks to complete...")
            if task_manager_instance:
                await task_manager_instance.shutdown(timeout=30)

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

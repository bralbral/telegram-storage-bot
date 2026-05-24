from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command

from src.db.database import Database
from src.handlers import docker, files, user
from src.handlers.admin import create_admin_handlers
from src.health import HealthServer
from src.middlewares.access import AccessMiddleware
from src.middlewares.throttle import ThrottleMiddleware
from src.task_manager import TaskManager
from src.utils.variables import DOWNLOAD_DIR


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


def get_config() -> dict:
    """Load configuration from environment variables only."""
    bot_token = os.getenv("BOT_TOKEN")
    use_local_api = os.getenv("USE_LOCAL_API", "false").lower() == "true"
    local_api_url = os.getenv("LOCAL_API_URL", "http://127.0.0.1:8081")

    admin_ids = []
    admin_ids_env = os.getenv("ADMIN_IDS")
    if admin_ids_env:
        try:
            admin_ids = [int(id.strip()) for id in admin_ids_env.split(",")]
        except ValueError:
            logger.error("Invalid ADMIN_IDS format in environment variables")

    return {
        "bot": {
            "token": bot_token,
            "use_local_api": use_local_api,
            "local_api_url": local_api_url,
            "admin_ids": admin_ids,
        }
    }


async def setup_bot() -> tuple[Bot, Dispatcher, HealthServer, Database, TaskManager]:
    """Create and configure bot and dispatcher."""
    config = get_config()

    bot_token = config["bot"]["token"]
    admin_ids = config["bot"]["admin_ids"]

    if not bot_token:
        logger.error("Bot token is not configured")
        raise ValueError("Bot token is required")

    if config["bot"]["use_local_api"]:
        bot = Bot(
            token=bot_token,
            api_server_url=config["bot"]["local_api_url"],
        )
        logger.info("Using local Bot API server")
    else:
        bot = Bot(token=bot_token)
        logger.info("Using standard Telegram Bot API")

    dp = Dispatcher()

    # Initialize database
    database = Database()
    await database.init()
    await user.set_commands(bot, admin_ids)
    dp.message.outer_middleware(ThrottleMiddleware())

    # Initialize task manager
    task_manager_instance = TaskManager()
    dp.message.outer_middleware(
        AccessMiddleware(database, admin_ids, task_manager_instance, DOWNLOAD_DIR)
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

    files.register_file_handlers(dp, DOWNLOAD_DIR)
    docker.register_text_handlers(dp, DOWNLOAD_DIR)

    # Health check server
    health_port = int(os.getenv("HEALTH_PORT", "8080"))
    health_server = HealthServer(port=health_port)

    logger.info(f"Bot configured with {len(admin_ids)} admin(s)")
    return bot, dp, health_server, database, task_manager_instance


async def run_bot() -> None:
    """Run the bot with graceful shutdown."""
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
        bot, dp, health_server, database, task_manager_instance = await setup_bot()
        DOWNLOAD_DIR.mkdir(exist_ok=True)

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

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command

from src.db.database import db
from src.handlers import docker, files, user
from src.middlewares.access import AccessMiddleware
from src.middlewares.throttle import ThrottleMiddleware
from src.utils.variables import DOWNLOAD_DIR


# Load environment variables from .env file if it exists (before logging setup)
def load_env_file() -> None:
    """Load environment variables from .env file if it exists."""
    env_file = Path(__file__).parent.parent.parent / ".env"
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


async def setup_bot() -> tuple[Bot, Dispatcher]:
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

    await db.init()
    await user.set_commands(bot, admin_ids)
    dp.message.outer_middleware(ThrottleMiddleware())
    dp.message.outer_middleware(AccessMiddleware(db, admin_ids))

    dp.message.register(user.cmd_start, Command("start"))
    dp.message.register(user.cmd_set_prefix, Command("set_prefix"))

    from src.handlers.admin import create_admin_handlers

    cmd_add_user, cmd_remove_user, cmd_list_users, cmd_status = create_admin_handlers(
        admin_ids
    )
    dp.message.register(cmd_add_user, Command("add_user"))
    dp.message.register(cmd_remove_user, Command("remove_user"))
    dp.message.register(cmd_list_users, Command("list_users"))
    dp.message.register(cmd_status, Command("status"))

    files.register_file_handlers(dp, DOWNLOAD_DIR)
    docker.register_text_handlers(dp, DOWNLOAD_DIR)

    logger.info(f"Bot configured with {len(admin_ids)} admin(s)")
    return bot, dp


async def run_bot() -> None:
    """Run the bot."""
    try:
        bot, dp = await setup_bot()
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot runtime error: {e}")
        raise
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(run_bot())

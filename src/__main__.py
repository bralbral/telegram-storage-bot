from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import yaml
from aiogram import Bot, Dispatcher

from db.database import db
from handlers import docker, files, user
from middlewares.access import AccessMiddleware
from middlewares.throttle import ThrottleMiddleware
from utils.variables import CONFIG_PATH, DOWNLOAD_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_config() -> dict:
    """Load configuration from config.yaml or environment variables."""
    config: dict[str, dict[str, Any]] = {"bot": {}, "storage": {}}

    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(
            f"Config file not found: {CONFIG_PATH}, using environment variables"
        )
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse config file: {e}, using environment variables")

    bot_token = config.get("bot", {}).get("token") or os.getenv("BOT_TOKEN")
    use_local_api = config.get("bot", {}).get("use_local_api", False)
    local_api_url = config.get("bot", {}).get("local_api_url", "http://127.0.0.1:8081")
    admin_ids = config.get("bot", {}).get("admin_ids", [])

    if os.getenv("USE_LOCAL_API", "false").lower() == "true":
        use_local_api = True

    if os.getenv("LOCAL_API_URL"):
        local_api_url = os.getenv("LOCAL_API_URL")

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
        },
        "storage": config.get("storage", {}),
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
    await user.set_commands(bot)
    dp.message.outer_middleware(ThrottleMiddleware())
    dp.message.outer_middleware(AccessMiddleware(db))

    dp.message.register(user.cmd_start, commands=["start"])
    dp.message.register(user.cmd_set_prefix, commands=["set_prefix"])

    from handlers.admin import create_admin_handlers

    cmd_add_user, cmd_remove_user, cmd_list_users = create_admin_handlers(admin_ids)
    dp.message.register(cmd_add_user, commands=["add_user"])
    dp.message.register(cmd_remove_user, commands=["remove_user"])
    dp.message.register(cmd_list_users, commands=["list_users"])

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

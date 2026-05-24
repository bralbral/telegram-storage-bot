from __future__ import annotations

import asyncio

import yaml
from aiogram import Bot, Dispatcher

from db.database import db
from handlers import docker, files, user
from middlewares.access import AccessMiddleware
from middlewares.throttle import ThrottleMiddleware
from utils.variables import CONFIG_PATH, DOWNLOAD_DIR


async def setup_bot() -> tuple[Bot, Dispatcher]:
    """Create and configure bot and dispatcher."""
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    bot_token = config["bot"]["token"]
    admin_ids = config["bot"].get("admin_ids", [])

    if config["bot"].get("use_local_api", False):
        bot = Bot(
            token=bot_token,
            api_server_url=config["bot"].get("local_api_url", "http://127.0.0.1:8081"),
        )
    else:
        bot = Bot(token=bot_token)

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

    return bot, dp


async def run_bot() -> None:
    """Run the bot."""
    bot, dp = await setup_bot()
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run_bot())
import logging
from configs import Config
from handlers.database import db
from pyrogram import Client
from pyrogram.types import Message

logger = logging.getLogger(__name__)

async def add_user_to_database(bot: Client, cmd: Message):
    try:
        user_id = cmd.from_user.id
        if not await db.is_user_exist(user_id):
            await db.add_user(user_id)
            if Config.LOG_CHANNEL:
                try:
                    first_name = (cmd.from_user.first_name or "User").replace("[", "").replace("]", "")
                    await bot.send_message(
                        int(Config.LOG_CHANNEL),
                        f"#NEW_USER:\n\nNew User <b>{first_name}</b> (ID: <code>{user_id}</code>) started @{Config.BOT_USERNAME} !!"
                    )
                except Exception as log_err:
                    logger.debug(f"Could not log new user: {log_err}")
    except Exception as e:
        logger.error(f"Error in add_user_to_database: {e}")

import datetime
import logging
from configs import Config
from handlers.database import db

logger = logging.getLogger(__name__)

async def handle_user_status(bot, cmd):
    try:
        chat_id = cmd.from_user.id
        try:
            if not await db.is_user_exist(chat_id):
                await db.add_user(chat_id)
                if Config.LOG_CHANNEL:
                    try:
                        await bot.send_message(
                            Config.LOG_CHANNEL,
                            f"#NEW_USER:\n\nNew User [{cmd.from_user.first_name}](tg://user?id={cmd.from_user.id}) started @{Config.BOT_USERNAME} !!"
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"User check note: {e}")

        try:
            ban_status = await db.get_ban_status(chat_id)
            if ban_status and ban_status.get("is_banned"):
                await cmd.reply_text("🚫 **Aapko is bot se ban kiya gaya hai.**", quote=True)
                return
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error in handle_user_status: {e}")
    finally:
        # Crucial: Always continue propagation so /start is NEVER blocked!
        await cmd.continue_propagation()

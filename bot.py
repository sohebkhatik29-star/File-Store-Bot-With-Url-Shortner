# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: bot.py
# Purpose: Clean Master Entry Point. Registers all modular handlers.
# ==============================================================================

import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from configs import Config
from handlers.database import db
from handlers.check_user_status import handle_user_status
from handlers.session_manager import session_mgr
from handlers.save_media import handle_incoming_movie_file, handle_generate_links_action
from handlers.start_handler import register_start_handlers
from handlers.admin_commands import register_admin_handlers
from handlers.session_callbacks import register_callback_handlers

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("AshMovieBot")

Bot = Client(
    name=Config.BOT_USERNAME or "AshMovieBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    in_memory=True
)

# 1. Global User Status & Ban Check Middleware
@Bot.on_message(filters.private, group=-1)
async def check_user(bot: Client, cmd: Message):
    """Enforces banned user checks and logs new users."""
    try:
        if cmd.from_user and cmd.from_user.id in Config.BANNED_USERS:
            await cmd.reply_text("🚫 **Aapko is bot se ban kiya gaya hai.**", quote=True)
            return
        await handle_user_status(bot, cmd)
    except Exception as e:
        logger.error(f"check_user error: {e}")
        await cmd.continue_propagation()

# 2. Movie Upload Session Commands: /addmovie, /finish, /cancel
@Bot.on_message(filters.command(["addmovie", "newmovie"]) & filters.private)
async def addmovie_command(bot: Client, cmd: Message):
    """Starts an explicit movie upload session."""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return

    await session_mgr.cancel_session(admin_id)
    text = (
        "🎬 <b>Movie Upload Session Started</b>\n\n"
        "Send the first video file now. After that, you can add more qualities of the same movie or generate the final movie link."
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Session", callback_data="session_cancel")]
    ])
    status_msg = await cmd.reply_text(text, reply_markup=markup, quote=True)
    await session_mgr.start_addmovie_session(admin_id, status_msg.id, cmd.chat.id)

@Bot.on_message(filters.command("cancel") & filters.private)
async def cancel_session_handler(bot: Client, cmd: Message):
    """Admin command to cancel active movie session."""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return
    session = await session_mgr.cancel_session(admin_id)
    title = session.get("title") if session else "Active"
    await cmd.reply_text(f"❌ Movie session <b>'{title}'</b> cancel kar diya gaya hai.", quote=True)

@Bot.on_message(filters.command(["finish", "generatelink"]) & filters.private)
async def finish_session_command(bot: Client, cmd: Message):
    """Admin command to finish session and generate links."""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return
    await handle_generate_links_action(bot, cmd.chat.id, admin_id)

# 3. Media Upload Listener
@Bot.on_message((filters.video | filters.document) & filters.private)
async def auto_movie_upload_listener(bot: Client, message: Message):
    """Handles incoming movie video/document file uploads within active session."""
    await handle_incoming_movie_file(bot, message)

# 4. Register Modular Handlers
register_start_handlers(Bot)
register_admin_handlers(Bot)
register_callback_handlers(Bot)

# 5. Application Lifecycle & Startup Notification
async def main():
    logger.info("Initializing Ash Movie Store Bot...")
    await Bot.start()
    try:
        await db.init_indexes()
        await session_mgr.restore_from_db()
        logger.info("MongoDB indexes and active sessions restored successfully!")
    except Exception as e:
        logger.error(f"Startup warning: {e}")

    # Send restart message to LOG_CHANNEL so user immediately sees bot is live!
    if Config.LOG_CHANNEL:
        try:
            bot_info = await Bot.get_me()
            await Bot.send_message(
                chat_id=Config.LOG_CHANNEL,
                text=f"🎬 <b>@{bot_info.username or Config.BOT_USERNAME} is RESTARTED ✅</b>\n\n"
                     f"⚡ <b>Status:</b> Live & Operational\n"
                     f"🍿 <b>Branding:</b> {Config.BRAND_NAME}\n"
                     f"👑 <b>Owner:</b> @{Config.OWNER_USERNAME}"
            )
            logger.info("Restart notification sent to LOG_CHANNEL!")
        except Exception as err:
            logger.warning(f"Could not send restart log to LOG_CHANNEL: {err}")

    logger.info("🎬 ASH MOVIES Bot is running!")
    await idle()
    await Bot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

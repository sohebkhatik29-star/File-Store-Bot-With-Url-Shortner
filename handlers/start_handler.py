# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/start_handler.py
# Purpose: Dedicated handler for /start, deep links, welcome menus, and informational cards.
# ==============================================================================

import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import QueryIdInvalid

from configs import Config
from handlers.add_user_to_db import add_user_to_database
from handlers.force_sub_handler import handle_force_sub
from handlers.helpers import b64_to_str
from handlers.send_file import send_movie_card, send_media_and_reply

logger = logging.getLogger(__name__)

def register_start_handlers(bot: Client):

    @bot.on_message(filters.command("start") & filters.private)
    async def start_cmd(client: Client, cmd: Message):
        user_id = cmd.from_user.id
        if user_id in Config.BANNED_USERS:
            return

        # Check Force Subscription Channel (Admin/Owner is always exempt)
        if Config.UPDATES_CHANNEL and user_id not in Config.ADMINS:
            status = await handle_force_sub(client, cmd)
            if status == 400:
                return

        text = cmd.text.strip()
        parts = text.split(" ", 1)

        # 1. Standard Start Command (No Arguments)
        if len(parts) == 1 or parts[1] == "/start":
            await add_user_to_database(client, cmd)
            safe_name = (cmd.from_user.first_name or "Movie Lover").replace("[", "").replace("]", "")
            welcome_text = Config.HOME_TEXT.format(
                brand=Config.BRAND_NAME,
                first_name=safe_name,
                user_id=user_id
            )
            channel_url = f"https://t.me/{Config.UPDATES_CHANNEL}" if Config.UPDATES_CHANNEL and not str(Config.UPDATES_CHANNEL).startswith("-") else f"https://t.me/{Config.BOT_USERNAME}"
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📢 Updates Channel", url=channel_url),
                    InlineKeyboardButton("🍿 Dev Info", callback_data="about_dev")
                ],
                [
                    InlineKeyboardButton("ℹ️ About Bot", callback_data="about_bot"),
                    InlineKeyboardButton("❌ Close", callback_data="close_card")
                ]
            ])
            await cmd.reply_text(welcome_text, reply_markup=markup, quote=True, disable_web_page_preview=True)
            return

        # 2. Deep Link Payload Processing
        payload = parts[1].strip()

        # Case A: Movie Deep Link format "mov_<movie_id>"
        if payload.startswith("mov_"):
            movie_id = payload.split("mov_", 1)[-1]
            is_admin = user_id in Config.ADMINS
            await send_movie_card(client, user_id=user_id, movie_id=movie_id, is_admin=is_admin)
            return

        # Case B: Legacy base64 single/batch file link
        try:
            try:
                file_id_str = b64_to_str(payload)
            except Exception:
                file_id_str = payload

            if file_id_str.startswith("batch_"):
                parts_ids = file_id_str.split("_")
                first_id = int(parts_ids[1])
                last_id = int(parts_ids[2])
                for msg_id in range(first_id, last_id + 1):
                    await send_media_and_reply(client, user_id, msg_id)
            else:
                file_id = int(file_id_str.split("_")[-1])
                await send_media_and_reply(client, user_id, file_id)
        except Exception as e:
            logger.error(f"Failed to handle deep link payload: {e}")
            await cmd.reply_text("❌ **Invalid ya Expired Link!** Kripya sahi link use karein.", quote=True)

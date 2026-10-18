# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/session_callbacks.py
# Purpose: Dedicated callback query router for session controls, quality download buttons,
#          duplicate handling, and navigation.
# ==============================================================================

import logging
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import QueryIdInvalid

from configs import Config
from handlers.database import db
from handlers.session_manager import session_mgr
from handlers.save_media import handle_generate_links_action
from handlers.send_file import deliver_movie_quality, send_movie_card

logger = logging.getLogger(__name__)

def register_callback_handlers(bot: Client):

    @bot.on_callback_query()
    async def callback_router(client: Client, query: CallbackQuery):
        data = query.data
        user_id = query.from_user.id

        # 1. Quality Download: dl_{movie_id}_{quality}
        if data.startswith("dl_"):
            parts = data.split("_", 2)
            if len(parts) >= 3:
                movie_id = parts[1]
                quality = parts[2]
                await deliver_movie_quality(client, query, movie_id, quality)
                return

        # 2. Preview Movie Card: preview_mov_{movie_id}
        elif data.startswith("preview_mov_"):
            movie_id = data.split("preview_mov_", 1)[-1]
            is_admin = user_id in Config.ADMINS
            await send_movie_card(client, user_id=user_id, movie_id=movie_id, is_admin=is_admin)
            await query.answer()
            return

        # 3. Session Continue Upload Button
        elif data == "session_continue":
            if user_id not in Config.ADMINS:
                return
            session = await session_mgr.get_session(user_id)
            if not session or not session.get("title"):
                await query.answer("Send the first video file now!", show_alert=True)
                return
            session_mgr.set_awaiting_next(user_id, True)
            title = session.get("title")
            year_str = f" ({session.get('year')})" if session.get("year") else ""
            qualities_str = ", ".join(session.get("qualities", [])) or "None"
            text = (
                f"🎬 <b>Movie: {title}{year_str}</b>\n\n"
                f"➕ <b>Send the next quality file now</b> (e.g. 720p, 1080p, 4K).\n\n"
                f"📁 Already saved: <code>[{qualities_str}]</code>"
            )
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Generate Links", callback_data="session_generate")],
                [InlineKeyboardButton("❌ Cancel Session", callback_data="session_cancel")]
            ])
            try:
                await query.message.edit(text, reply_markup=markup)
            except Exception:
                pass
            await query.answer("Send next quality file!")
            return

        # 4. Session Generate Links Button
        elif data == "session_generate":
            if user_id not in Config.ADMINS:
                return
            await handle_generate_links_action(client, query.message.chat.id, user_id, query)
            return

        # 5. Session Cancel Button
        elif data == "session_cancel":
            if user_id not in Config.ADMINS:
                return
            await session_mgr.cancel_session(user_id)
            try:
                await query.message.edit("❌ <b>Movie upload session cancelled.</b> (No new files will be added)")
            except Exception:
                pass
            await query.answer("Session cancelled!")
            return

        # 6. Duplicate Quality Handling
        elif data.startswith("dup_replace_"):
            if user_id not in Config.ADMINS:
                return
            parts = data.split("_")
            movie_id = parts[2]
            quality = parts[3]
            pending = session_mgr.get_pending_mismatch(user_id)
            if pending:
                quality_data = {
                    "file_id": pending["media_file_id"],
                    "channel_msg_id": pending["message_id"],
                    "file_name": pending["filename"],
                    "file_size": pending["filesize"],
                    "file_size_formatted": pending["filesize_str"],
                }
                await db.add_quality_to_movie(movie_id, quality, quality_data)
                session_mgr.clear_pending_mismatch(user_id)
                movie = await db.get_movie(movie_id)
                saved_q_list = list(movie.get("qualities", {}).keys())
                text = (
                    f"🔄 <b>Quality '{quality}' replaced successfully!</b>\n\n"
                    f"🎬 Movie: <b>{movie.get('title')}</b>\n"
                    f"📁 Saved Qualities: <code>[{', '.join(saved_q_list)}]</code>"
                )
                markup = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("➕ Continue Upload", callback_data="session_continue"),
                        InlineKeyboardButton("🔗 Generate Links", callback_data="session_generate")
                    ],
                    [InlineKeyboardButton("❌ Cancel Session", callback_data="session_cancel")]
                ])
                await query.message.edit(text, reply_markup=markup)
                await query.answer("Quality replaced!")
            return

        elif data == "dup_cancel":
            session_mgr.clear_pending_mismatch(user_id)
            try:
                await query.message.edit("❌ <b>Duplicate upload cancelled.</b> Existing file preserved.")
            except Exception:
                pass
            await query.answer("Cancelled duplicate!")
            return

        # 7. Navigation & Info
        elif data == "about_bot":
            await query.message.edit(
                Config.ABOUT_BOT_TEXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]
                ])
            )
            await query.answer()

        elif data == "about_dev":
            await query.message.edit(
                Config.ABOUT_DEV_TEXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]
                ])
            )
            await query.answer()

        elif data == "back_home":
            safe_name = (query.from_user.first_name or "Movie Lover").replace("[", "").replace("]", "")
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
            await query.message.edit(welcome_text, reply_markup=markup, disable_web_page_preview=True)
            await query.answer()

        elif data == "close_card":
            await query.message.delete()

        try:
            await query.answer()
        except QueryIdInvalid:
            pass

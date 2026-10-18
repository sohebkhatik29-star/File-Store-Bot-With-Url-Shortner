# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: bot.py
# Purpose: Main Telegram Bot Controller with /addmovie Session System,
#          Clean Single-Message Updates, and Netflix-Inspired Card Delivery.
# ==============================================================================

import os
import asyncio
import logging
from pyrogram import Client, filters, enums, idle
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from pyrogram.errors import FloodWait, QueryIdInvalid, UserNotParticipant

from configs import Config
from handlers.database import db
from handlers.add_user_to_db import add_user_to_database
from handlers.check_user_status import handle_user_status
from handlers.force_sub_handler import handle_force_sub
from handlers.broadcast_handlers import main_broadcast_handler
from handlers.helpers import b64_to_str
from handlers.session_manager import session_mgr
from handlers.save_media import handle_incoming_movie_file, handle_generate_links_action, forward_to_db_channel
from handlers.send_file import send_movie_card, deliver_movie_quality, send_media_and_reply
from handlers.movie_card import build_final_movie_card_text, build_final_movie_card_buttons, generate_movie_links
from handlers.parser import normalize_title, format_size

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

# ==================== MIDDLEWARE & USER STATUS ====================

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

# ==================== /start COMMAND & DEEP LINKS ====================

@Bot.on_message(filters.command("start") & filters.private)
async def start_handler(bot: Client, cmd: Message):
    user_id = cmd.from_user.id
    if user_id in Config.BANNED_USERS:
        return

    # Check Force Subscription Channel (Admin/Owner is always exempt)
    if Config.UPDATES_CHANNEL and user_id not in Config.ADMINS:
        status = await handle_force_sub(bot, cmd)
        if status == 400:
            return

    text = cmd.text.strip()
    parts = text.split(" ", 1)

    # 1. Standard Start Command (No Arguments)
    if len(parts) == 1 or parts[1] == "/start":
        await add_user_to_database(bot, cmd)
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
        await send_movie_card(bot, user_id=user_id, movie_id=movie_id, is_admin=is_admin)
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
                await send_media_and_reply(bot, user_id, msg_id)
        else:
            file_id = int(file_id_str.split("_")[-1])
            await send_media_and_reply(bot, user_id, file_id)
    except Exception as e:
        logger.error(f"Failed to handle deep link payload: {e}")
        await cmd.reply_text("❌ **Invalid ya Expired Link!** Kripya sahi link use karein.", quote=True)

# ==================== /addmovie COMMAND & SESSION WORKFLOW ====================

@Bot.on_message(filters.command(["addmovie", "newmovie"]) & filters.private)
async def addmovie_command(bot: Client, cmd: Message):
    """
    Starts an explicit movie upload session.
    Clean single-message UI flow.
    """
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return

    # Cancel previous session if any
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
    if session:
        title = session.get("title") or "Active"
        await cmd.reply_text(f"❌ Movie session <b>'{title}'</b> cancel kar diya gaya hai.", quote=True)
    else:
        await cmd.reply_text("Koi active movie session nahi tha.", quote=True)

@Bot.on_message(filters.command(["finish", "generatelink"]) & filters.private)
async def finish_session_command(bot: Client, cmd: Message):
    """Admin command to finish session and generate links."""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return
    await handle_generate_links_action(bot, cmd.chat.id, admin_id)

@Bot.on_message(filters.command("status") & filters.private)
async def status_handler(bot: Client, cmd: Message):
    """View active session state and saved qualities."""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return

    session = await session_mgr.get_session(admin_id)
    if not session or not session.get("title"):
        await cmd.reply_text(
            "ℹ️ <b>Koi Active Movie Session Nahi Hai.</b>\n\n"
            "Nayi movie start karne ke liye <b>/addmovie</b> bhejein.",
            quote=True
        )
        return

    movie = await db.get_movie(session.get("movie_id"))
    qualities = movie.get("qualities", {}) if movie else {}
    q_list = [f"• <b>{q_name}:</b> {q_val.get('file_size_formatted', 'N/A')}" for q_name, q_val in qualities.items()]
    q_str = "\n".join(q_list) if q_list else "None yet"

    await cmd.reply_text(
        f"📊 <b>CURRENT ACTIVE MOVIE STATUS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🍿 <b>Movie:</b> <code>{session.get('title')} ({session.get('year', '')})</code>\n"
        f"🆔 <b>Movie ID:</b> <code>{session.get('movie_id')}</code>\n\n"
        f"📁 <b>Saved Qualities:</b>\n{q_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Finish karne ke liye <b>/finish</b> ya cancel ke liye <b>/cancel</b> dabayein.",
        quote=True
    )

@Bot.on_message(filters.command("movies") & filters.private)
async def list_movies_handler(bot: Client, cmd: Message):
    """List recent movies with quick links."""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return

    movies = await db.list_movies(limit=10, skip=0)
    total = await db.total_movies_count()

    if not movies:
        await cmd.reply_text("Movie database abhi khali hai.", quote=True)
        return

    text = f"📚 <b>Movie Library ({len(movies)}/{total} Movies):</b>\n\n"
    buttons = []
    for m in movies:
        m_id = m.get("movie_id")
        m_title = m.get("title")
        m_qualities = list(m.get("qualities", {}).keys())
        text += f"• <b>{m_title}</b> [{', '.join(m_qualities)}]\n  ID: <code>{m_id}</code>\n\n"
        buttons.append([InlineKeyboardButton(f"🎬 {m_title}", callback_data=f"preview_mov_{m_id}")])

    await cmd.reply_text(text, quote=True, reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_message(filters.command("delete") & filters.private)
async def delete_movie_cmd(bot: Client, cmd: Message):
    """Delete a movie by movie_id: /delete <movie_id>"""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return

    parts = cmd.text.split(" ", 1)
    if len(parts) < 2:
        await cmd.reply_text("Usage: <code>/delete &lt;movie_id&gt;</code>", quote=True)
        return

    target_id = parts[1].strip()
    ok = await db.delete_movie(target_id)
    if ok:
        await cmd.reply_text(f"✅ Movie <code>{target_id}</code> database se delete ho gayi.", quote=True)
    else:
        await cmd.reply_text(f"❌ Movie ID <code>{target_id}</code> nahi mili.", quote=True)

@Bot.on_message(filters.command("stats") & filters.private)
async def stats_cmd(bot: Client, cmd: Message):
    """View bot metrics."""
    admin_id = cmd.from_user.id
    if admin_id not in Config.ADMINS:
        return

    total_users = await db.total_users_count()
    total_movies = await db.total_movies_count()
    active_sessions = len(session_mgr.active_sessions)

    await cmd.reply_text(
        f"📊 <b>{Config.BRAND_NAME} System Statistics:</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{total_users}</code>\n"
        f"🎬 <b>Total Movies:</b> <code>{total_movies}</code>\n"
        f"⚡ <b>Active Sessions:</b> <code>{active_sessions}</code>\n"
        f"🤖 <b>Bot Status:</b> <code>Online & Operational</code>",
        quote=True
    )

@Bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(bot: Client, cmd: Message):
    """Broadcast functionality."""
    if cmd.from_user.id not in Config.ADMINS:
        return
    await main_broadcast_handler(bot, cmd)

# ==================== PHOTO / MANUAL POSTER UPLOAD ====================

@Bot.on_message(filters.photo & filters.private)
async def handle_photo_upload(bot: Client, message: Message):
    admin_id = message.from_user.id
    if admin_id not in Config.ADMINS:
        return

    session = await session_mgr.get_session(admin_id)
    photo_id = message.photo.file_id

    if session and session.get("movie_id"):
        movie_id = session.get("movie_id")
        await db.update_movie_poster(movie_id, photo_id, source="manual")
        session["poster_file_id"] = photo_id
        await db.set_active_session(admin_id, session)
        await message.reply_text(
            f"🖼 <b>Poster Updated!</b>\n\n"
            f"Yeh poster active movie <b>'{session.get('title')}'</b> ke liye set kar diya gaya hai.",
            quote=True
        )
    else:
        await message.reply_text(
            "🖼 Photo received. Poster set karne ke liye pehle <b>/addmovie</b> se session shuru karein.",
            quote=True
        )

# ==================== FILE UPLOAD LISTENER ====================

@Bot.on_message((filters.video | filters.document) & filters.private)
async def auto_movie_upload_listener(bot: Client, message: Message):
    """Handles incoming movie video/document file uploads within active session."""
    await handle_incoming_movie_file(bot, message)

# ==================== CALLBACK QUERY ROUTER ====================

@Bot.on_callback_query()
async def callback_router(bot: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    # 1. Quality Download: dl_{movie_id}_{quality}
    if data.startswith("dl_"):
        parts = data.split("_", 2)
        if len(parts) >= 3:
            movie_id = parts[1]
            quality = parts[2]
            await deliver_movie_quality(bot, query, movie_id, quality)
            return

    # 2. Preview Movie Card: preview_mov_{movie_id}
    elif data.startswith("preview_mov_"):
        movie_id = data.split("preview_mov_", 1)[-1]
        is_admin = user_id in Config.ADMINS
        await send_movie_card(bot, user_id=user_id, movie_id=movie_id, is_admin=is_admin)
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
        await handle_generate_links_action(bot, query.message.chat.id, user_id, query)
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
            # Replace quality in database
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

# ==================== STARTUP & LIFECYCLE ====================

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
                text=f"🎬 <b>@{bot_info.username or Config.BOT_USERNAME} is RESTARTED ✅</b>\n\n⚡ <b>Status:</b> Live & Operational\n🍿 <b>Branding:</b> {Config.BRAND_NAME}\n👑 <b>Owner:</b> @{Config.OWNER_USERNAME}"
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

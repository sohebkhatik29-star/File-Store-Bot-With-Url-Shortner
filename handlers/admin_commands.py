# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/admin_commands.py
# Purpose: Dedicated Admin Management Commands: /movies, /delete, /stats,
#          /status, and manual poster photo updates.
# ==============================================================================

import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from configs import Config
from handlers.database import db
from handlers.session_manager import session_mgr
from handlers.broadcast_handlers import main_broadcast_handler

logger = logging.getLogger(__name__)

def register_admin_handlers(bot: Client):

    @bot.on_message(filters.command("status") & filters.private)
    async def status_handler(client: Client, cmd: Message):
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

    @bot.on_message(filters.command("movies") & filters.private)
    async def list_movies_handler(client: Client, cmd: Message):
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

    @bot.on_message(filters.command("delete") & filters.private)
    async def delete_movie_cmd(client: Client, cmd: Message):
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

    @bot.on_message(filters.command("stats") & filters.private)
    async def stats_cmd(client: Client, cmd: Message):
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

    @bot.on_message(filters.command("broadcast") & filters.private)
    async def broadcast_cmd(client: Client, cmd: Message):
        """Broadcast functionality."""
        if cmd.from_user.id not in Config.ADMINS:
            return
        await main_broadcast_handler(client, cmd)

    @bot.on_message(filters.photo & filters.private)
    async def handle_photo_upload(client: Client, message: Message):
        """Manual poster attach/change."""
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

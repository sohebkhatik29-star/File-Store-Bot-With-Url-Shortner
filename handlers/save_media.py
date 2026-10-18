# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/save_media.py
# Purpose: Handles incoming media strictly within the /addmovie session,
#          maintains a single edited status message, prevents KGF in Jaat,
#          and eliminates chat clutter.
# ==============================================================================

import asyncio
import logging
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait

from configs import Config
from handlers.database import db
from handlers.parser import extract_movie_metadata, format_size
from handlers.poster import extract_poster_from_message
from handlers.session_manager import session_mgr
from handlers.movie_card import build_final_movie_card_text, build_final_movie_card_buttons, generate_movie_links

logger = logging.getLogger(__name__)

async def forward_to_db_channel(bot: Client, message: Message) -> Message:
    try:
        sent = await message.copy(Config.DB_CHANNEL)
        return sent
    except FloodWait as sl:
        logger.warning(f"FloodWait of {sl.value}s while saving to DB channel")
        await asyncio.sleep(sl.value)
        return await forward_to_db_channel(bot, message)
    except Exception as e:
        logger.error(f"Failed to forward media to DB channel: {e}")
        raise e

async def handle_incoming_movie_file(bot: Client, message: Message):
    admin_id = message.from_user.id
    if admin_id not in Config.ADMINS:
        return

    media = message.video or message.document
    if not media:
        return

    # Check if there is an active /addmovie session
    session = await session_mgr.get_session(admin_id)
    if not session:
        await message.reply_text(
            "ℹ️ **Koi Movie Upload Session Active Nahi Hai.**\n\n"
            "Nayi movie add karne ke liye pehle **/addmovie** command bhejein!",
            quote=True
        )
        return

    # Use per-admin lock to process forwarded files sequentially without race conditions
    async with session_mgr.get_lock(admin_id):
        session = await session_mgr.get_session(admin_id)
        if not session:
            return

        filename = getattr(media, "file_name", "") or "Movie_Video"
        caption = message.caption or ""
        filesize = getattr(media, "file_size", 0)
        filesize_str = format_size(filesize)

        meta = extract_movie_metadata(filename, caption)
        incoming_title = meta["title"]
        incoming_quality = meta["quality"]
        incoming_year = meta["year"]
        incoming_langs = meta["languages"]

        # ==================== CASE 1: FIRST FILE IN SESSION ====================
        if session.get("status") == "AWAITING_FIRST_FILE" or not session.get("title"):
            movie_id = db.generate_movie_id()
            extracted_poster, poster_source = await extract_poster_from_message(bot, message)

            movie = await db.create_movie(
                title=incoming_title,
                normalized_title=meta["normalized_title"],
                year=incoming_year,
                languages=incoming_langs,
                poster_file_id=extracted_poster,
                admin_id=admin_id,
                movie_id=movie_id
            )

            channel_msg = await forward_to_db_channel(bot, message)
            quality_data = {
                "file_id": media.file_id,
                "channel_msg_id": channel_msg.id,
                "file_name": filename,
                "file_size": filesize,
                "file_size_formatted": filesize_str,
            }
            await db.add_quality_to_movie(movie_id, incoming_quality, quality_data)
            await session_mgr.register_first_movie_file(
                admin_id=admin_id,
                movie_id=movie_id,
                title=incoming_title,
                year=incoming_year,
                languages=incoming_langs,
                quality=incoming_quality,
                poster_file_id=extracted_poster
            )

            year_str = f" ({incoming_year})" if incoming_year else ""
            status_text = (
                f"🎬 **Movie Upload Session: {incoming_title}{year_str}**\n\n"
                f"✅ **Saved Quality:** `{incoming_quality}` ({filesize_str})\n"
                f"📁 **Saved Qualities:** `[{incoming_quality}]`\n"
                f"🌐 **Language:** `{', '.join(incoming_langs)}`\n\n"
                f"Aap agli quality add kar sakte hain ya final link generate kar sakte hain:"
            )
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➕ Continue Upload", callback_data="session_continue"),
                    InlineKeyboardButton("🔗 Generate Links", callback_data="session_generate")
                ],
                [
                    InlineKeyboardButton("❌ Cancel Session", callback_data="session_cancel")
                ]
            ])

            # Update the single status message instead of flooding the chat!
            status_msg_id = session.get("status_msg_id")
            status_chat_id = session.get("status_chat_id", message.chat.id)
            updated = False
            if status_msg_id:
                try:
                    await bot.edit_message_text(
                        chat_id=status_chat_id,
                        message_id=status_msg_id,
                        text=status_text,
                        reply_markup=markup
                    )
                    updated = True
                except Exception:
                    pass

            if not updated:
                new_msg = await message.reply_text(status_text, reply_markup=markup, quote=True)
                session["status_msg_id"] = new_msg.id
                await db.set_active_session(admin_id, session)

            return

        # ==================== CASE 2: ADDITIONAL FILE FOR ACTIVE MOVIE ====================
        active_title = session.get("title", "")
        active_year = session.get("year")
        active_year_str = f" ({active_year})" if active_year else ""
        movie_id = session.get("movie_id")
        movie = await db.get_movie(movie_id)

        # 1. STRICT MOVIE NAME PROTECTION (e.g. KGF sent when Jaat is active)
        is_match, reason, _ = await session_mgr.validate_incoming_upload(admin_id, incoming_title)
        if not is_match:
            warning_text = (
                f"⚠️ **Different Movie Detected!**\n\n"
                f"📌 **Current movie:** `{active_title}{active_year_str}`\n"
                f"🚫 **Received file appears to be:** `{incoming_title}`\n\n"
                f"❌ **This file was NOT added.** Finish or cancel the current session before starting another movie."
            )
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➕ Continue Upload", callback_data="session_continue"),
                    InlineKeyboardButton("🔗 Generate Links", callback_data="session_generate")
                ],
                [
                    InlineKeyboardButton("❌ Cancel Session", callback_data="session_cancel")
                ]
            ])
            await message.reply_text(warning_text, reply_markup=markup, quote=True)
            return

        # 2. DUPLICATE QUALITY CHECK
        existing_qualities = movie.get("qualities", {}) if movie else {}
        if incoming_quality in existing_qualities:
            existing_size = existing_qualities[incoming_quality].get("file_size_formatted", "Unknown")
            session_mgr.store_pending_mismatch(admin_id, {
                "message_id": message.id,
                "media_file_id": media.file_id,
                "filename": filename,
                "filesize": filesize,
                "filesize_str": filesize_str,
                "quality": incoming_quality,
                "movie_id": movie_id
            })
            dup_text = (
                f"⚠️ **Duplicate Quality Detected!**\n\n"
                f"Movie **'{active_title}'** ke paas pehle se **{incoming_quality}** available hai.\n\n"
                f"• **Existing Size:** `{existing_size}`\n"
                f"• **Incoming Size:** `{filesize_str}`\n\n"
                f"Kya aap purani file ko replace karna chahte hain?"
            )
            dup_markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Yes, Replace Quality", callback_data=f"dup_replace_{movie_id}_{incoming_quality}_{message.id}"),
                    InlineKeyboardButton("❌ No, Keep Existing", callback_data="dup_cancel")
                ]
            ])
            await message.reply_text(dup_text, reply_markup=dup_markup, quote=True)
            return

        # 3. SAVE ADDITIONAL QUALITY TO THE SAME MOVIE RECORD!
        channel_msg = await forward_to_db_channel(bot, message)
        quality_data = {
            "file_id": media.file_id,
            "channel_msg_id": channel_msg.id,
            "file_name": filename,
            "file_size": filesize,
            "file_size_formatted": filesize_str,
        }
        await db.add_quality_to_movie(movie_id, incoming_quality, quality_data)
        await session_mgr.register_additional_quality(admin_id, incoming_quality)

        # If poster was missing, try extracting from this video
        if not movie.get("poster_file_id"):
            extracted_poster, poster_source = await extract_poster_from_message(bot, message)
            if extracted_poster:
                await db.update_movie_poster(movie_id, extracted_poster, poster_source)

        updated_movie = await db.get_movie(movie_id)
        saved_q_list = list(updated_movie.get("qualities", {}).keys())

        status_text = (
            f"🎬 **Movie Upload Session: {active_title}{active_year_str}**\n\n"
            f"✅ **Added Quality:** `{incoming_quality}` ({filesize_str})\n"
            f"📁 **Total Saved Qualities:** `[{', '.join(saved_q_list)}]`\n\n"
            f"Aap agli quality add kar sakte hain ya final link generate kar sakte hain:"
        )
        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Continue Upload", callback_data="session_continue"),
                InlineKeyboardButton("🔗 Generate Links", callback_data="session_generate")
            ],
            [
                InlineKeyboardButton("❌ Cancel Session", callback_data="session_cancel")
            ]
        ])

        status_msg_id = session.get("status_msg_id")
        status_chat_id = session.get("status_chat_id", message.chat.id)
        updated = False
        if status_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=status_chat_id,
                    message_id=status_msg_id,
                    text=status_text,
                    reply_markup=markup
                )
                updated = True
            except Exception:
                pass

        if not updated:
            new_msg = await message.reply_text(status_text, reply_markup=markup, quote=True)
            session["status_msg_id"] = new_msg.id
            await db.set_active_session(admin_id, session)

async def handle_generate_links_action(bot: Client, chat_id: int, admin_id: int, query: CallbackQuery = None):
    """Finishes the session and creates ONE clean, professional final movie card."""
    session = await session_mgr.finish_session(admin_id)
    if not session or not session.get("movie_id"):
        msg = "⚠️ Koi active movie session nahi mila jisme files upload hui hon."
        if query:
            await query.answer(msg, show_alert=True)
        else:
            await bot.send_message(chat_id, msg)
        return

    movie_id = session["movie_id"]
    movie = await db.get_movie(movie_id)
    if not movie or not movie.get("qualities"):
        msg = "⚠️ Is session mein koi quality save nahi hui."
        if query:
            await query.answer(msg, show_alert=True)
        return

    short_link, raw_link = generate_movie_links(movie_id)
    card_text = build_final_movie_card_text(movie)
    card_buttons = build_final_movie_card_buttons(movie)
    poster = movie.get("poster_file_id")

    # If poster is missing, extract on-demand from the saved video in DB_CHANNEL!
    if not poster and movie.get("qualities") and Config.DB_CHANNEL:
        try:
            first_q = list(movie["qualities"].values())[0]
            channel_msg_id = first_q.get("channel_msg_id")
            if channel_msg_id:
                db_msg = await bot.get_messages(Config.DB_CHANNEL, channel_msg_id)
                extracted_poster, _ = await extract_poster_from_message(bot, db_msg)
                if extracted_poster:
                    poster = extracted_poster
                    await db.update_movie_poster(movie_id, poster, "on_demand_extract")
        except Exception as e:
            logger.debug(f"On-demand poster extraction: {e}")

    # Send the final movie card
    if poster:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=poster,
                caption=card_text,
                reply_markup=card_buttons
            )
        except Exception:
            await bot.send_message(chat_id=chat_id, text=card_text, reply_markup=card_buttons)
    else:
        await bot.send_message(chat_id=chat_id, text=card_text, reply_markup=card_buttons)

    # Send success message with shareable deep link
    qualities_str = ", ".join(movie.get("qualities", {}).keys())
    success_text = (
        f"✅ **Movie Upload Complete!**\n\n"
        f"🎬 **Movie:** `{movie.get('title')}`\n"
        f"📁 **Saved Qualities:** `[{qualities_str}]`\n"
        f"🆔 **Movie ID:** `{movie_id}`\n\n"
        f"🔗 **Shareable Link:**\n`{short_link}`\n\n"
        f"✨ Final movie card has been generated above!"
    )
    await bot.send_message(chat_id=chat_id, text=success_text)

    if query:
        await query.answer("Movie Card & Links Generated!")

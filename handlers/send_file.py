# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/send_file.py
# Purpose: Movie delivery, quality download execution, 30-min auto-delete timers,
#          and backward compatibility for legacy file links.
# ==============================================================================

import asyncio
import logging
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import FloodWait

from configs import Config
from handlers.database import db
from handlers.movie_card import build_final_movie_card_text, build_final_movie_card_buttons

logger = logging.getLogger(__name__)

async def delete_after_delay(message: Message, delay: int = 1800):
    """Auto-deletes delivered movie file after specified seconds (default 30 min)."""
    try:
        await asyncio.sleep(delay)
        await message.delete()
        logger.info(f"Auto-deleted file message {message.id} after {delay} seconds.")
    except Exception as e:
        logger.debug(f"Auto-delete note: {e}")

async def send_movie_card(bot: Client, user_id: int, movie_id: str, is_admin: bool = False):
    """
    Sends the clean final movie card to a user when they click the deep link.
    """
    movie = await db.get_movie(movie_id)
    if not movie:
        await bot.send_message(
            chat_id=user_id,
            text="❌ **Movie Not Found!**\n\nYeh movie database se remove kar di gayi hai ya link invalid hai."
        )
        return

    card_text = build_final_movie_card_text(movie)
    card_buttons = build_final_movie_card_buttons(movie)

    poster = movie.get("poster_file_id")
    if not poster and movie.get("qualities") and Config.DB_CHANNEL:
        try:
            from handlers.poster import extract_poster_from_message
            first_q = list(movie["qualities"].values())[0]
            channel_msg_id = first_q.get("channel_msg_id")
            if channel_msg_id:
                db_msg = await bot.get_messages(Config.DB_CHANNEL, channel_msg_id)
                extracted_poster, _ = await extract_poster_from_message(bot, db_msg)
                if extracted_poster:
                    poster = extracted_poster
                    await db.update_movie_poster(movie_id, poster, "on_demand_extract")
        except Exception as e:
            logger.debug(f"On-demand poster extraction in send_movie_card: {e}")

    if poster:
        try:
            await bot.send_photo(
                chat_id=user_id,
                photo=poster,
                caption=card_text,
                reply_markup=card_buttons
            )
            return
        except Exception as e:
            logger.warning(f"Failed to send poster photo: {e}")

    await bot.send_message(
        chat_id=user_id,
        text=card_text,
        reply_markup=card_buttons
    )

async def deliver_movie_quality(bot: Client, query: CallbackQuery, movie_id: str, quality: str):
    """
    Sends the requested movie quality file to the user from DB_CHANNEL with auto-delete notice.
    """
    user_id = query.from_user.id
    movie = await db.get_movie(movie_id)

    if not movie:
        await query.answer("Movie record nahi mila!", show_alert=True)
        return

    qualities = movie.get("qualities", {})
    q_data = qualities.get(quality)

    if not q_data:
        await query.answer(f"Quality '{quality}' is movie ke liye uplabdh nahi hai!", show_alert=True)
        return

    channel_msg_id = q_data.get("channel_msg_id")
    if not channel_msg_id:
        await query.answer("File reference missing!", show_alert=True)
        return

    await query.answer("Sending your file... please wait!", show_alert=False)

    try:
        if Config.FORWARD_AS_COPY:
            sent_file = await bot.copy_message(
                chat_id=user_id,
                from_chat_id=Config.DB_CHANNEL,
                message_id=channel_msg_id
            )
        else:
            sent_file = await bot.forward_messages(
                chat_id=user_id,
                from_chat_id=Config.DB_CHANNEL,
                message_ids=channel_msg_id
            )

        notice = await bot.send_message(
            chat_id=user_id,
            text=f"⚠️ **Copyright Protection Alert:**\n\n"
                 f"File will be automatically deleted in **{Config.AUTO_DELETE_TIME // 60} minutes**.\n"
                 f"Kripya ise turant apne 'Saved Messages' mein forward kar lein!",
            reply_to_message_id=sent_file.id
        )

        asyncio.create_task(delete_after_delay(sent_file, Config.AUTO_DELETE_TIME))
        asyncio.create_task(delete_after_delay(notice, Config.AUTO_DELETE_TIME))

    except FloodWait as sl:
        await asyncio.sleep(sl.value)
        await deliver_movie_quality(bot, query, movie_id, quality)
    except Exception as e:
        logger.error(f"Error sending movie quality: {e}")
        await bot.send_message(chat_id=user_id, text=f"File bhejne mein error aaya: {e}")

# ==================== LEGACY FILE SUPPORT ====================

async def send_media_and_reply(bot: Client, user_id: int, file_id: int):
    """Maintains backward compatibility for old FileStore base64 links."""
    try:
        if Config.FORWARD_AS_COPY:
            sent = await bot.copy_message(chat_id=user_id, from_chat_id=Config.DB_CHANNEL, message_id=file_id)
        else:
            sent = await bot.forward_messages(chat_id=user_id, from_chat_id=Config.DB_CHANNEL, message_ids=file_id)

        notice = await bot.send_message(
            chat_id=user_id,
            text=f"⚠️ File will be auto-deleted in {Config.AUTO_DELETE_TIME // 60} minutes.",
            reply_to_message_id=sent.id
        )
        asyncio.create_task(delete_after_delay(sent, Config.AUTO_DELETE_TIME))
        asyncio.create_task(delete_after_delay(notice, Config.AUTO_DELETE_TIME))
    except Exception as e:
        logger.error(f"Legacy file send error: {e}")

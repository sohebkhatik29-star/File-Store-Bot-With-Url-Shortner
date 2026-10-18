import asyncio
import logging
from typing import Union
from configs import Config
from pyrogram import Client
from pyrogram.errors import FloodWait, UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

logger = logging.getLogger(__name__)

async def get_invite_link(bot: Client, chat_id: Union[str, int]):
    try:
        invite_link = await bot.create_chat_invite_link(chat_id=chat_id)
        return invite_link
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await get_invite_link(bot, chat_id)
    except Exception as e:
        logger.warning(f"Could not generate invite link for {chat_id}: {e}")
        return None

async def handle_force_sub(bot: Client, cmd: Message):
    # 1. Bot Owner and Admins ALWAYS bypass Force-Sub check!
    if cmd.from_user and cmd.from_user.id in Config.ADMINS:
        return 200

    if not Config.UPDATES_CHANNEL:
        return 200

    if str(Config.UPDATES_CHANNEL).startswith("-100"):
        channel_chat_id = int(Config.UPDATES_CHANNEL)
    else:
        channel_chat_id = Config.UPDATES_CHANNEL

    try:
        user = await bot.get_chat_member(chat_id=channel_chat_id, user_id=cmd.from_user.id)
        if user.status == "kicked":
            await bot.send_message(
                chat_id=cmd.from_user.id,
                text="🚫 **Sorry, you are banned from using this bot.**",
                disable_web_page_preview=True
            )
            return 400
        return 200

    except UserNotParticipant:
        try:
            invite_link = await get_invite_link(bot, chat_id=channel_chat_id)
            channel_url = invite_link.invite_link if invite_link else f"https://t.me/{Config.UPDATES_CHANNEL}"
        except Exception:
            channel_url = f"https://t.me/{Config.UPDATES_CHANNEL}"

        await bot.send_message(
            chat_id=cmd.from_user.id,
            text=f"📢 **Please Join Our Updates Channel To Use This Bot!**\n\n"
                 f"Due to heavy load, only channel subscribers can access movies.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Updates Channel", url=channel_url)],
                [InlineKeyboardButton("🔄 Refresh / Try Again", callback_data="refreshForceSub")]
            ])
        )
        return 400

    except Exception as e:
        # If bot is not yet admin in channel or channel is private, do not block users!
        logger.warning(f"[ForceSub Warning] Skipping force-sub check (Bot might not be admin in channel {Config.UPDATES_CHANNEL}): {e}")
        return 200

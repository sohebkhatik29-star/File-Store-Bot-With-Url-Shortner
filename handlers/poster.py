# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/poster.py
# Purpose: Robust, permanent video poster extraction.
#          Downloads the embedded video thumbnail and converts it to a genuine
#          Telegram photo.file_id so Telegram never rejects it with PHOTO_INVALID.
# ==============================================================================

import os
import logging
from typing import Tuple, Optional
from pyrogram import Client
from pyrogram.types import Message
from configs import Config

logger = logging.getLogger(__name__)

async def extract_poster_from_message(bot: Client, message: Message) -> Tuple[Optional[str], str]:
    """
    Extracts poster from incoming video/document by downloading the embedded
    thumbnail and uploading it as a valid Telegram photo into DB_CHANNEL.
    Returns: (photo_file_id_or_none, source_description)
    """
    try:
        # 1. If message is already a photo (e.g. admin sent photo)
        if message.photo:
            return message.photo.file_id, "manual_photo"

        # 2. Extract embedded thumbnail from video or document
        media = message.video or message.document
        if not media:
            return None, "none"

        thumb = None
        if hasattr(media, "thumbs") and media.thumbs:
            thumb = media.thumbs[-1]
        elif hasattr(media, "thumb") and media.thumb:
            thumb = media.thumb

        if not thumb:
            logger.info("No embedded thumbnail found on media.")
            return None, "none"

        # Download small thumbnail (~20-50 KB) locally
        logger.info(f"Downloading embedded thumbnail for {getattr(media, 'file_name', 'media')}...")
        thumb_path = await bot.download_media(thumb)

        if thumb_path and os.path.exists(thumb_path):
            try:
                # Upload to DB_CHANNEL as a REAL Telegram Photo to get a permanent photo.file_id
                target_channel = Config.DB_CHANNEL or message.chat.id
                sent_photo = await bot.send_photo(
                    chat_id=target_channel,
                    photo=thumb_path,
                    caption=f"🖼 Poster extracted for {getattr(media, 'file_name', 'Movie')}"
                )
                if sent_photo and sent_photo.photo:
                    photo_file_id = sent_photo.photo.file_id
                    logger.info(f"Successfully created permanent photo file_id: {photo_file_id[:15]}...")
                    return photo_file_id, "video_thumbnail"
            finally:
                # Always remove local temp file
                if os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                    except Exception:
                        pass

    except Exception as e:
        logger.warning(f"[Poster Extraction Error]: {e}")

    return None, "none"

# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/poster.py
# Purpose: Robust, multi-tier video poster extraction & fallback management.
# ==============================================================================

import os
import logging
from typing import Tuple, Optional
from pyrogram.types import Message

logger = logging.getLogger(__name__)

async def extract_poster_from_message(message: Message) -> Tuple[Optional[str], str]:
    """
    Attempts to extract poster from incoming Telegram message.
    Priority order:
    1. Video attached thumbnail (message.video.thumbs)
    2. Document attached thumbnail (message.document.thumbs)
    3. None (safe fallback, allows admin to add manual poster)
    
    Returns: (file_id_or_none, source_description)
    """
    try:
        # Check Video Thumbnail
        if message.video and message.video.thumbs:
            largest_thumb = message.video.thumbs[-1]
            return largest_thumb.file_id, "video_thumbnail"

        # Check Document Thumbnail (MKV / MP4 sent as document)
        if message.document and message.document.thumbs:
            largest_thumb = message.document.thumbs[-1]
            return largest_thumb.file_id, "document_thumbnail"

        # Check if message is a photo (e.g. admin sends manual poster)
        if message.photo:
            largest_photo = message.photo.file_id
            return largest_photo, "manual_photo"

    except Exception as e:
        logger.warning(f"[Poster Extraction] Safe fallback caught error: {e}")

    return None, "none"

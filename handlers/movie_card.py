# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/movie_card.py
# Purpose: Final Movie Cards, Download Buttons, and Deep Links.
# ==============================================================================

import requests
import string
import random
from typing import Dict, Any, Tuple
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from configs import Config

def shorten_url_if_enabled(original_url: str) -> str:
    if not Config.SHORTLINK_URL or not Config.SHORTLINK_API:
        return original_url
    try:
        alias = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(7))
        api_url = f"https://{Config.SHORTLINK_URL}/api?api={Config.SHORTLINK_API}&url={original_url}&alias={alias}"
        resp = requests.get(api_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success" or data.get("shortenedUrl"):
                return data.get("shortenedUrl", original_url)
    except Exception as e:
        print(f"[Shortener] Fallback to original URL: {e}")
    return original_url

def build_final_movie_card_text(movie: Dict[str, Any]) -> str:
    """
    Builds the clean, professional final movie card text.
    Example:
    🎬 JAAT (2025)
    🌐 Language: Hindi
    🎞 Quality: 480p | 720p | 1080p
    🍿 Available Downloads:
    """
    title = movie.get("title", "Untitled").upper()
    year = movie.get("year")
    year_str = f" ({year})" if year else ""
    languages = movie.get("languages", ["Hindi"])
    lang_str = " • ".join(languages) if languages else "Hindi"

    qualities = movie.get("qualities", {})
    order = {"480p": 1, "540p": 2, "720p": 3, "1080p": 4, "2160p": 5}
    sorted_q_names = sorted(list(qualities.keys()), key=lambda q: order.get(q, 99))
    q_str = " | ".join(sorted_q_names) if sorted_q_names else "Standard"

    text = f"🎬 <b>{title}{year_str}</b>\n\n"
    text += f"🌐 <b>Language:</b> {lang_str}\n"
    text += f"🎞 <b>Quality:</b> {q_str}\n\n"
    text += "🍿 <b>Available Downloads:</b>"
    return text

def build_final_movie_card_buttons(movie: Dict[str, Any]) -> InlineKeyboardMarkup:
    """
    Creates individual download buttons for each saved quality.
    Never shows qualities with no saved file.
    """
    movie_id = movie.get("movie_id", "")
    qualities = movie.get("qualities", {})
    order = {"480p": 1, "540p": 2, "720p": 3, "1080p": 4, "2160p": 5}
    sorted_qualities = sorted(qualities.items(), key=lambda item: order.get(item[0], 99))

    buttons = []
    for q_name, q_data in sorted_qualities:
        size_str = q_data.get("file_size_formatted", "")
        label = f"⬇️ Download {q_name}" + (f" ({size_str})" if size_str else "")
        callback_data = f"dl_{movie_id}_{q_name}"
        buttons.append([InlineKeyboardButton(label, callback_data=callback_data)])

    # Utilities row
    channel_url = f"https://t.me/{Config.UPDATES_CHANNEL}" if Config.UPDATES_CHANNEL and not str(Config.UPDATES_CHANNEL).startswith("-") else f"https://t.me/{Config.BOT_USERNAME}"
    buttons.append([
        InlineKeyboardButton("📢 Updates Channel", url=channel_url),
        InlineKeyboardButton("❌ Close", callback_data="close_card")
    ])

    return InlineKeyboardMarkup(buttons)

def generate_movie_links(movie_id: str) -> Tuple[str, str]:
    """Generates Telegram deep link and shortened version."""
    raw_link = f"https://t.me/{Config.BOT_USERNAME}?start=mov_{movie_id}"
    short_link = shorten_url_if_enabled(raw_link)
    return short_link, raw_link

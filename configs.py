# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: configs.py
# Purpose: Central configuration, environment variable loader, and text templates.
# ==============================================================================

import os

class Config(object):
    # Telegram API Credentials (from https://my.telegram.org)
    API_ID = int(os.environ.get("API_ID", "30720676"))
    API_HASH = os.environ.get("API_HASH", "a078e3476750afbd6db7d6c5e5e658d9")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "8950506278:AAGcdQq7AxDBThbiPL-1RpH80cWjSoBJQUw")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "Ash_best_movie_bot").replace("@", "")

    # Telegram Database & Log Channels
    DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-1003982969802"))
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003763748918"))
    UPDATES_CHANNEL = os.environ.get("UPDATES_CHANNEL", "-1002196570573")  # Force-sub channel ID or username

    # URL Shortener Configuration (Optional)
    SHORTLINK_URL = os.environ.get("SHORTLINK_URL", "")  # e.g. "shareus.io" or "droplink.co"
    SHORTLINK_API = os.environ.get("SHORTLINK_API", "")  # Shortener API key
    ENABLE_SHORTLINK = bool(os.environ.get("ENABLE_SHORTLINK", False))

    # Bot Owner and Admin IDs
    BOT_OWNER = int(os.environ.get("BOT_OWNER", "5566977478"))
    OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "movies_1780").replace("@", "")
    raw_admins = os.environ.get("ADMINS", "5566977478")
    ADMINS = set([BOT_OWNER])
    if raw_admins:
        for x in raw_admins.replace(",", " ").split():
            if x.strip().isdigit():
                ADMINS.add(int(x.strip()))

    # MongoDB Atlas Database Configuration
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "mongodb+srv://sohebkhatik29_db_user:3E3bPvJH8ECFtpBq@cluster0.z6gan8b.mongodb.net/moviefilterbot?retryWrites=true&w=majority&appName=Cluster0"
    )
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "moviefilterbot")

    # Safety, Bans & Security
    BANNED_USERS = set(int(x) for x in os.environ.get("BANNED_USERS", "").split() if x.strip().isdigit())
    BANNED_CHAT_IDS = list(set(int(x) for x in os.environ.get("BANNED_CHAT_IDS", "").split() if x.strip().isdigit()))
    OTHER_USERS_CAN_SAVE_FILE = bool(os.environ.get("OTHER_USERS_CAN_SAVE_FILE", False))  # Only admins by default

    # File Sending Options
    FORWARD_AS_COPY = bool(os.environ.get("FORWARD_AS_COPY", True))
    BROADCAST_AS_COPY = bool(os.environ.get("BROADCAST_AS_COPY", True))
    AUTO_DELETE_TIME = int(os.environ.get("AUTO_DELETE_TIME", 1800))  # 30 minutes in seconds

    # Movie Store & Branding Features
    BRAND_NAME = "ASH MOVIES"
    AUTO_EXTRACT_POSTER = bool(os.environ.get("AUTO_EXTRACT_POSTER", True))
    DEFAULT_POSTER_URL = os.environ.get("DEFAULT_POSTER_URL", "")

    # Text Templates
    HOME_TEXT = """🎬 **Welcome to {brand}** 🎬

Namaste [{first_name}](tg://user?id={user_id})!

Yeh ek **Automatic Movie File Store Bot** hai. Yahan aapko latest movies, multiple verified qualities (480p, 720p, 1080p, 4K) aur direct high-speed download links milenge.

✨ **How to use:**
• Movie link par click karein.
• Apni pasand ki quality select karein.
• File turant download karein.

⚠️ **Note:** Copyright protection ke liye files 30 minutes baad auto-delete ho jayengi, isliye save ya forward kar lein!"""

    ABOUT_BOT_TEXT = f"""╭────[ 🎬 **{BRAND_NAME} BOT** ]────⍟
│
├🔸 **Bot Name:** {BRAND_NAME} Store (@{BOT_USERNAME})
├🔸 **Library:** Pyrogram / Pyrofork (Python 3)
├🔸 **Database:** MongoDB Atlas
├🔸 **Features:** 
│  • Auto Movie Indexing
│  • Active Movie Session Manager
│  • Multiple Quality Grouping
│  • Auto Video Poster Extraction
│  • Netflix-Inspired Cards
│
╰──────[ 🍿 Enjoy Streaming ]───────────⍟"""

    ABOUT_DEV_TEXT = f"""🧑🏻‍💻 **Developer & Owner Info**

⚡ **Bot System:** {BRAND_NAME} Automatic File Store
👑 **Owner:** @{OWNER_USERNAME}
🛡️ **Security:** Session-Protected & Admin Verified
🤖 **Bot Username:** @{BOT_USERNAME}"""

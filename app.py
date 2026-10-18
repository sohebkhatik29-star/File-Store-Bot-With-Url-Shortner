import os
import sys
import subprocess
import threading
from flask import Flask, jsonify

app = Flask(__name__)

bot_process = None

def start_bot_process():
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        try:
            print("[WebServer] Starting Telegram bot process (bot.py)...")
            bot_process = subprocess.Popen([sys.executable, "bot.py"])
            print(f"[WebServer] bot.py launched with PID: {bot_process.pid}")
        except Exception as e:
            print(f"[WebServer] Failed to launch bot.py: {e}")

# Launch bot on web server initialization
threading.Thread(target=start_bot_process, daemon=True).start()

@app.route("/")
def health_check():
    # Auto-revive bot if it stopped
    if bot_process is None or bot_process.poll() is not None:
        start_bot_process()
    return jsonify({
        "status": "online",
        "service": "ASH AUTOMATIC MOVIE FILE STORE BOT",
        "bot": "Ash_best_movie_bot",
        "branding": "ASH MOVIES",
        "version": "2.0.0"
    })

if __name__ == "__main__":
    start_bot_process()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

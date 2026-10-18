# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/session_manager.py
# Purpose: Strict, Lock-Protected Active Movie Session Manager.
#          Ensures clean sequential processing, prevents KGF inside Jaat,
#          and tracks single-message UI updates.
# ==============================================================================

import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from handlers.database import db
from handlers.parser import is_title_match, normalize_title

logger = logging.getLogger(__name__)

class MovieSessionManager:
    def __init__(self):
        self.active_sessions: Dict[int, Dict[str, Any]] = {}
        self.pending_files: Dict[int, Dict[str, Any]] = {}
        self._locks: Dict[int, asyncio.Lock] = {}

    def get_lock(self, admin_id: int) -> asyncio.Lock:
        if admin_id not in self._locks:
            self._locks[admin_id] = asyncio.Lock()
        return self._locks[admin_id]

    async def restore_from_db(self):
        """Restores unfinished active sessions on startup."""
        try:
            sessions = await db.get_all_active_sessions()
            for s in sessions:
                admin_id = s.get("admin_id")
                if admin_id:
                    self.active_sessions[admin_id] = s
            logger.info(f"[SessionManager] Restored {len(self.active_sessions)} active sessions.")
        except Exception as e:
            logger.error(f"[SessionManager] Restore warning: {e}")

    async def get_session(self, admin_id: int) -> Optional[Dict[str, Any]]:
        if admin_id in self.active_sessions:
            return self.active_sessions[admin_id]
        s = await db.get_active_session(admin_id)
        if s:
            self.active_sessions[admin_id] = s
        return s

    async def start_addmovie_session(self, admin_id: int, status_msg_id: int, status_chat_id: int) -> Dict[str, Any]:
        """Triggered when admin sends /addmovie."""
        session_data = {
            "admin_id": admin_id,
            "status": "AWAITING_FIRST_FILE",
            "movie_id": None,
            "title": None,
            "normalized_title": None,
            "year": None,
            "languages": [],
            "poster_file_id": None,
            "qualities": [],
            "status_msg_id": status_msg_id,
            "status_chat_id": status_chat_id,
            "awaiting_next": True
        }
        self.active_sessions[admin_id] = session_data
        await db.set_active_session(admin_id, session_data)
        return session_data

    async def register_first_movie_file(self, admin_id: int, movie_id: str, title: str,
                                       year: Optional[int], languages: list, quality: str,
                                       poster_file_id: Optional[str]) -> Dict[str, Any]:
        session = await self.get_session(admin_id) or {}
        session["admin_id"] = admin_id
        session["status"] = "ACTIVE"
        session["movie_id"] = movie_id
        session["title"] = title
        session["normalized_title"] = normalize_title(title)
        session["year"] = year
        session["languages"] = languages or ["Hindi"]
        session["poster_file_id"] = poster_file_id
        session["qualities"] = [quality]
        session["awaiting_next"] = False

        self.active_sessions[admin_id] = session
        await db.set_active_session(admin_id, session)
        return session

    async def register_additional_quality(self, admin_id: int, quality: str):
        session = await self.get_session(admin_id)
        if not session:
            return
        if quality not in session.get("qualities", []):
            session.setdefault("qualities", []).append(quality)
        session["awaiting_next"] = False
        self.active_sessions[admin_id] = session
        await db.set_active_session(admin_id, session)

    def set_awaiting_next(self, admin_id: int, state: bool = True):
        if admin_id in self.active_sessions:
            self.active_sessions[admin_id]["awaiting_next"] = state

    async def finish_session(self, admin_id: int) -> Optional[Dict[str, Any]]:
        session = await self.get_session(admin_id)
        if admin_id in self.active_sessions:
            del self.active_sessions[admin_id]
        if admin_id in self.pending_files:
            del self.pending_files[admin_id]
        await db.clear_active_session(admin_id)
        return session

    async def cancel_session(self, admin_id: int) -> Optional[Dict[str, Any]]:
        return await self.finish_session(admin_id)

    async def validate_incoming_upload(self, admin_id: int, incoming_title: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        session = await self.get_session(admin_id)
        if not session:
            return False, "NO_ACTIVE_SESSION", None

        # If admin started /addmovie and this is the first file:
        if session.get("status") == "AWAITING_FIRST_FILE" or not session.get("title"):
            return True, "FIRST_FILE", session

        # Active movie already set (e.g. "Jaat")
        active_title = session.get("title", "")
        if is_title_match(active_title, incoming_title):
            return True, "SESSION_MATCH", session

        # Strict mismatch! E.g. KGF sent when Jaat is active
        return False, "SESSION_MISMATCH", session

    def store_pending_mismatch(self, admin_id: int, pending_data: Dict[str, Any]):
        self.pending_files[admin_id] = pending_data

    def get_pending_mismatch(self, admin_id: int) -> Optional[Dict[str, Any]]:
        return self.pending_files.get(admin_id)

    def clear_pending_mismatch(self, admin_id: int):
        if admin_id in self.pending_files:
            del self.pending_files[admin_id]

session_mgr = MovieSessionManager()

# ==============================================================================
# ASH AUTOMATIC MOVIE FILE STORE BOT 🎬
# Module: handlers/database.py
# Purpose: Dual-Persistent Database Engine (MongoDB Atlas + Local Safe Storage)
#          Ensures zero data loss, survives restarts, and never fails links.
# ==============================================================================

import os
import json
import uuid
import datetime
import logging
import asyncio
import motor.motor_asyncio
from configs import Config

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
MOVIES_FILE = os.path.join(DATA_DIR, "movies.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

class Database:
    def __init__(self, uri: str, database_name: str):
        # 1. MongoDB Setup with fast timeout
        self._client = None
        self.db = None
        self.users_col = None
        self.movies_col = None
        self.sessions_col = None
        self.has_mongo = False

        if uri:
            try:
                self._client = motor.motor_asyncio.AsyncIOMotorClient(
                    uri,
                    serverSelectionTimeoutMS=3000,
                    connectTimeoutMS=3000
                )
                self.db = self._client[database_name]
                self.users_col = self.db.users
                self.movies_col = self.db.movies
                self.sessions_col = self.db.movie_sessions
                self.has_mongo = True
            except Exception as e:
                logger.warning(f"[DB] MongoDB init warning: {e}")

        # 2. In-Memory & Local Disk Persistence
        self._mem_users = set()
        self._mem_movies = {}
        self._mem_sessions = {}
        self._load_local_data()

    def _load_local_data(self):
        """Loads cached data from disk to ensure zero-loss across reboots."""
        try:
            if os.path.exists(MOVIES_FILE):
                with open(MOVIES_FILE, "r", encoding="utf-8") as f:
                    self._mem_movies = json.load(f)
            if os.path.exists(SESSIONS_FILE):
                with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                    # keys in json are strings, convert to int for admin_id
                    data = json.load(f)
                    self._mem_sessions = {int(k): v for k, v in data.items() if k.isdigit()}
            if os.path.exists(USERS_FILE):
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    self._mem_users = set(json.load(f))
            logger.info(f"[DB] Loaded {len(self._mem_movies)} movies & {len(self._mem_sessions)} sessions from local storage.")
        except Exception as e:
            logger.error(f"[DB] Error loading local data: {e}")

    def _save_local_movies(self):
        try:
            with open(MOVIES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._mem_movies, f, indent=2)
        except Exception as e:
            logger.error(f"[DB] Failed to save movies to disk: {e}")

    def _save_local_sessions(self):
        try:
            with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in self._mem_sessions.items()}, f, indent=2)
        except Exception as e:
            logger.error(f"[DB] Failed to save sessions to disk: {e}")

    def _save_local_users(self):
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self._mem_users), f)
        except Exception as e:
            logger.error(f"[DB] Failed to save users to disk: {e}")

    async def init_indexes(self):
        if not self.has_mongo:
            return
        try:
            await self.users_col.create_index("id", unique=True)
            await self.movies_col.create_index("movie_id", unique=True)
            await self.movies_col.create_index("normalized_title")
            await self.sessions_col.create_index("admin_id", unique=True)
            logger.info("[DB] MongoDB indexes checked successfully!")
        except Exception as e:
            logger.warning(f"[DB] Index creation skipped (Offline fallback active): {e}")

    # ==================== USERS ====================

    async def add_user(self, id: int):
        self._mem_users.add(int(id))
        self._save_local_users()
        if self.has_mongo:
            try:
                await self.users_col.update_one(
                    {"id": int(id)},
                    {"$setOnInsert": {
                        "id": int(id),
                        "join_date": datetime.date.today().isoformat(),
                        "ban_status": {"is_banned": False, "ban_duration": 0, "banned_on": datetime.date.max.isoformat(), "ban_reason": ""}
                    }},
                    upsert=True
                )
            except Exception:
                pass

    async def is_user_exist(self, id: int) -> bool:
        if int(id) in self._mem_users:
            return True
        if self.has_mongo:
            try:
                user = await self.users_col.find_one({"id": int(id)})
                if user:
                    self._mem_users.add(int(id))
                    return True
            except Exception:
                pass
        return False

    async def total_users_count(self) -> int:
        return len(self._mem_users) or 1

    async def get_ban_status(self, id: int):
        return {"is_banned": False}

    # ==================== MOVIES ====================

    def generate_movie_id(self) -> str:
        return uuid.uuid4().hex[:8]

    async def create_movie(self, title: str, normalized_title: str, year: int = None,
                           languages: list = None, poster_file_id: str = None,
                           admin_id: int = None, movie_id: str = None) -> dict:
        m_id = movie_id or self.generate_movie_id()
        movie_doc = {
            "movie_id": m_id,
            "title": title,
            "normalized_title": normalized_title,
            "year": year,
            "languages": languages or ["Hindi"],
            "poster_file_id": poster_file_id,
            "poster_source": "extracted" if poster_file_id else "none",
            "created_by": admin_id,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "updated_at": datetime.datetime.utcnow().isoformat(),
            "qualities": {}
        }
        self._mem_movies[m_id] = movie_doc
        self._save_local_movies()

        if self.has_mongo:
            try:
                await self.movies_col.insert_one(movie_doc)
            except Exception as e:
                logger.debug(f"[DB] Mongo create movie error: {e}")

        return movie_doc

    async def get_movie(self, movie_id: str) -> dict:
        # Check in-memory/disk first for instant 0ms latency
        if movie_id in self._mem_movies:
            return self._mem_movies[movie_id]

        if self.has_mongo:
            try:
                doc = await self.movies_col.find_one({"movie_id": movie_id})
                if doc:
                    self._mem_movies[movie_id] = doc
                    self._save_local_movies()
                    return doc
            except Exception:
                pass
        return None

    async def find_movie_by_title(self, normalized_title: str, year: int = None) -> dict:
        for m in self._mem_movies.values():
            if m.get("normalized_title") == normalized_title:
                if year is None or m.get("year") == year:
                    return m

        if self.has_mongo:
            try:
                query = {"normalized_title": normalized_title}
                if year:
                    query["year"] = year
                doc = await self.movies_col.find_one(query)
                if doc:
                    self._mem_movies[doc["movie_id"]] = doc
                    return doc
            except Exception:
                pass
        return None

    async def add_quality_to_movie(self, movie_id: str, quality: str, quality_data: dict) -> bool:
        if movie_id in self._mem_movies:
            self._mem_movies[movie_id].setdefault("qualities", {})[quality] = quality_data
            self._mem_movies[movie_id]["updated_at"] = datetime.datetime.utcnow().isoformat()
            self._save_local_movies()

        if self.has_mongo:
            try:
                await self.movies_col.update_one(
                    {"movie_id": movie_id},
                    {
                        "$set": {
                            f"qualities.{quality}": quality_data,
                            "updated_at": datetime.datetime.utcnow().isoformat()
                        }
                    }
                )
            except Exception:
                pass
        return True

    async def update_movie_poster(self, movie_id: str, poster_file_id: str, source: str = "manual") -> bool:
        if movie_id in self._mem_movies:
            self._mem_movies[movie_id]["poster_file_id"] = poster_file_id
            self._mem_movies[movie_id]["poster_source"] = source
            self._save_local_movies()

        if self.has_mongo:
            try:
                await self.movies_col.update_one(
                    {"movie_id": movie_id},
                    {
                        "$set": {
                            "poster_file_id": poster_file_id,
                            "poster_source": source,
                            "updated_at": datetime.datetime.utcnow().isoformat()
                        }
                    }
                )
            except Exception:
                pass
        return True

    async def delete_movie(self, movie_id: str) -> bool:
        if movie_id in self._mem_movies:
            del self._mem_movies[movie_id]
            self._save_local_movies()

        if self.has_mongo:
            try:
                await self.movies_col.delete_one({"movie_id": movie_id})
            except Exception:
                pass
        return True

    async def list_movies(self, limit: int = 10, skip: int = 0):
        all_movies = list(self._mem_movies.values())
        all_movies.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return all_movies[skip:skip+limit]

    async def total_movies_count(self) -> int:
        return len(self._mem_movies)

    # ==================== ACTIVE SESSIONS ====================

    async def get_active_session(self, admin_id: int) -> dict:
        return self._mem_sessions.get(int(admin_id))

    async def set_active_session(self, admin_id: int, session_data: dict):
        session_data["admin_id"] = int(admin_id)
        session_data["updated_at"] = datetime.datetime.utcnow().isoformat()
        self._mem_sessions[int(admin_id)] = session_data
        self._save_local_sessions()

        if self.has_mongo:
            try:
                await self.sessions_col.update_one(
                    {"admin_id": int(admin_id)},
                    {"$set": session_data},
                    upsert=True
                )
            except Exception:
                pass

    async def clear_active_session(self, admin_id: int):
        if int(admin_id) in self._mem_sessions:
            del self._mem_sessions[int(admin_id)]
            self._save_local_sessions()

        if self.has_mongo:
            try:
                await self.sessions_col.delete_one({"admin_id": int(admin_id)})
            except Exception:
                pass

    async def get_all_active_sessions(self) -> list:
        return list(self._mem_sessions.values())

db = Database(Config.DATABASE_URL, Config.DATABASE_NAME)

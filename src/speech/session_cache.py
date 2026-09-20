"""
session_cache.py — Phase 8

SQLite-backed conversation memory for the speech pipeline.
Stores turns keyed by session_id so barge-in interruptions can resume
with full context.

Schema:
  sessions(id TEXT, created_at REAL)
  turns(session_id TEXT, turn_idx INT, role TEXT, content TEXT, ts REAL)
"""

import json as _json
import sqlite3
import time
import uuid
from pathlib import Path


class SessionCache:
    """
    Lightweight SQLite session store.

    Usage:
        cache = SessionCache("./data/session_cache.db")
        sid = cache.new_session()
        cache.add_turn(sid, "user", "What is Section 3(p)?")
        cache.add_turn(sid, "assistant", "[CLEAR] Section 3(p) excludes...")
        history = cache.get_history(sid, last_n=4)
    """

    def __init__(self, db_path: str = "./data/session_cache.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS turns (
                session_id TEXT,
                turn_idx   INTEGER,
                role       TEXT,
                content    TEXT,
                ts         REAL,
                PRIMARY KEY (session_id, turn_idx)
            );
        """)
        self._db.commit()

    # ------------------------------------------------------------------

    def new_session(self, session_id: str = None) -> str:
        """Create a new session and return its ID."""
        sid = session_id or str(uuid.uuid4())
        self._db.execute(
            "INSERT OR IGNORE INTO sessions VALUES (?, ?)",
            (sid, time.time())
        )
        self._db.commit()
        return sid

    def add_turn(self, session_id: str, role: str, content: str):
        """Append a turn to the session."""
        self.new_session(session_id)
        # Use a serialised transaction to avoid turn_idx races
        with self._db:
            row = self._db.execute(
                "SELECT COALESCE(MAX(turn_idx), -1) FROM turns WHERE session_id=?",
                (session_id,)
            ).fetchone()
            next_idx = row[0] + 1
            self._db.execute(
                "INSERT INTO turns VALUES (?,?,?,?,?)",
                (session_id, next_idx, role, content, time.time())
            )

    def get_history(self, session_id: str, last_n: int = 4) -> list:
        """
        Return the last N turns as a list of {role, content} dicts
        (oldest first) — ready to pass into orchestrator session_context.
        """
        rows = self._db.execute(
            """SELECT role, content FROM turns
               WHERE session_id=?
               ORDER BY turn_idx DESC LIMIT ?""",
            (session_id, last_n)
        ).fetchall()
        # Reverse to chronological order
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def save_interruption(self, session_id: str, partial_answer: str, tts_char_pos: int):
        """
        Save the state at the moment of barge-in interruption so it can
        be resumed or referenced in the next turn.
        """
        self.add_turn(session_id, "assistant_interrupted",
                      f"[INTERRUPTED at char {tts_char_pos}] {partial_answer[:500]}")

    def list_sessions(self, limit: int = 20) -> list:
        """Return recent session IDs ordered by creation time."""
        rows = self._db.execute(
            "SELECT id, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"id": r[0], "created_at": r[1]} for r in rows]

    def save_wizard_answers(self, session_id: str, answers: dict):
        """Persist collected wizard answers (stored as a special turn role)."""
        self.add_turn(session_id, "wizard_answers", _json.dumps(answers))

    def load_wizard_answers(self, session_id: str) -> dict:
        """Return the most recently saved wizard answers for a session, or {}."""
        rows = self._db.execute(
            """SELECT content FROM turns
               WHERE session_id=? AND role='wizard_answers'
               ORDER BY turn_idx DESC LIMIT 1""",
            (session_id,)
        ).fetchone()
        if rows:
            try:
                return _json.loads(rows[0])
            except Exception:
                return {}
        return {}

    def close(self):
        """Explicitly close the DB connection (needed on Windows for file cleanup)."""
        self._db.close()

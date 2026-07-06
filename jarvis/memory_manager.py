"""
memory_manager.py — Long-term memory system for Jarvis.

Architecture:
  - SQLite: full conversation history, searchable
  - JSON:   habits, preferences, schedule patterns

Auto-extracts:
  - Habits from repeated commands (open Spotify every morning)
  - Preferences from user corrections and explicit statements
  - Schedule patterns from time-stamped activity logs
  - People mentioned in conversations

Brain injects relevant memories into every LLM prompt.
"""

import json
import re
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

log = get_logger(__name__)

DB_FILE    = Path("memory/jarvis_memory.db")
PREFS_FILE = Path("memory/user_preferences.json")
HABITS_FILE = Path("memory/habits.json")


# ── Database setup ─────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    DB_FILE.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp REAL NOT NULL,
            date      TEXT NOT NULL,
            hour      INTEGER NOT NULL,
            extracted INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS habits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            action      TEXT NOT NULL,
            hour_of_day INTEGER,
            day_of_week INTEGER,
            count       INTEGER DEFAULT 1,
            last_seen   REAL,
            UNIQUE(action, hour_of_day)
        );

        CREATE TABLE IF NOT EXISTS people (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            relation   TEXT,
            notes      TEXT,
            last_mentioned REAL
        );

        CREATE INDEX IF NOT EXISTS idx_conv_date ON conversations(date);
        CREATE INDEX IF NOT EXISTS idx_conv_hour ON conversations(hour);
        """)
    log.info("Memory database initialised.")


# ── Memory Manager ─────────────────────────────────────────────────────────────

class MemoryManager:
    """
    Manages all long-term memory for Jarvis.

    Usage:
        memory = MemoryManager()
        memory.save_turn("user", "open spotify")
        memory.save_turn("assistant", "Opening Spotify.")
        context = memory.get_context_for_prompt()
    """

    # Commands to track as habits
    HABIT_COMMANDS = [
        "open", "play", "search", "wikipedia",
        "whatsapp", "discord", "volume", "close",
    ]

    # Patterns to extract people's names
    PERSON_PATTERNS = [
        r"(?:message|call|text|whatsapp|discord)\s+([A-Z][a-z]+)",
        r"(?:this is|that is|his name is|her name is)\s+([A-Z][a-z]+)",
        r"([A-Z][a-z]+)(?:'s|\s+is\s+my)",
    ]

    def __init__(self) -> None:
        init_db()
        self._prefs: dict  = self._load_json(PREFS_FILE)
        self._habits: dict = self._load_json(HABITS_FILE)
        self._session_turns: list = []   # in-memory buffer for current session

    # ── Public API ─────────────────────────────────────────────────────────────

    def save_turn(self, role: str, content: str) -> None:
        """Save a conversation turn to SQLite."""
        now  = time.time()
        dt   = datetime.fromtimestamp(now)
        date = dt.strftime("%Y-%m-%d")
        hour = dt.hour

        with _get_db() as conn:
            conn.execute(
                "INSERT INTO conversations (role, content, timestamp, date, hour) "
                "VALUES (?, ?, ?, ?, ?)",
                (role, content, now, date, hour)
            )

        self._session_turns.append({"role": role, "content": content})

        # Auto-extract habits and people from user turns
        if role == "user":
            self._extract_habits(content, hour, dt.weekday())
            self._extract_people(content)

    def get_context_for_prompt(self) -> str:
        """
        Build a context string to inject into LLM system prompt.
        Includes: relevant habits, last session summary, schedule prediction.
        """
        parts = []

        # 1. Time-based habit prediction
        prediction = self._predict_current_needs()
        if prediction:
            parts.append(f"User habit note: {prediction}")

        # 2. Recent preferences
        pref_summary = self._get_preference_summary()
        if pref_summary:
            parts.append(f"Known preferences: {pref_summary}")

        # 3. Last session summary (what user did yesterday/last time)
        last_session = self._get_last_session_summary()
        if last_session:
            parts.append(f"Last session: {last_session}")

        return " | ".join(parts) if parts else ""

    def get_recent_history(self, turns: int = 10) -> list[dict]:
        """Get last N conversation turns from SQLite."""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT role, content FROM conversations "
                "ORDER BY timestamp DESC LIMIT ?",
                (turns * 2,)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]}
                for r in reversed(rows)]

    def search_memory(self, query: str, limit: int = 5) -> list[dict]:
        """Search conversation history for relevant past context."""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, date FROM conversations "
                "WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", limit)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"], "date": r["date"]}
                for r in rows]

    def remember_preference(self, key: str, value) -> None:
        """Explicitly store a user preference."""
        self._prefs[key] = {"value": value, "set_at": time.time()}
        self._save_json(PREFS_FILE, self._prefs)
        log.info("Preference saved: %s = %s", key, value)

    def recall_preference(self, key: str, default=None):
        entry = self._prefs.get(key)
        return entry["value"] if entry else default

    def get_habits_summary(self) -> str:
        """Return human-readable summary of learned habits."""
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT action, hour_of_day, count FROM habits "
                "ORDER BY count DESC LIMIT 10"
            ).fetchall()
        if not rows:
            return "No habits learned yet."
        lines = []
        for r in rows:
            hour = r["hour_of_day"]
            time_str = f"{hour:02d}:00" if hour is not None else "various times"
            lines.append(f"  • '{r['action']}' at {time_str} ({r['count']} times)")
        return "\n".join(lines)

    def get_daily_summary(self, date: str = None) -> str:
        """Get summary of what happened on a given date (default: today)."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, hour FROM conversations "
                "WHERE date = ? ORDER BY timestamp",
                (date,)
            ).fetchall()
        if not rows:
            return f"No activity recorded for {date}."

        user_turns = [r["content"] for r in rows if r["role"] == "user"]
        if not user_turns:
            return f"No user activity on {date}."

        # Simple summary — count commands and topics
        commands = [t for t in user_turns if len(t.split()) <= 6]
        topics   = [t for t in user_turns if len(t.split()) > 6]
        summary  = f"On {date}: {len(user_turns)} interactions. "
        if commands:
            summary += f"Commands: {', '.join(commands[:5])}. "
        if topics:
            summary += f"Topics discussed: {len(topics)}."
        return summary

    def add_person(self, name: str, relation: str = "", notes: str = "") -> None:
        """Remember a person."""
        with _get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO people (name, relation, notes, last_mentioned) "
                "VALUES (?, ?, ?, ?)",
                (name.capitalize(), relation, notes, time.time())
            )
        log.info("Person remembered: %s (%s)", name, relation)

    def get_known_people(self) -> list[dict]:
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT name, relation, notes FROM people ORDER BY last_mentioned DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Private: extraction ───────────────────────────────────────────────────

    def _extract_habits(self, text: str, hour: int, weekday: int) -> None:
        """Detect repeated commands and store as habits."""
        lower = text.lower().strip()
        for cmd in self.HABIT_COMMANDS:
            if lower.startswith(cmd) or f" {cmd} " in lower:
                action = lower[:40]  # truncate long actions
                with _get_db() as conn:
                    existing = conn.execute(
                        "SELECT id, count FROM habits WHERE action = ? AND hour_of_day = ?",
                        (action, hour)
                    ).fetchone()
                    if existing:
                        conn.execute(
                            "UPDATE habits SET count = count + 1, last_seen = ? WHERE id = ?",
                            (time.time(), existing["id"])
                        )
                    else:
                        conn.execute(
                            "INSERT INTO habits (action, hour_of_day, day_of_week, count, last_seen) "
                            "VALUES (?, ?, ?, 1, ?)",
                            (action, hour, weekday, time.time())
                        )
                break

    def _extract_people(self, text: str) -> None:
        """Extract person names mentioned in conversation."""
        for pattern in self.PERSON_PATTERNS:
            for match in re.finditer(pattern, text):
                name = match.group(1).capitalize()
                if len(name) > 2:
                    with _get_db() as conn:
                        conn.execute(
                            "INSERT OR IGNORE INTO people (name, last_mentioned) VALUES (?, ?)",
                            (name, time.time())
                        )
                        conn.execute(
                            "UPDATE people SET last_mentioned = ? WHERE name = ?",
                            (time.time(), name)
                        )

    def _predict_current_needs(self) -> str:
        """Look at habits for current hour and predict what user might want."""
        hour = datetime.now().hour
        with _get_db() as conn:
            rows = conn.execute(
                "SELECT action, count FROM habits "
                "WHERE hour_of_day = ? AND count >= 3 "
                "ORDER BY count DESC LIMIT 3",
                (hour,)
            ).fetchall()
        if not rows:
            return ""
        actions = [r["action"] for r in rows]
        return f"Around this time the user often: {'; '.join(actions)}"

    def _get_preference_summary(self) -> str:
        """Summarise stored preferences briefly."""
        if not self._prefs:
            return ""
        items = []
        for key, entry in list(self._prefs.items())[:5]:
            val = entry.get("value", entry) if isinstance(entry, dict) else entry
            items.append(f"{key}={val}")
        return ", ".join(items)

    def _get_last_session_summary(self) -> str:
        """Get a brief summary of the previous session."""
        today = datetime.now().strftime("%Y-%m-%d")
        with _get_db() as conn:
            # Get last date that isn't today
            row = conn.execute(
                "SELECT date, COUNT(*) as cnt FROM conversations "
                "WHERE date != ? GROUP BY date ORDER BY date DESC LIMIT 1",
                (today,)
            ).fetchone()
        if not row:
            return ""
        return f"{row['date']} ({row['cnt']} interactions)"

    # ── JSON helpers ──────────────────────────────────────────────────────────

    def _load_json(self, path: Path) -> dict:
        path.parent.mkdir(exist_ok=True)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_json(self, path: Path, data: dict) -> None:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

"""
db.py — SQLite database layer for the Discord Poll Bot.

Handles all CRUD operations for polls and votes.
Tables:
  - polls:  stores poll metadata (question, description, timing, status)
  - votes:  stores individual votes (one per user per poll)
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polls.db")


def _get_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database with row_factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")       # Better concurrency
    conn.execute("PRAGMA foreign_keys=ON;")         # Enforce FK constraints
    return conn


# ──────────────────────────────────────────────
#  Initialization
# ──────────────────────────────────────────────

def init_db() -> None:
    """Create the database tables if they do not already exist."""
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS polls (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id        INTEGER NOT NULL,
                channel_id      INTEGER NOT NULL,
                message_id      INTEGER,
                question        TEXT    NOT NULL,
                description     TEXT    DEFAULT '',
                options         TEXT    NOT NULL,           -- JSON-encoded list of option labels
                duration_minutes INTEGER NOT NULL,
                created_at      TEXT    NOT NULL,           -- ISO-8601 UTC
                ends_at         TEXT    NOT NULL,           -- ISO-8601 UTC
                ended           INTEGER NOT NULL DEFAULT 0, -- 0=active, 1=ended
                winning_option  TEXT    DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS votes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id     INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                option_label TEXT   NOT NULL,
                voted_at    TEXT    NOT NULL,               -- ISO-8601 UTC
                FOREIGN KEY (poll_id) REFERENCES polls(id),
                UNIQUE(poll_id, user_id)                   -- One vote per user per poll
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────
#  Poll CRUD
# ──────────────────────────────────────────────

def create_poll(
    guild_id: int,
    channel_id: int,
    question: str,
    description: str,
    options_json: str,
    duration_minutes: int,
    created_at: str,
    ends_at: str,
) -> int:
    """
    Insert a new poll into the database.
    Returns the new poll's row ID.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO polls (guild_id, channel_id, question, description, options,
                               duration_minutes, created_at, ends_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, question, description, options_json,
             duration_minutes, created_at, ends_at),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def set_poll_message_id(poll_id: int, message_id: int) -> None:
    """Update the message_id for a poll after posting it to the channel."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE polls SET message_id = ? WHERE id = ?",
            (message_id, poll_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_poll(poll_id: int) -> dict | None:
    """Fetch a single poll by ID. Returns a dict or None."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_active_polls() -> list[dict]:
    """Return all polls that have not ended yet."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM polls WHERE ended = 0").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_past_polls(guild_id: int, limit: int = 10) -> list[dict]:
    """Return the most recent ended polls for a guild."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM polls WHERE guild_id = ? AND ended = 1 ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_guild_polls(guild_id: int, limit: int = 25) -> list[dict]:
    """Return all polls (active + ended) for a guild, most recent first."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM polls WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
            (guild_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def end_poll(poll_id: int, winning_option: str | None = None) -> None:
    """Mark a poll as ended and optionally set the winning option."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE polls SET ended = 1, winning_option = ? WHERE id = ?",
            (winning_option, poll_id),
        )
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────
#  Vote CRUD
# ──────────────────────────────────────────────

def has_voted(poll_id: int, user_id: int) -> bool:
    """Check whether a user has already voted in a poll."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM votes WHERE poll_id = ? AND user_id = ?",
            (poll_id, user_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def record_vote(poll_id: int, user_id: int, option_label: str) -> bool:
    """
    Record a vote. Returns True if successful, False if the user already voted
    (enforced by the UNIQUE constraint).
    """
    conn = _get_connection()
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO votes (poll_id, user_id, option_label, voted_at) VALUES (?, ?, ?, ?)",
            (poll_id, user_id, option_label, now),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_vote_counts(poll_id: int) -> dict[str, int]:
    """
    Return a dict mapping option_label -> vote count for a poll.
    Example: {"Yes": 5, "No": 3, "Maybe": 1}
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT option_label, COUNT(*) as cnt FROM votes WHERE poll_id = ? GROUP BY option_label",
            (poll_id,),
        ).fetchall()
        return {row["option_label"]: row["cnt"] for row in rows}
    finally:
        conn.close()


def get_total_votes(poll_id: int) -> int:
    """Return the total number of votes for a poll."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM votes WHERE poll_id = ?",
            (poll_id,),
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()

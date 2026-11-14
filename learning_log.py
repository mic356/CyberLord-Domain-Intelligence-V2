"""Oga self-learning loop: question + terminal activity logging.

Stores every AI question (persona, which path answered, whether it fell
back to "I don't know") and every academy terminal command/error in a
small SQLite database. The daily trainer (train_daily.py) reads it.

Storage note (read LEARNING_LOOP.md): Render free tier has NO persistent
disk. The default file lives in /tmp and therefore survives only until
the next deploy/restart. Set LEARNING_LOG_PATH to a persistent path if
Render disk is ever enabled. Learning never breaks the request path:
every write is best-effort and failures are swallowed.
"""
import os
import re
import sqlite3
import threading
import time

_LOCK = threading.Lock()

# Cap: keep the log bounded. Oldest rows pruned past this.
MAX_ROWS = 10_000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    persona TEXT NOT NULL,
    question TEXT NOT NULL,
    answer_path TEXT NOT NULL,
    fell_back INTEGER NOT NULL,
    answer_snippet TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS terminal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    command TEXT NOT NULL DEFAULT '',
    output_snippet TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ai_questions_ts ON ai_questions(ts);
CREATE INDEX IF NOT EXISTS idx_terminal_events_ts ON terminal_events(ts);
"""

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|otp|seed|private[_-]?key)\s*(?:[:=]|is)\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|AIza[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{8,}|xox[bpas]-[A-Za-z0-9-]{8,})\b"), "[REDACTED]"),
    (re.compile(r"\b[A-Fa-f0-9]{64}\b"), "[REDACTED]"),
    # Nigerian phone numbers
    (re.compile(r"\b(\+?234|0)[789][01]\d{8}\b"), "[REDACTED]"),
    # email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED]"),
    # long base64-ish blobs (keys/tokens of ~40+ chars)
    (re.compile(r"\b[A-Za-z0-9+/=_-]{40,}\b"), "[REDACTED]"),
]


def sanitize(text, limit=600):
    """Redact secrets/PII, strip control characters, cap length."""
    if text is None:
        return ""
    s = str(text)
    for pat, repl in _SECRET_PATTERNS:
        s = pat.sub(repl, s)
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def _db_path():
    return os.environ.get("LEARNING_LOG_PATH") or os.path.join(
        os.environ.get("TMPDIR", "/tmp"), "cyberlord_learning.db"
    )


def _connect():
    con = sqlite3.connect(_db_path(), timeout=5)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(_SCHEMA)
    return con


def _prune(con):
    for table in ("ai_questions", "terminal_events"):
        con.execute(
            f"DELETE FROM {table} WHERE id NOT IN "
            f"(SELECT id FROM {table} ORDER BY id DESC LIMIT ?)",
            (MAX_ROWS,),
        )


def is_fallback(reply_text):
    """True when a built-in reply carries the 'I don't know' marker."""
    low = (reply_text or "").lower()
    return bool(
        "i don't know" in low or "i do not know" in low
        or "honest answer" in low
    )


def log_question(persona, question, answer_path, reply_text=""):
    """Record one AI question. Never raises."""
    with _LOCK:
        _log_question_inner(persona, question, answer_path, reply_text)

def _log_question_inner(persona, question, answer_path, reply_text=""):
    try:
        persona = (persona or "main").strip().lower() or "main"
        if persona not in ("tutor", "main"):
            persona = "main"
        answer_path = (answer_path or "").strip()[:40] or "unknown"
        con = _connect()
        try:
            con.execute(
                "INSERT INTO ai_questions (ts, persona, question, answer_path, fell_back, answer_snippet) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    time.time(),
                    persona,
                    sanitize(question, 600),
                    answer_path,
                    1 if is_fallback(reply_text) else 0,
                    sanitize(reply_text, 200),
                ),
            )
            _prune(con)
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def log_terminal(kind, command="", output=""):
    """Record one terminal event. kind: 'command' or 'error'. Never raises."""
    with _LOCK:
        _log_terminal_inner(kind, command, output)

def _log_terminal_inner(kind, command="", output=""):
    try:
        kind = (kind or "command").strip().lower()
        if kind not in ("command", "error"):
            kind = "command"
        con = _connect()
        try:
            con.execute(
                "INSERT INTO terminal_events (ts, kind, command, output_snippet) VALUES (?, ?, ?, ?)",
                (
                    time.time(),
                    kind,
                    sanitize(command, 300),
                    sanitize(output, 300),
                ),
            )
            _prune(con)
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


def read_all(db_path=None):
    """Return (questions, terminal_events) as lists of dicts. For the trainer."""
    path = db_path or _db_path()
    empty = ([], [])
    if not os.path.exists(path):
        return empty
    try:
        con = sqlite3.connect(path, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            qs = con.execute(
                "SELECT ts, persona, question, answer_path, fell_back, answer_snippet FROM ai_questions ORDER BY id"
            ).fetchall()
            te = con.execute(
                "SELECT ts, kind, command, output_snippet FROM terminal_events ORDER BY id"
            ).fetchall()
            return [dict(r) for r in qs], [dict(r) for r in te]
        finally:
            con.close()
    except Exception:
        return empty

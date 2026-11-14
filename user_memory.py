"""Per-user AI memory for CyberLord.

Remembers each logged-in user across sessions: recent chat summary/progress
(topics asked, lessons completed, last visit, preferences they state in chat
like "remember I'm a beginner").

Storage:
- Neon Postgres via LEARNING_DATABASE_URL (psycopg) when set.
- Graceful local sqlite fallback when unset (or Postgres unreachable),
  so the site and tests keep working with no database config.
- Optionally backed by the site's own SQLAlchemy "database" (postgres on
  Render at DATABASE_URL, sqlite locally) when neither env var is set,
  via the UserMemory model in app.py. Pass a flask/sqlalchemy session
  object (db) to the store for that behaviour.

Privacy: secrets are redacted before storage, the same way learning logs
are. Rows per user are capped. Anonymous users must never be given a
user_id; callers check authentication first.
"""
import json
import os
import re
import sqlite3
import threading
import time

MAX_ROWS_PER_USER = 20
SUMMARY_LIMIT = 1500

# Redaction: never store credentials, tokens, keys, OTPs, payment or
# wallet secrets, or database URLs, even if the user pastes them in chat.
_REDACT_PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd|pwd|passcode|pin|otp|one[- ]?time[- ]?code|secret|api[-_ ]?key|access[-_ ]?token|auth[-_ ]?token|bearer|session(?:id|token)?|cookie|private[-_ ]?key|seed[-_ ]?phrase|recovery[-_ ]?code|2fa[-_ ]?code|mfa[-_ ]?code)\b\s*[:=]\s*\S+"),
     r"\1=[REDACTED]"),
    (re.compile(r"(?i)\b(postgres(?:ql)?://|postgresql://|mysql://|mongodb(?:\+srv)?://|redis://|amqp://)\S+"),
     r"\1[REDACTED]"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_\-]{8,}|gh[pousr]_[A-Za-z0-9_]{10,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9\-]{8,}|AIza[A-Za-z0-9_\-]{10,}|gsk_[A-Za-z0-9_\-]{10,})\b"),
     "[REDACTED]"),
    (re.compile(r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}"),
     "Bearer [REDACTED]"),
    (re.compile(r"(?i)(0x)?[0-9a-f]{64,}\b"),
     "[REDACTED]"),
    (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
     "[REDACTED]"),
    (re.compile(r"\b\d{3}[- ]\d{3}\b"),
     "[REDACTED]"),
    (re.compile(r"(?i)\b(?:mnemonic|seed phrase)\b.*$"),
     "[REDACTED]"),
    (re.compile(r"(?i)\b(?:my|the|this|that)\s+(?:password|secret|otp|pin|code|seed|api[-_ ]?key|token|key)\s+is\s+\S+"),
     "REDACTED"),
]

def redact_text(text):
    """Replace secret-looking values with [REDACTED]. Never raises."""
    if not text:
        return ""
    try:
        out = str(text)
        for pat, repl in _REDACT_PATTERNS:
            out = pat.sub(repl, out)
        return out
    except Exception:
        return ""

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS user_ai_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    email TEXT DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'fact',
    summary TEXT NOT NULL DEFAULT '',
    topic TEXT DEFAULT '',
    persona TEXT DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
)
"""
_CREATE_IDX = "CREATE INDEX IF NOT EXISTS idx_user_ai_memory_user ON user_ai_memory(user_id, updated_at)"

def _connect_sqlite(path):
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _detect_backend():
    url = (os.getenv("LEARNING_DATABASE_URL") or "").strip()
    if url:
        # postgres:// -> psycopg URL stays as-is for psycopg directly
        return "postgres", url
    return "sqlite", os.getenv("USER_MEMORY_SQLITE_PATH", "instance/user_memory.db")

class MemoryStore:
    """One backend: postgres (psycopg) or sqlite. Fail-closed write on error,
    never raises to callers: memory is a nicety, never a crash source."""

    def __init__(self, backend=None, dsn=None, sqlite_path=None, flask_db=None):
        self.flask_db = flask_db
        self.backend = backend or ("postgres" if dsn else "sqlite")
        self.dsn = dsn or ""
        self.sqlite_path = sqlite_path or "instance/user_memory.db"
        self._lock = threading.Lock()
        self._ready = False
        if self.flask_db is None:
            self._ensure()

    # -- backend plumbing -------------------------------------------------
    def _ensure(self):
        if self._ready:
            return
        try:
            if self.backend == "postgres":
                import psycopg
                conn = psycopg.connect(self.dsn, connect_timeout=8)
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_ai_memory (
                        id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        email TEXT DEFAULT '',
                        kind TEXT NOT NULL DEFAULT 'fact',
                        summary TEXT NOT NULL DEFAULT '',
                        topic TEXT DEFAULT '',
                        persona TEXT DEFAULT '',
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )""")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_user_ai_memory_user ON user_ai_memory(user_id, updated_at)")
                conn.commit()
                cur.close()
                conn.close()
            else:
                os.makedirs(os.path.dirname(self.sqlite_path) or ".", exist_ok=True)
                conn = _connect_sqlite(self.sqlite_path)
                conn.execute(_CREATE_SQL)
                conn.execute(_CREATE_IDX)
                conn.commit()
                conn.close()
            self._ready = True
        except Exception:
            # graceful degradation: fall back to sqlite once, then give up quietly
            if self.backend == "postgres":
                self.backend = "sqlite"
                self.dsn = ""
                try:
                    os.makedirs(os.path.dirname(self.sqlite_path) or ".", exist_ok=True)
                    conn = _connect_sqlite(self.sqlite_path)
                    conn.execute(_CREATE_SQL)
                    conn.execute(_CREATE_IDX)
                    conn.commit()
                    conn.close()
                    self._ready = True
                except Exception:
                    self._ready = False
            else:
                self._ready = False

    def _pg_conn(self):
        import psycopg
        return psycopg.connect(self.dsn, connect_timeout=8)

    # -- public API -------------------------------------------------------
    def save(self, user_id, email, kind, summary, topic="", persona=""):
        """Persist one memory row. Returns True on success, False if skipped.
        user_id '' or None (anon) is a no-op so anonymous users stay private."""
        if not user_id:
            return False
        kind = (kind or "fact")[:20]
        summary = redact_text(str(summary or ""))[:1200].strip()
        if not summary:
            return False
        topic = redact_text(str(topic or ""))[:200]
        email = redact_text(str(email or ""))[:255]
        persona = (persona or "")[:20]
        now = time.time()
        try:
            if self.flask_db is not None:
                return self._save_flask(user_id, email, kind, summary, topic, persona, now)
            self._ensure()
            if not self._ready:
                return False
            with self._lock:
                if self.backend == "postgres":
                    conn = self._pg_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO user_ai_memory (user_id, email, kind, summary, topic, persona, created_at, updated_at)"
                        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (str(user_id), email, kind, summary, topic, persona, now, now))
                    cur.execute(
                        "DELETE FROM user_ai_memory WHERE id IN ("
                        " SELECT id FROM user_ai_memory WHERE user_id=%s"
                        " ORDER BY updated_at DESC, id DESC OFFSET %s)",
                        (str(user_id), MAX_ROWS_PER_USER))
                    conn.commit()
                    cur.close()
                    conn.close()
                else:
                    conn = _connect_sqlite(self.sqlite_path)
                    conn.execute(_CREATE_SQL)
                    conn.execute(
                        "INSERT INTO user_ai_memory (user_id, email, kind, summary, topic, persona, created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (str(user_id), email, kind, summary, topic, persona, now, now))
                    conn.execute(
                        "DELETE FROM user_ai_memory WHERE id IN ("
                        " SELECT id FROM user_ai_memory WHERE user_id=?"
                        " ORDER BY updated_at DESC, id DESC LIMIT -1 OFFSET ?)",
                        (str(user_id), MAX_ROWS_PER_USER))
                    conn.commit()
                    conn.close()
            return True
        except Exception:
            return False

    def _save_flask(self, user_id, email, kind, summary, topic, persona, now):
        from datetime import datetime, timezone
        try:
            from app import db, UserMemory
            dt = datetime.utcfromtimestamp(now)
            row = UserMemory(user_id=str(user_id), email=email or "", kind=kind,
                             summary=summary, topic=topic, persona=persona,
                             updated_at=dt)
            db.session.add(row)
            db.session.commit()
            rows = (UserMemory.query.filter_by(user_id=str(user_id))
                    .order_by(UserMemory.updated_at.desc(), UserMemory.id.desc())
                    .offset(MAX_ROWS_PER_USER).all())
            for r in rows:
                db.session.delete(r)
            if rows:
                db.session.commit()
            return True
        except Exception:
            try:
                from app import db
                db.session.rollback()
            except Exception:
                pass
            return False

    def load(self, user_id, limit=8):
        """Return list of memory dicts, newest first. [] for anon/unknown."""
        if not user_id:
            return []
        try:
            if self.flask_db is not None:
                return self._load_flask(user_id, limit)
            self._ensure()
            if not self._ready:
                return []
            with self._lock:
                if self.backend == "postgres":
                    conn = self._pg_conn()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT user_id, email, kind, summary, topic, persona, created_at, updated_at"
                        " FROM user_ai_memory WHERE user_id=%s ORDER BY updated_at DESC, id DESC LIMIT %s",
                        (str(user_id), limit))
                    rows = [dict(zip([d.name for d in cur.description], r)) for r in cur.fetchall()]
                    cur.close()
                    conn.close()
                else:
                    conn = _connect_sqlite(self.sqlite_path)
                    conn.execute(_CREATE_SQL)
                    cur = conn.execute(
                        "SELECT user_id, email, kind, summary, topic, persona, created_at, updated_at"
                        " FROM user_ai_memory WHERE user_id=? ORDER BY updated_at DESC, id DESC LIMIT ?",
                        (str(user_id), limit))
                    rows = [dict(r) for r in cur.fetchall()]
                    conn.close()
            return [{k: (v if v is not None else "") for k, v in r.items()} for r in rows]
        except Exception:
            return []

    def _load_flask(self, user_id, limit):
        try:
            from app import UserMemory
            rows = (UserMemory.query.filter_by(user_id=str(user_id))
                    .order_by(UserMemory.updated_at.desc(), UserMemory.id.desc())
                    .limit(limit).all())
            return [{"user_id": r.user_id, "email": r.email or "", "kind": r.kind,
                     "summary": r.summary or "", "topic": r.topic or "",
                     "persona": r.persona or "", "created_at": 0, "updated_at": 0} for r in rows]
        except Exception:
            return []

    def context_summary(self, user_id, email="", limit=8):
        """Short block for the AI system context, or '' when nothing known."""
        rows = self.load(user_id, limit=limit)
        if not rows:
            return ""
        bits = []
        name = (email or rows[0].get("email") or "").strip()
        if name:
            bits.append("this is %s" % name)
        for r in rows:
            bits.append(r.get("summary") or "")
        text = "; ".join(b for b in bits if b).strip()
        if not text:
            return ""
        return text[:SUMMARY_LIMIT]

    def touch_visit(self, user_id, email, persona=""):
        return self.save(user_id, email, "visit", "last visit: %s" % time.strftime("%Y-%m-%d"), persona=persona)

# -- module-level helpers used by app.py -----------------------------------

_default_store = None

def get_store(flask_db=None):
    """Lazily build the store from env: LEARNING_DATABASE_URL, else sqlite."""
    global _default_store
    if _default_store is not None:
        return _default_store
    backend, dsn_or_path = _detect_backend()
    if backend == "postgres":
        _default_store = MemoryStore(backend="postgres", dsn=dsn_or_path, flask_db=flask_db)
    else:
        _default_store = MemoryStore(backend="sqlite", sqlite_path=dsn_or_path, flask_db=flask_db)
    return _default_store

def reset_store():
    global _default_store
    _default_store = None

_REMEMBER_RES = [
    re.compile(r"(?i)\bremember\s+(?:this|that|me|us)\b[:\s,]*?(.*)$"),
    re.compile(r"(?i)\bremember\s+(?:i'?m|i am|my name is|call me)\s+(.*)$"),
    re.compile(r"(?i)\bkeep in mind\s+(?:that\s+)?(.*)$"),
    re.compile(r"(?i)\bdon'?t forget\s+(?:that\s+)?(.*)$"),
    re.compile(r"(?i)\bnote to (?:remember|self)\b[:\s,]*?(.*)$"),
]

def extract_remember(text):
    """Return the fact a user asked to remember, or '' if they didn't."""
    low = (text or "").strip()
    for pat in _REMEMBER_RES:
        m = pat.search(low)
        if m:
            fact = m.group(1).strip(" .!?")
            if fact and len(fact) >= 2:
                return redact_text(fact)[:400]
    return ""

def is_remember_request(text):
    return bool(extract_remember(text))

# ---------------------------------------------------------------------------
# Automatic fact extraction (silent memory).
#
# The AI saves durable user facts on its own, without the user ever having
# to say "remember this", and the reply never announces any of it. Only
# facts stated about the user are picked up (name, skill level, study/work
# context, goals, preferences, location). Questions and facts about third
# parties (including the AI itself) are deliberately ignored so memory
# stays accurate. Every candidate still goes through redact_text + the
# normal save() path, so secrets are never stored.
# ---------------------------------------------------------------------------
def display_name_from_email(email):
    """Best-effort first name from an email local-part, or ''."""
    try:
        local = str(email or "").split("@", 1)[0]
        local = re.sub(r"[^A-Za-z]+", " ", local).strip()
        if not local:
            return ""
        return local.split()[0].capitalize()[:40]
    except Exception:
        return ""

# (kind, pattern, template) -- template's {fact} is group 1, cleaned.
_FACT_PATTERNS = [
    ("fact", re.compile(r"(?i)\bmy name(?:'s| is) ([A-Za-z][A-Za-z '\-]{1,30})"),
     "user's name is {fact}"),
    ("fact", re.compile(r"(?i)\bcall me ([A-Za-z][A-Za-z '\-]{1,30})"),
     "user's name is {fact}"),
    ("fact", re.compile(r"(?i)\bi am (?:called|named|known as) ([A-Za-z][A-Za-z '\-]{1,30})"),
     "user's name is {fact}"),
    ("preference", re.compile(
        r"(?i)\bi(?:'m| am) (?:a )?(beginner|intermediate|advanced|newbie|expert|student|professional|experienced|noob)(?: level)?\b"),
     "user is a {fact}"),
    ("preference", re.compile(
        r"(?i)\bi (?:have|had) (?:had )?(?:about |up to |around )?(\d{1,3}) (?:years?|yrs?) of (?:experience|cyber(?:security)?|security|networking|programming|coding|it)"),
     "user has {fact} years of experience"),
    ("preference", re.compile(r"(?i)\bi (?:study|learn|am studying|am learning) at (night|nights|evening|evenings|morning|mornings|weekends?)\b"),
     "user studies at {fact}"),
    ("preference", re.compile(r"(?i)\bi (?:like|prefer|love|enjoy|want) (short answers?|long answers?|step[- ]by[- ]step|short|detailed|long|quick|simple|practical|visual|text[- ]based|code[- ]based|examples?|videos?|audios?)"),
     "user prefers {fact}"),
    ("fact", re.compile(r"(?i)\bi (?:study|am studying|learn|am learning) (?:at|in) ((?:.+? )(?:school|college|university|class))\b"),
     "user studies at {fact}"),
    ("fact", re.compile(r"(?i)\bi (?:work|am working|am employed) (?:as|in|at) ((?:a |an |the )?[^.,!?]{2,60})"),
     "user works as {fact}"),
    ("fact", re.compile(r"(?i)\bi live in ([A-Za-z][A-Za-z .'\-]{1,40})"),
     "user lives in {fact}"),
    ("fact", re.compile(r"(?i)\bi(?:'m| am) from ([A-Za-z][A-Za-z .'\-]{1,40})"),
     "user is from {fact}"),
    ("fact", re.compile(r"(?i)\bmy goal(?:s| is)? (?:is |are )?to ((?:become|be|learn|master|get|understand|build|start)(?: [a-z]+){0,5})"),
     "user's goal is to {fact}"),
    ("fact", re.compile(r"(?i)\bi want to (?:be (?:a|an) )?((?:a|an) [a-z]+|[a-z]+(?: [a-z]+){0,3})"),
     "user wants to be {fact}"),
]
# Cues that mark a match as third-party / not about the user: skip them.
_THIRD_PARTY_RE = re.compile(
    r"(?i)\b(he|she|his|her|they|their|the academy|the tutor|cyber|the site|it|this lesson|the course)\b")
_QUESTION_RE = re.compile(r"^\s*(what|how|why|when|where|who|can|could|do|does|is|are|tell|explain|help)\b", re.I)
_STOP_FACTS = {"the", "a", "an", "to", "it", "that", "this", "my", "you", "me"}

def _clean_fact(raw):
    fact = redact_text(re.sub(r"\s+", " ", str(raw or ""))).strip(" .!?,;:'\"")
    # Cut trailing clauses that would turn a fact into a question or a
    # third-party statement ("... and what about nmap?").
    fact = re.split(r"(?i)\s+(?:and|but|so|what|how|why|when|where|can you)\b", fact)[0].strip(" .!?,;:'\"")
    if not fact or fact.lower() in _STOP_FACTS:
        return ""
    return fact[:300]

def extract_facts(text):
    """Return a list of (kind, fact) durable facts stated by the user.

    Explicit "remember ..." facts come first (via extract_remember),
    then automatic facts. Questions, third-party statements and the
    AI's own content never produce facts. Never raises.
    """
    raw = str(text or "")
    if not raw or len(raw) > 2000:
        return []
    is_question = bool(_QUESTION_RE.match(raw.strip()))
    facts, seen = [], set()
    explicit = extract_remember(raw)
    if explicit and explicit not in seen:
        # An explicit remember sentence is never a question; if it does
        # end in a "?" the user is asking, not telling, so skip it.
        if "?" not in explicit:
            seen.add(explicit)
            facts.append(("preference", explicit))
    if is_question:
        return facts
    for kind, pat, template in _FACT_PATTERNS:
        try:
            m = pat.search(raw)
        except Exception:
            continue
        if not m:
            continue
        # Only the last non-None group matters to the template callers.
        captured = next((g for g in m.groups() if g), None)
        if _THIRD_PARTY_RE.search(raw[:m.start()] + " " + raw[m.end():]):
            # The surrounding turn is about someone/something else.
            if m.start() > 0:
                continue
        fact = _clean_fact(captured)
        if not fact:
            continue
        if fact.lower() in ("my name",):
            continue
        summary = template.format(fact=fact)
        if summary in seen or summary.lower() in seen:
            continue
        seen.add(summary)
        # Never store secrets, and never store a fact that looks like a
        # question ("what is phishing" etc.).
        if "?" in summary or re.search(r"(?i)\b(what|how|why|when|where)\b", summary[:12]):
            continue
        facts.append((kind, summary))
    return facts

def extract_facts_from_turns(messages):
    """facts from the latest user turn only (history can be stale/conflicting)."""
    if not messages:
        return []
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
            return extract_facts(m["content"])
    return []

def remember_facts(store, user_id, email, messages, persona=""):
    """Silently persist durable facts from the conversation. Returns the
    count stored; the reply path must never mention this happened."""
    if not user_id:
        return 0
    stored = 0
    for kind, fact in extract_facts_from_turns(messages):
        try:
            kind = (kind or "fact")
            if store.save(str(user_id), email or "", kind, fact,
                          persona=(persona or "")[:20]):
                stored += 1
        except Exception:
            continue
    return stored

def lesson_completed_summary(lesson_title):
    return "completed lesson: %s" % redact_text(str(lesson_title or ""))[:200]

def topic_summary(text):
    t = redact_text(str(text or ""))[:200]
    if not t:
        return ""
    return "previously asked: %s" % t

def compose_system_context(email, context_summary, persona=""):
    """Block to prepend to the system prompt for a returning user."""
    if not context_summary:
        return ""
    parts = ["You are talking to %s (logged in), a returning CyberLord user." % (email or "this user")]
    parts.append("What you remember about them: %s." % context_summary[:SUMMARY_LIMIT])
    parts.append("Great them like a regular: say hello warmly, use their remembered name if you have one, and keep the conversation moving; never ask them to repeat what they already told you.")
    parts.append("Never announce, mention or hint that you saved, stored, learned or remember anything about them.")
    return " ".join(parts)

"""Public site reviews for CyberLord.

Visitors leave a star rating (1-5) plus short text on the homepage.
New reviews start as "pending" and only appear publicly after the
owner approves them in the existing /admin area.

Storage:
- Neon Postgres via LEARNING_DATABASE_URL (psycopg) when set.
- Local sqlite fallback when unset (or Postgres unreachable).
Never raises to callers: reviews are a nicety, never a crash source.
"""
import os
import re
import sqlite3
import threading
import time

REVIEW_TEXT_LIMIT = 500
REVIEW_NAME_LIMIT = 60
REVIEW_EMAIL_LIMIT = 120
REVIEW_STATUSES = ("pending", "approved", "rejected")

# Basic profanity / spam guard: whole-word matches against a small block
# list, plus crude URL/link spam and repeated-character spam checks.
_BANNED_RE = re.compile(
    r"(?i)\b(fuck|shit|bitch|bastard|asshole|dick|porn|xxx|viagra|casino|"
    r"free money|click here|buy now|spam|scam|idiot|stupid)"
    r"\b"
)
_URL_RE = re.compile(r"(?i)(https?://|www\.|\.com/|\.ng/|\.ru/)")
_REPEAT_RE = re.compile(r"(.)\1{9,}")


def clean_text(raw):
    return " ".join(str(raw or "").split()).strip()


def validate_review(name, rating, text, email=""):
    """Return (ok, error). Pure function, no DB."""
    try:
        rating_int = int(rating)
    except (TypeError, ValueError):
        return False, "Rating must be a whole number between 1 and 5."
    # Reject bools and floats that are not whole numbers.
    if isinstance(rating, bool) or (isinstance(rating, float) and not rating.is_integer()):
        return False, "Rating must be a whole number between 1 and 5."
    if rating_int < 1 or rating_int > 5:
        return False, "Rating must be between 1 and 5."
    text_clean = clean_text(text)
    if not text_clean:
        return False, "Please write a few words about your experience."
    if len(text_clean) > REVIEW_TEXT_LIMIT:
        return False, "Review text must be %d characters or fewer." % REVIEW_TEXT_LIMIT
    if _BANNED_RE.search(text_clean) or _BANNED_RE.search(clean_text(name)):
        return False, "Review blocked: please keep it respectful and free of bad language."
    if _URL_RE.search(text_clean):
        return False, "Review blocked: please remove links from your review."
    if _REPEAT_RE.search(text_clean):
        return False, "Review blocked: please avoid repeated characters."
    name_clean = clean_text(name) or "anonymous"
    if len(name_clean) > REVIEW_NAME_LIMIT:
        return False, "Name must be %d characters or fewer." % REVIEW_NAME_LIMIT
    email_clean = clean_text(email)
    if email_clean and ("@" not in email_clean or len(email_clean) > REVIEW_EMAIL_LIMIT):
        return False, "That email address does not look right."
    return True, ""


# -- storage -----------------------------------------------------------------

_CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS site_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT 'anonymous',
    rating INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    email TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL
)
"""
_CREATE_PG = """
CREATE TABLE IF NOT EXISTS site_reviews (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'anonymous',
    rating INTEGER NOT NULL,
    text TEXT NOT NULL DEFAULT '',
    email TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at DOUBLE PRECISION NOT NULL
)
"""
_IDX = "CREATE INDEX IF NOT EXISTS idx_site_reviews_status ON site_reviews(status, created_at)"


def _connect_sqlite(path):
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _detect_backend():
    url = (os.getenv("LEARNING_DATABASE_URL") or "").strip()
    if url:
        return "postgres", url
    return "sqlite", os.getenv("REVIEWS_SQLITE_PATH", "instance/reviews.db")


class ReviewStore:
    """One backend: postgres (psycopg) or sqlite. Fail-closed write on error."""

    def __init__(self, backend=None, dsn=None, sqlite_path=None):
        self.backend = backend or ("postgres" if dsn else "sqlite")
        self.dsn = dsn or ""
        self.sqlite_path = sqlite_path or "instance/reviews.db"
        self._lock = threading.Lock()
        self._ready = False
        self._ensure()

    def _ensure(self):
        if self._ready:
            return
        try:
            if self.backend == "postgres":
                import psycopg
                conn = psycopg.connect(self.dsn, connect_timeout=8)
                cur = conn.cursor()
                cur.execute(_CREATE_PG)
                cur.execute(_IDX)
                conn.commit()
                cur.close()
                conn.close()
            else:
                parent = os.path.dirname(self.sqlite_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                conn = _connect_sqlite(self.sqlite_path)
                conn.execute(_CREATE_SQLITE)
                conn.execute(_IDX)
                conn.commit()
                conn.close()
            self._ready = True
        except Exception:
            pass

    def _conn(self):
        if self.backend == "postgres":
            import psycopg
            return psycopg.connect(self.dsn, connect_timeout=8)
        return _connect_sqlite(self.sqlite_path)

    def submit(self, name, rating, text, email=""):
        """Validate and insert as pending. Returns (ok, error, row_or_None)."""
        ok, err = validate_review(name, rating, text, email)
        if not ok:
            return False, err, None
        rating_int = int(rating)
        name_clean = clean_text(name) or "anonymous"
        text_clean = clean_text(text)
        email_clean = clean_text(email)
        now = time.time()
        try:
            with self._lock:
                conn = self._conn()
                cur = conn.cursor()
                if self.backend == "postgres":
                    cur.execute(
                        "INSERT INTO site_reviews (name, rating, text, email, status, created_at)"
                        " VALUES (%s, %s, %s, %s, 'pending', %s) RETURNING id",
                        (name_clean, rating_int, text_clean, email_clean, now),
                    )
                    row_id = cur.fetchone()[0]
                else:
                    cur.execute(
                        "INSERT INTO site_reviews (name, rating, text, email, status, created_at)"
                        " VALUES (?, ?, ?, ?, 'pending', ?)",
                        (name_clean, rating_int, text_clean, email_clean, now),
                    )
                    row_id = cur.lastrowid
                conn.commit()
                cur.close()
                conn.close()
        except Exception:
            return False, "Could not save your review right now. Please try again.", None
        return True, "", {
            "id": row_id, "name": name_clean, "rating": rating_int,
            "text": text_clean, "email": email_clean,
            "status": "pending", "created_at": now,
        }

    def list_approved(self, limit=20):
        try:
            with self._lock:
                conn = self._conn()
                cur = conn.cursor()
                ph = "%s" if self.backend == "postgres" else "?"
                cur.execute(
                    "SELECT id, name, rating, text, created_at FROM site_reviews"
                    " WHERE status='approved' ORDER BY created_at DESC LIMIT " + ph,
                    (int(limit),),
                )
                rows = cur.fetchall()
                cur.close()
                conn.close()
        except Exception:
            return []
        return [
            {"id": r[0], "name": r[1], "rating": r[2], "text": r[3], "created_at": r[4]}
            for r in rows
        ]

    def average_rating(self):
        try:
            with self._lock:
                conn = self._conn()
                cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(AVG(rating), 0), COUNT(*) FROM site_reviews WHERE status='approved'"
                )
                row = cur.fetchone()
                cur.close()
                conn.close()
        except Exception:
            return 0.0, 0
        return float(row[0] or 0.0), int(row[1] or 0)

    def public_summary(self, limit=20):
        avg, count = self.average_rating()
        return {
            "average_rating": round(avg, 1),
            "review_count": count,
            "reviews": self.list_approved(limit=limit),
        }

    def list_by_status(self, status, limit=250):
        if status not in REVIEW_STATUSES and status != "all":
            status = "pending"
        try:
            with self._lock:
                conn = self._conn()
                cur = conn.cursor()
                ph = "%s" if self.backend == "postgres" else "?"
                if status == "all":
                    cur.execute(
                        "SELECT id, name, rating, text, email, status, created_at FROM site_reviews"
                        " ORDER BY created_at DESC LIMIT " + ph,
                        (int(limit),),
                    )
                else:
                    cur.execute(
                        "SELECT id, name, rating, text, email, status, created_at FROM site_reviews"
                        " WHERE status=" + ph + " ORDER BY created_at DESC LIMIT " + ph,
                        (status, int(limit)),
                    )
                rows = cur.fetchall()
                cur.close()
                conn.close()
        except Exception:
            return []
        return [
            {"id": r[0], "name": r[1], "rating": r[2], "text": r[3],
             "email": r[4], "status": r[5], "created_at": r[6]}
            for r in rows
        ]

    def status_counts(self):
        counts = {"pending": 0, "approved": 0, "rejected": 0}
        try:
            with self._lock:
                conn = self._conn()
                cur = conn.cursor()
                cur.execute("SELECT status, COUNT(*) FROM site_reviews GROUP BY status")
                for status, n in cur.fetchall():
                    counts[status] = int(n)
                cur.close()
                conn.close()
        except Exception:
            pass
        return counts

    def set_status(self, review_id, new_status):
        if new_status not in REVIEW_STATUSES:
            return False
        try:
            with self._lock:
                conn = self._conn()
                cur = conn.cursor()
                ph = "%s" if self.backend == "postgres" else "?"
                cur.execute(
                    "UPDATE site_reviews SET status=" + ph + " WHERE id=" + ph,
                    (new_status, int(review_id)),
                )
                if self.backend == "postgres":
                    changed = cur.rowcount != 0
                else:
                    cur.execute("SELECT changes()")
                    changed = cur.fetchone()[0] > 0
                conn.commit()
                cur.close()
                conn.close()
        except Exception:
            return False
        return changed


_default_store = None


def get_store():
    """Lazily build the store from env: LEARNING_DATABASE_URL, else sqlite."""
    global _default_store
    if _default_store is not None:
        return _default_store
    backend, dsn_or_path = _detect_backend()
    if backend == "postgres":
        _default_store = ReviewStore(backend="postgres", dsn=dsn_or_path)
    else:
        _default_store = ReviewStore(backend="sqlite", sqlite_path=dsn_or_path)
    return _default_store


def reset_store():
    global _default_store
    _default_store = None

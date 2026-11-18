import os, re, json, hmac, hashlib, secrets, socket, ssl, ipaddress, subprocess, shutil, time, threading, base64, csv, wave

from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse, parse_qs
import requests
import dns.resolver
import phonenumbers
import phonenumbers.carrier
import phonenumbers.timezone
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from io import BytesIO
from PIL import Image, ImageOps
from html.parser import HTMLParser
from difflib import SequenceMatcher
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle, KeepTogether

from academy_questions import ACADEMY_LESSONS, ACADEMY_COURSES, get_course_for_lesson, course_lessons

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "CHANGE-ME-TO-A-LONG-RANDOM-SECRET")
# Large media bypasses Flask request-body limits through direct multipart object-storage uploads.
# Ordinary chat/image endpoints retain a conservative request cap.
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("CYBERLORD_WEB_REQUEST_MAX_BYTES", str(30 * 1024 * 1024)))
CYBERLORD_LARGE_FILE_MAX_BYTES = min(
    max(int(os.getenv("CYBERLORD_LARGE_FILE_MAX_BYTES", str(2 * 1024 * 1024 * 1024))), 5 * 1024 * 1024),
    2 * 1024 * 1024 * 1024,
)
CYBERLORD_MULTIPART_PART_BYTES = 16 * 1024 * 1024


def _large_upload_s3():
    """Return an S3-compatible Backblaze B2 client; credentials remain server-side."""
    endpoint = os.getenv("B2_ENDPOINT_URL", "").strip().rstrip("/")
    access = os.getenv("B2_KEY_ID", "").strip()
    secret = os.getenv("B2_APPLICATION_KEY", "").strip()
    region = os.getenv("B2_REGION", "us-west-004").strip()
    if not all((endpoint, access, secret, os.getenv("B2_BUCKET_NAME", "").strip())):
        return None
    try:
        import boto3
        from botocore.config import Config
        return boto3.client(
            "s3", endpoint_url=endpoint,
            aws_access_key_id=access, aws_secret_access_key=secret,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    except Exception as exc:
        app.logger.warning("Large upload storage is unavailable: %s", str(exc)[:160])
        return None


def _large_upload_bucket():
    return os.getenv("B2_BUCKET_NAME", "").strip()


def _large_upload_allowed(filename, mime):
    ext = os.path.splitext(filename or "")[1].lower()
    allowed = {
        ".mp4": {"video/mp4"}, ".mov": {"video/quicktime"}, ".webm": {"video/webm"},
        ".mpeg": {"video/mpeg"}, ".mpg": {"video/mpeg"}, ".pdf": {"application/pdf"},
        ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".png": {"image/png"}, ".webp": {"image/webp"},
        ".mp3": {"audio/mpeg"}, ".wav": {"audio/wav", "audio/x-wav"},
        ".m4a": {"audio/mp4", "audio/x-m4a"}, ".ogg": {"audio/ogg"},
        ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
        ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
        ".txt": {"text/plain"}, ".md": {"text/markdown", "text/plain"},
        ".csv": {"text/csv", "application/vnd.ms-excel", "text/plain"},
    }
    return ext in allowed and mime in allowed[ext]



def _normalize_image_for_ai(raw, mime_type=None, max_bytes=2_500_000):
    """Accept larger uploads, then resize/re-encode them for efficient AI vision input."""
    if not raw or len(raw) > 25 * 1024 * 1024:
        return None
    try:
        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
        if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            image = background
        else:
            image = image.convert("RGB")
        quality = 90
        while quality >= 45:
            output = BytesIO()
            image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
            data = output.getvalue()
            if len(data) <= max_bytes:
                return {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}
            quality -= 7
        # If still large, reduce dimensions and retry once more.
        image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="JPEG", quality=55, optimize=True)
        data = output.getvalue()
        if len(data) <= max_bytes:
            return {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}
    except Exception as exc:
        app.logger.warning("Image normalization failed: %s", str(exc)[:140])
    return None

# Keep cookies out of reach of JavaScript, limit cross-site sending, and
# mark them Secure over HTTPS. Render always serves the app over HTTPS, so
# Secure is on in production; locally (plain http), omit it so tests and
# local development still work.
_ON_RENDER = bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_HOSTNAME"))
_USE_SECURE = _ON_RENDER or os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = _USE_SECURE
app.config["REMEMBER_COOKIE_HTTPONLY"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
app.config["REMEMBER_COOKIE_SECURE"] = _USE_SECURE

db_url = os.getenv("DATABASE_URL", "sqlite:///cyberlord.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True} if db_url.startswith("postgresql") else {}

# ---------------------------------------------------------------------------
# In-memory rate limiting (no Redis: Render free tier). Sliding window per IP.
# Stored in process memory only, so counters reset on restart or redeploy;
# while the process is alive the limits are enforced for any slot of time.
# ---------------------------------------------------------------------------
def _env_float(name, default):
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return float(default)

def _env_int(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return int(default)

LOGIN_FAIL_DELAY = _env_float("LOGIN_FAIL_DELAY_SEC", 1.5)
RATE_LIMITS = {
    "login": (_env_int("LOGIN_MAX_ATTEMPTS", 5), _env_int("LOGIN_WINDOW_SEC", 300)),
    "register": (_env_int("REGISTER_MAX_ATTEMPTS", 10), _env_int("REGISTER_WINDOW_SEC", 900)),
    "forgot": (_env_int("FORGOT_MAX_ATTEMPTS", 5), _env_int("FORGOT_WINDOW_SEC", 900)),
    "scan": (_env_int("SCAN_MAX_ATTEMPTS", 10), _env_int("SCAN_WINDOW_SEC", 60)),
    "review": (_env_int("REVIEW_MAX_ATTEMPTS", 5), _env_int("REVIEW_WINDOW_SEC", 3600)),

}

_rate_lock = threading.Lock()
_rate_store = {}  # key -> list[timestamps]


def client_ip():
    """Best-effort client address behind Cloudflare/Render proxies."""
    for header in ("CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"):
        raw = request.headers.get(header, "")
        if raw:
            candidate = raw.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                continue
    return request.remote_addr or "unknown"


def rate_limited(*, key, limit, window):
    """Sliding-window check. Returns True when this request exceeds the limit.

    When the limit is exceeded, the rejected attempt IS recorded, so a client
    that keeps hammering stays blocked (a sustained hammering only extends its
    own lockout, it never lets it pass). Expired slots are dropped, and a
    slot that ages out is freed. Storage is process memory only, so counters
    reset on a restart or redeploy and fail open (traffic allowed again).
    """
    now = time.monotonic()
    with _rate_lock:
        hits = _rate_store.get(key, [])
        cutoff = now - window
        hits = [t for t in hits if t > cutoff]
        _rate_store[key] = hits
        if len(hits) >= limit:
            return True
        hits.append(now)
        return False


def _check_rate(kind, *extra):
    """Returns a 429 response when the named limit is hit, else None."""
    limit, window = RATE_LIMITS[kind]
    suffix = ":" + ":".join(extra) if extra else ""
    key = kind + ":" + client_ip() + suffix
    if rate_limited(key=key, limit=limit, window=window):
        app.logger.warning("Rate limit hit: %s", key)
        return jsonify(error="Too many attempts. Please wait a little and try again."), 429
    return None


def rate_limit(kind):
    """Decorator: per-IP sliding-window limit for one endpoint kind."""
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            limit_resp = _check_rate(kind)
            if limit_resp is not None:
                return limit_resp
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def form_str(name, max_length):
    """Trimmed form value, truncated to a sane length so oversized posts
    cannot blow up stored fields or column sizes downstream."""
    return (request.form.get(name, "") or "").strip()[:max_length]


# ---------------------------------------------------------------------------
# Security headers + session cookie flags.
# The site renders from inline template code rather than JS bundles, so the
# CSP allows self plus inline scripts/styles. The inline content is:
#   <script> in templates/base.html (theme bootstrap on page load)
#   <script> in templates/login.html (theme bootstrap + theme toggle)
#   <script> in templates/payment_result.html (same as login.html)
#   <script type="application/ld+json"> in base.html / index.html / faq.html
#   a <style> block in templates/login.html, and external fonts
#   (https://fonts.googleapis.com) on the login page.
# Withdrawing 'unsafe-inline' later, once the inline theme-bootstrap script
# is moved into a static file, is a safe follow-up but is not required for
# the app to stay working on the free tier.
# ---------------------------------------------------------------------------
CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)


@app.after_request
def add_security_headers(response):
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response


db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# Fixed prices agreed for launch. NGN prices are fixed rather than live FX conversions.
PLANS = {
    "free": {"name": "FREE", "price": 0, "ngn": 0, "rank": 0},
    "pro": {"name": "PRO", "price": 6300, "ngn": 6300, "rank": 1},
    "pro_plus": {"name": "PRO PLUS", "price": 12600, "ngn": 12600, "rank": 2},
    # Tutor Pro is a separate add-on entitlement (see tutor_pro_expires_at on User).
    # rank stays 0 so it never unlocks PRO / PRO PLUS scan tools or courses on its own;
    # it only unlocks unlimited tutor chat + voice UI + Code Lab.
    "tutor_pro": {"name": "TUTOR PRO", "price": 6300, "ngn": 6300, "rank": 0},
}
TUTOR_FREE_DAILY_LIMIT = 10
TUTOR_PRO_NGN = 6300
PRO_TOOLS = {"phone", "email_review", "breach"}
PLUS_TOOLS = {"attack_surface", "cve", "compare", "port"}
TOOL_NAMES = {
    "domain": "Domain Security Scan", "subdomains": "Subdomain Intelligence",
    "email": "Email Security", "dns": "DNS Intelligence", "technology": "Technology Fingerprint",
    "ip": "IP Intelligence", "phone": "Phone Intelligence", "email_review": "Individual Email Review",
    "breach": "Breach Exposure", "attack_surface": "Attack Surface Map",
    "cve": "CVE Intelligence", "compare": "Compare Domains", "port": "Limited Port Scanner", "deep_scan": "Deep Scan"
}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    plan = db.Column(db.String(20), default="free", nullable=False)
    plan_expires_at = db.Column(db.DateTime)
    # Separate add-on: Tutor Pro (unlimited tutor + Code Lab) for 30 days.
    # Kept distinct from `plan` so a PRO / PRO PLUS user can add Tutor Pro
    # without losing their main plan.
    tutor_pro_expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reference = db.Column(db.String(120), unique=True, nullable=False, index=True)
    plan = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime)
    currency = db.Column(db.String(10), default="NGN", nullable=False)
    network = db.Column(db.String(20))
    tx_hash = db.Column(db.String(140), unique=True, index=True)
    expires_at = db.Column(db.DateTime)

class BankReceipt(db.Model):
    """Private receipt evidence stored in the database (not ephemeral Render disk)."""
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payment.id"), nullable=False, unique=True, index=True)
    filename = db.Column(db.String(180), nullable=False)
    content_type = db.Column(db.String(80), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class MessagingLinkCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class MessagingAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(16), nullable=False)
    external_id = db.Column(db.String(160), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    linked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("channel", "external_id", name="uq_messaging_channel_external"),)


class MessagingState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(16), nullable=False)
    external_id = db.Column(db.String(160), nullable=False)
    persona = db.Column(db.String(16), default="main", nullable=False)
    history_json = db.Column(db.Text, default="[]", nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("channel", "external_id", name="uq_messaging_state"),)


class MessagingEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel = db.Column(db.String(16), nullable=False)
    event_id = db.Column(db.String(180), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("channel", "event_id", name="uq_messaging_event"),)


class ScanHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    tool = db.Column(db.String(40), nullable=False)
    target = db.Column(db.String(255), nullable=False)
    result_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MonitoredDomain(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    domain = db.Column(db.String(253), nullable=False)
    verification_token = db.Column(db.String(80), nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    last_fingerprint = db.Column(db.String(64))
    last_checked_at = db.Column(db.DateTime)
    next_check_at = db.Column(db.DateTime, index=True)
    last_status = db.Column(db.String(40), default="awaiting_verification")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "domain", name="uq_monitored_domain_user_domain"),)

class MonitoringAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    monitored_domain_id = db.Column(db.Integer, db.ForeignKey("monitored_domain.id"), nullable=False, index=True)
    domain = db.Column(db.String(253), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    detail = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default="info", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime)


class AcademyProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    lesson_slug = db.Column(db.String(80), nullable=False)
    best_score = db.Column(db.Integer, default=0, nullable=False)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "lesson_slug", name="uq_academy_progress_user_lesson"),)


class BoardPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(140), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(32), default="General", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class TutorUsage(db.Model):
    """One row per tutor question, used for the free daily tutor limit."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    day = db.Column(db.String(10), nullable=False, index=True)  # UTC YYYY-MM-DD
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class BoardReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("board_post.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class UserMemory(db.Model):
    """Per-user AI memory: what Cyber should remember about a logged-in user
    between sessions (topics asked, lessons completed, preferences they state,
    last visit). Mirrors the user_memory.py store; used when that store is
    wired to the site database. Rows per user are capped in user_memory.py."""
    __tablename__ = "user_memory"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), nullable=False, index=True)
    email = db.Column(db.String(255), default="", nullable=False)
    kind = db.Column(db.String(20), default="fact", nullable=False)
    summary = db.Column(db.Text, nullable=False)
    topic = db.Column(db.String(200), default="")
    persona = db.Column(db.String(20), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

DOMAIN_RE = re.compile(r"(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")


def normalize_domain(value):
    """Strict public-domain validation. Anything that is not exactly one
    valid domain name (no scheme, no '@', no leading/trailing punctuation,
    no internal spaces or shell metacharacters) is rejected early so scan
    tools never receive hostile input such as 'x.com; rm -rf' or 'x.com at y'."""
    value = (value or "").strip().lower()

    if "@" in value or " " in value or "_" in value:
        raise ValueError("Enter a valid public domain name, e.g. example.com.")
    if "://" in value:
        value = urlparse(value).hostname or ""
    if not value:
        raise ValueError("Enter a valid public domain name, e.g. example.com.")
    if "@" in value or " " in value or "_" in value or ".." in value:
        raise ValueError("Enter a valid public domain name, e.g. example.com.")
    if value.startswith("."):
        raise ValueError("Enter a valid public domain name, e.g. example.com.")
    value = value.split("/")[0].split(":")[0].strip(".")

    if not value or len(value) > 253 or not DOMAIN_RE.fullmatch(value):
        raise ValueError("Enter a valid public domain name, e.g. example.com.")
    return value


def refresh_subscription(user):
    """Downgrade expired paid plans before checking access or showing the dashboard.

    Flask-Login's AnonymousUserMixin is truthy, but it has no subscription
    attributes. Messaging webhooks run outside a logged-in browser session.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return
    if user.plan != "free" and user.plan_expires_at:
        expiry = user.plan_expires_at
        if expiry <= datetime.utcnow():
            user.plan = "free"
            user.plan_expires_at = None
            db.session.commit()

def activate_subscription(user, payment):
    """Start a fresh 30-day term only after server-side payment verification."""
    now = datetime.utcnow()
    if payment.plan == "tutor_pro":
        # Add-on: do not overwrite the main plan (PRO / PRO PLUS / free).
        user.tutor_pro_expires_at = now + timedelta(days=30)
        payment.status = "success"
        payment.verified_at = now
        payment.expires_at = user.tutor_pro_expires_at
        db.session.commit()
        return
    user.plan = payment.plan
    user.plan_expires_at = now + timedelta(days=30)
    payment.status = "success"
    payment.verified_at = now
    payment.expires_at = user.plan_expires_at
    db.session.commit()


def tutor_pro_active(user=None):
    """True only while a verified Tutor Pro add-on is unexpired."""
    user = current_user if user is None else user
    # AnonymousUserMixin is truthy; never treat it as a real account.
    if not user or not getattr(user, "is_authenticated", False):
        return False
    refresh_subscription(user)
    expiry = getattr(user, "tutor_pro_expires_at", None)
    if expiry and expiry <= datetime.utcnow():
        user.tutor_pro_expires_at = None
        db.session.commit()
        return False
    return bool(expiry)


def tutor_usage_today(user=None):
    user = current_user if user is None else user
    if not user or getattr(user, "id", None) is None:
        return 0
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return TutorUsage.query.filter_by(user_id=user.id, day=today).count()


def tutor_remaining(user=None):
    if tutor_pro_active(user):
        return None  # unlimited
    return max(0, TUTOR_FREE_DAILY_LIMIT - tutor_usage_today(user))


def record_tutor_use(user=None):
    user = current_user if user is None else user
    if not user or getattr(user, "id", None) is None:
        return
    db.session.add(TutorUsage(user_id=user.id, day=datetime.utcnow().strftime("%Y-%m-%d")))
    db.session.commit()

def allowed_tool(tool):
    refresh_subscription(current_user)
    rank = PLANS.get(current_user.plan, PLANS["free"])["rank"]
    if tool in PRO_TOOLS and rank < 1: return False
    if tool in PLUS_TOOLS and rank < 2: return False
    return True

def plan_rank(user=None):
    user = user if user is not None else current_user
    refresh_subscription(user)
    return PLANS.get(getattr(user, "plan", "free") or "free", PLANS["free"])["rank"]

def course_locked(course, user=None):
    return plan_rank(user) < int(course.get("plan", 0))

def require_tool(tool):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if not allowed_tool(tool):
                flash("This tool requires " + ("PRO PLUS" if tool in PLUS_TOOLS else "PRO") + ". Choose a plan below.", "warning")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def save_scan(tool, target, result):
    db.session.add(ScanHistory(user_id=current_user.id, tool=tool, target=target, result_json=json.dumps(result, default=str)))
    db.session.commit()

def dns_records(domain, record):
    try:
        answers = dns.resolver.resolve(domain, record, lifetime=4)
        return [str(x) for x in answers]
    except Exception:
        return []

def public_domain_addresses(domain):
    """Resolve a target and reject private, loopback, link-local and reserved IPs."""
    try:
        infos = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
        addresses = sorted({item[4][0] for item in infos})
    except socket.gaierror:
        addresses = []
    if not addresses:
        raise ValueError("The domain did not resolve to a public IP address.")
    parsed = [ipaddress.ip_address(x) for x in addresses]
    if any(not ip.is_global for ip in parsed):
        raise ValueError("This target resolves to a non-public IP. Private and internal network targets are blocked.")
    return addresses

def fetch_site(domain):
    addresses = public_domain_addresses(domain)
    response = requests.get("https://" + domain, timeout=8, allow_redirects=True,
        headers={"User-Agent":"CyberLord-Domain-Intelligence/3.0"}, stream=True)
    # Do not follow a redirect to a private/internal host.
    final_host = urlparse(response.url).hostname or ""
    if final_host and final_host != domain:
        public_domain_addresses(final_host)
    body = response.raw.read(250000, decode_content=True).decode(response.encoding or "utf-8", errors="replace")
    return response, body, addresses

def tls_details(domain):
    ctx = ssl.create_default_context()
    with socket.create_connection((domain, 443), timeout=6) as raw:
        with ctx.wrap_socket(raw, server_hostname=domain) as tls:
            cert = tls.getpeercert()
            expiry = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            sans = [value for kind, value in cert.get("subjectAltName", []) if kind == "DNS"]
            return {"status":"verified", "protocol":tls.version(), "cipher":tls.cipher()[0] if tls.cipher() else None,
                "subject":cert.get("subject"), "issuer":cert.get("issuer"), "not_before":cert.get("notBefore"),
                "not_after":cert.get("notAfter"), "days_until_expiry":(expiry-datetime.now(timezone.utc)).days,
                "subject_alt_names":sans[:30]}

def http_security(domain):
    response, body, addresses = fetch_site(domain)
    headers = {k.lower():v for k,v in response.headers.items()}
    wanted = ["strict-transport-security","content-security-policy","x-content-type-options","x-frame-options","referrer-policy","permissions-policy","cross-origin-opener-policy","cross-origin-resource-policy"]
    cookie_findings=[]
    for cookie in response.cookies:
        raw = response.headers.get("Set-Cookie", "")
        cookie_findings.append({"name":cookie.name,"secure":"secure" in raw.lower(),"httponly":"httponly" in raw.lower(),"samesite":"samesite" in raw.lower()})
    findings=[]
    for key in wanted:
        if not headers.get(key):
            severity = "medium" if key in ("strict-transport-security","content-security-policy","x-content-type-options") else "low"
            findings.append({"severity":severity,"title":"Missing HTTP security header: "+key,"detail":"The final HTTPS response did not include this header.","evidence":None,"fix":"Configure an appropriate value at the web server, reverse proxy or application layer."})
    for item in cookie_findings:
        if not item["secure"] or not item["httponly"]:
            findings.append({"severity":"low","title":"Cookie security attributes need review","detail":"Cookie %s is missing Secure or HttpOnly."%item['name'],"fix":"Set Secure, HttpOnly and an appropriate SameSite attribute where compatible."})
    return {"status":response.status_code,"final_url":response.url,"resolved_addresses":addresses,
        "headers":{k:headers.get(k) for k in wanted},"server_header":headers.get("server"),
        "powered_by_header":headers.get("x-powered-by"),"cookies":cookie_findings,
        "content_type":headers.get("content-type"),"content_length":headers.get("content-length"),
        "findings":findings,"html_sample_length":len(body)}

def scan_domain(domain):
    result = {"target":domain,"checked_at":datetime.now(timezone.utc).isoformat(),"findings":[],"evidence":{}}
    public_domain_addresses(domain)
    for record in ["A","AAAA","MX","NS","TXT","CAA","SOA"]:
        result["evidence"][record] = dns_records(domain, record)
    if not result["evidence"]["A"] and not result["evidence"]["AAAA"]:
        result["findings"].append({"severity":"high","title":"No address record returned","detail":"No A or AAAA record was resolved during this check.","fix":"Confirm DNS hosting and publish the intended address record."})
    try:
        result["evidence"]["tls"] = tls_details(domain)
        if result["evidence"]["tls"].get("days_until_expiry",999) < 21:
            result["findings"].append({"severity":"high","title":"TLS certificate expires soon","detail":"The certificate has fewer than 21 days remaining.","fix":"Renew and deploy the certificate before expiry."})
    except Exception as e:
        result["evidence"]["tls"] = {"status":"not_verified","reason":str(e)[:180]}
        result["findings"].append({"severity":"medium","title":"HTTPS certificate could not be verified","detail":"A TLS connection could not be established from this scanner.","fix":"Check HTTPS listener, certificate chain, hostname and firewall rules."})
    try:
        result["evidence"]["http"] = http_security(domain)
        result["findings"].extend(result["evidence"]["http"].pop("findings", []))
    except Exception as e:
        result["evidence"]["http"] = {"status":"unavailable","reason":str(e)[:180]}
    result["coverage_note"] = "Expanded DNS, TLS and HTTP configuration review. This is non-exploitative external assessment, not a penetration test; results are limited to publicly observable evidence."
    return result

COMMON_SUBDOMAINS = "www mail webmail smtp imap pop ftp api app admin portal vpn remote login auth sso dev test staging stage beta demo old new shop store blog forum support help docs cdn static assets media img images files download status git gitlab github ci jenkins build m api2 ns1 ns2 mx1 mx2 autodiscover autoconfig mta selector1 selector2".split()

def scan_subdomains(domain):
    rows=[]
    for prefix in COMMON_SUBDOMAINS:
        host=f"{prefix}.{domain}"
        a=dns_records(host,"A"); aaaa=dns_records(host,"AAAA"); cname=dns_records(host,"CNAME")
        if a or aaaa or cname:
            rows.append({"host":host,"A":a,"AAAA":aaaa,"CNAME":cname})
    return {"target":domain,"count":len(rows),"discovered":rows,"method":"DNS resolution of a curated common-name list","note":"This is not exhaustive and does not attempt zone transfers or brute-force wordlists."}

def email_posture(domain):
    mx=dns_records(domain,"MX"); txt=dns_records(domain,"TXT"); dmarc=dns_records("_dmarc."+domain,"TXT")
    spf=[x for x in txt if "v=spf1" in x.lower()]
    policy="none"
    if dmarc:
        m=re.search(r"(?:^|;)\s*p\s*=\s*(none|quarantine|reject)",";".join(dmarc),re.I)
        if m: policy=m.group(1).lower()
    findings=[]
    if not mx: findings.append({"severity":"medium","title":"No MX record found","detail":"No mail exchanger was returned for this domain.","fix":"Publish the correct MX records if the domain receives email."})
    if not spf: findings.append({"severity":"medium","title":"SPF record not found","detail":"No TXT record containing v=spf1 was found at the root domain.","fix":"Publish one SPF policy covering all legitimate senders; avoid multiple SPF records."})
    if not dmarc: findings.append({"severity":"medium","title":"DMARC record not found","detail":"No _dmarc TXT record was returned.","fix":"Publish a DMARC policy and begin with monitored reporting before enforcement."})
    elif policy=="none": findings.append({"severity":"low","title":"DMARC policy is monitoring-only","detail":"The DMARC policy is p=none.","fix":"After reviewing aggregate reports and legitimate senders, consider moving to quarantine or reject."})
    return {"target":domain,"mx":mx,"spf":spf,"root_txt":txt,"dmarc":dmarc,"dmarc_policy":policy,"findings":findings,
        "dkim_selectors_checked":{sel:dns_records(sel+"._domainkey."+domain,"TXT") for sel in ["default","google","selector1","selector2","s1","s2"]},
        "note":"DNS-based email posture only. It cannot prove mailbox existence, sender identity or actual delivery."}

# ---------------------------------------------------------------------------
# Email exposure check (public, free tier) — Hudson Rock infostealer intel
#
# Source decision (verified 2026-11-14): Hudson Rock's free "Cavalier" email
# endpoint at
#   https://www.hudsonrock.com/api/json/v2/stats/website-results/email?email=...
# is keyless, needs no account and no API key. It backs the public checker on
# hudsonrock.com and returns JSON. It reports whether the email appears in
# infostealer (malware) credential dumps, i.e. a computer infected by an
# infostealer had this email's saved credentials. It does NOT list named
# breaches (unlike HIBP, which requires a paid API key and is therefore not
# used). Free alternatives checked and rejected: XposedOrNot's API
# (api.xposedornot.com) aggressively rate-limits automated callers — 429
# "Request dropped / scanning_protection" even on the public breaches list —
# so it cannot serve a production lookup; breach.directory / cib.db.rip
# were also unreachable from our network.
#
# The lookup is pluggable via check_email_exposure(): only this one function
# talks to the sources, so a future keyed provider (e.g. HIBP) can be swapped
# in without touching routes or templates. The function NEVER raises: any
# failure is reported as status "source_unavailable" and the UI says so
# plainly instead of showing fake or empty results.
# ---------------------------------------------------------------------------

HUDSON_ROCK_EMAIL_URL = "https://www.hudsonrock.com/api/json/v2/stats/website-results/email"
# Second keyless endpoint on Cavalier's own host, tried as fallback if the
# main hudsonrock.com host fails (both return the same JSON shape).
HUDSON_ROCK_FALLBACK_URL = "https://cavalier.hudsonrock.com/api/json/v2/stats/website-results/email"


def _hudson_rock_email_check(email):
    """Keyless infostealer-exposure lookup. Returns a normalised dict."""
    out = {"source": "Hudson Rock infostealer intelligence (free, no key required)",
           "status": "source_unavailable", "found": False,
           "date_compromised": None, "computer_name": None,
           "total_user_services": 0, "total_corporate_services": 0,
           "provider_url": "https://www.hudsonrock.com/free-tools"}
    last_exc = None
    for url in (HUDSON_ROCK_EMAIL_URL, HUDSON_ROCK_FALLBACK_URL):
        try:
            r = requests.get(url, params={"email": email},
                             headers={"User-Agent": "CyberLord-Email-Check/1.0", "Accept": "application/json"},
                             timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            last_exc = exc
            continue
        if not isinstance(data, dict):
            out["reason"] = "The exposure source returned an unexpected response."
            return out
        out["status"] = "ok"
        out["computer_name"] = data.get("computer_name")
        out["date_compromised"] = data.get("date_compromised")
        out["total_user_services"] = int(data.get("total_user_services") or 0)
        out["total_corporate_services"] = int(data.get("total_corporate_services") or 0)
        out["found"] = bool(out["date_compromised"] or out["total_user_services"] or out["total_corporate_services"])
        if data.get("message"):
            out["provider_message"] = data.get("message")
        return out
    out["reason"] = "The exposure source could not be reached just now (" + str(last_exc)[:140] + ")."
    return out


def check_email_exposure(email):
    """Pluggable breach-source entry point. No fake data: if the source fails,
    status is 'source_unavailable' and callers must say so."""
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return {"email": email, "status": "invalid", "found": False,
                "reason": "Enter a valid email address."}
    result = _hudson_rock_email_check(email)
    result["email"] = email
    result["checked_at"] = datetime.now(timezone.utc).isoformat()
    result["scope_note"] = ("This checks public infostealer-compromise intelligence only. "
                            "It is not a full breach database: an email not listed here may "
                            "still appear in a breach this source does not cover. A listing "
                            "means credentials tied to this email were recovered from an "
                            "infected computer; change those passwords from a clean device.")
    return result


def technology_fingerprint(domain):
    response, body, addresses=fetch_site(domain)
    headers={k.lower():v for k,v in response.headers.items()}
    technologies=[]
    patterns=[("WordPress",r"wp-content|wp-includes"),("Drupal",r"/sites/(?:default|all)/files"),("Joomla",r"/media/system/js/"),("React",r"react(?:\.production)?\.min\.js|__react"),("Next.js",r"/_next/static/"),("Nuxt",r"__nuxt"),("Laravel",r"laravel_session"),("Shopify",r"cdn\.shopify\.com"),("Cloudflare",r"cloudflare"),("Bootstrap",r"bootstrap(?:\.min)?\.css")]
    for name,pattern in patterns:
        if re.search(pattern,body+" "+str(response.headers),re.I): technologies.append(name)
    generator=re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)',body,re.I)
    scripts=re.findall(r'<script[^>]+src=["\']([^"\']+)',body,re.I)[:25]
    styles=re.findall(r'<link[^>]+href=["\']([^"\']+\.css[^"\']*)',body,re.I)[:25]
    return {"target":domain,"http_status":response.status_code,"resolved_addresses":addresses,"detected_hints":sorted(set(technologies)),
        "generator_meta":generator.group(1) if generator else None,"server":headers.get("server"),"x_powered_by":headers.get("x-powered-by"),
        "cookies":list(response.cookies.keys()),"script_paths":scripts,"stylesheet_paths":styles,
        "confidence_note":"Technology hints are heuristic and may be incomplete or spoofed. They are not verified software versions and must not be treated as CVE proof."}

def ip_intelligence(value):
    ip=ipaddress.ip_address(value)
    if not ip.is_global: raise ValueError("Only public IP addresses can be queried.")
    try: ptr, _aliases, _names = socket.gethostbyaddr(str(ip))
    except Exception: ptr, _names = None, []
    # Named reverse loses the source order when there is no PTR; report the
    # full name list only when the lookup actually succeeded.
    return {"ip":str(ip),"version":ip.version,"is_global":ip.is_global,"reverse_dns":ptr,
        "reverse_dns_names":list(_names)[:10] if ptr else [],
        "rdap_url":"https://rdap.org/ip/"+str(ip),"note":"RDAP link points to registration data; allocation data does not identify a device owner or prove malicious activity."}


# ---------------------------------------------------------------------------
# Deep Scan: passive public OSINT only (no intrusive scanning).
# Keyless sources: RDAP (rdap.org), crt.sh JSON API, Internet Archive Wayback
# availability API, and public DNS. No API keys required for these endpoints.
# Anything that would need a key (e.g. a breach-intelligence provider) is
# intentionally not implemented here; the breach tool already reports
# provider status honestly.
# ---------------------------------------------------------------------------

def _rdap_whois(domain):
    """Registration data via RDAP, keyless. Returns parsed summary.
    Honest degradation: any transport or parse failure returns
    status 'not_available' with the reason, never a guessed value."""
    out = {"source": "RDAP (rdap.org)", "status": "not_available", "registrar": None,
           "registrar_handle": None,
           "created": None, "expires": None, "updated": None, "status_flags": [],
           "name_servers": [], "registrant_country": None, "registrar_country": None,
           "note": "(parsed from public RDAP record; empty fields mean not published)"}
    data = None
    last_exc = None
    for attempt in range(3):
        try:
            r = requests.get("https://rdap.org/domain/" + domain,
                             headers={"Accept": "application/json", "User-Agent": "CyberLord-Deep-Scan/1.0"},
                             timeout=12)
            if r.status_code == 404:
                out["status"] = "no_rdap_record"
                return out
            r.raise_for_status()
            data = r.json()
            break
        except Exception as exc:
            last_exc = exc
            if r is not None and getattr(r, "status_code", None) in (400, 403, 410):
                break
            if attempt < 2:
                time.sleep(1 + attempt)
    if data is None:
        out["reason"] = str(last_exc)[:180] if last_exc else "RDAP request failed"
        return out
    out["status"] = "ok"
    out["status_flags"] = data.get("status", []) or []
    out["name_servers"] = [ns.get("ldhName") for ns in (data.get("nameservers") or []) if ns.get("ldhName")][:15]
    for ev in data.get("events", []) or []:
        name = (ev.get("eventAction") or "").lower()
        date = ev.get("eventDate")
        if name == "registration" and date: out["created"] = date
        elif name == "expiration" and date: out["expires"] = date
        elif name in ("last update of rdap database", "last changed", "updated") and date: out["updated"] = date
    for ent in data.get("entities", []) or []:
        roles = [str(x).lower() for x in (ent.get("roles") or [])]
        vcard = ent.get("vcardArray")
        country = None
        fn = None
        if isinstance(vcard, list) and len(vcard) > 1:
            for item in vcard[1] or []:
                try:
                    if item[0] == "fn" and item[3]:
                        fn = item[3]
                    if item[0] == "adr" and isinstance(item[3], list) and item[3]:
                        country = item[3][-1] or None
                except Exception:
                    continue
        if "registrar" in roles:
            out["registrar"] = fn or ent.get("handle") or None
            out["registrar_handle"] = ent.get("handle") or None
            out["registrar_country"] = country
        if "registrant" in roles and country:
            out["registrant_country"] = country
    return out

def _ct_history(domain):
    """Certificate Transparency history + subdomain enumeration via crt.sh (keyless).
    crt.sh is rate-limited and frequently times out: retry up to 3 times with
    backoff, then report status 'not_available' honestly. A domain with no CT
    entries is reported as total_entries=0, never as an invented list."""
    out = {"source": "crt.sh Certificate Transparency", "status": "not_available",
           "total_entries": 0, "subdomains": [], "subdomain_count": 0,
           "earliest_seen": None, "latest_seen": None,
           "issuers": [], "note": "CT logs are public; absence of entries does not prove a certificate never existed."}
    rows = None
    last_exc = None
    for attempt in range(3):
        try:
            r = requests.get("https://crt.sh/", params={"q": "%." + domain, "output": "json"},
                             headers={"User-Agent": "CyberLord-Deep-Scan/1.0"}, timeout=25)
            r.raise_for_status()
            parsed = r.json()
            if not isinstance(parsed, list):
                out["status"] = "unexpected_response"
                return out
            rows = parsed
            break
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2 + attempt * 3)
    if rows is None:
        out["reason"] = ("crt.sh unavailable after 3 attempts: " +
                         (str(last_exc)[:150] if last_exc else "request failed"))
        return out
    out["status"] = "ok"
    out["total_entries"] = len(rows)
    subs, issuers, dates = set(), set(), []
    for row in rows:
        if not isinstance(row, dict): continue
        for name in str(row.get("name_value", "")).splitlines():
            name = name.strip().lower().lstrip("*.")
            if name and (name == domain or name.endswith("." + domain)):
                subs.add(name)
        if row.get("issuer_name"): issuers.add(str(row["issuer_name"])[:120])
        if row.get("not_before"): dates.append(str(row["not_before"])[:10])
    out["subdomains"] = sorted(subs)[:500]
    out["subdomain_count"] = len(subs)
    out["issuers"] = sorted(issuers)[:25]
    if dates:
        out["earliest_seen"] = min(dates); out["latest_seen"] = max(dates)
    return out

def _deeper_dns(domain):
    """Deeper DNS: MX/NS/TXT/CAA/SOA plus DMARC, SPF split, DKIM common selectors, DNSSEC.
    DKIM found sets are the UNION of all TXT records per selector, so long keys
    split across multiple strings are never truncated or lost."""
    records = {kind: dns_records(domain, kind) for kind in ("MX", "NS", "TXT", "CAA", "SOA", "DNSKEY", "DS")}
    txt = records["TXT"]
    spf = [x for x in txt if "v=spf1" in x.lower()]
    dmarc = dns_records("_dmarc." + domain, "TXT")
    dmarc_policy = None
    if dmarc:
        m = re.search(r"(?:^|;)\s*p\s*=\s*(none|quarantine|reject)", ";".join(dmarc), re.I)
        if m: dmarc_policy = m.group(1).lower()
    dkim_found = {}
    for sel in ("default", "google", "selector1", "selector2", "s1", "s2", "k1", "dkim"):
        vals = dns_records(sel + "._domainkey." + domain, "TXT")
        if vals:
            dkim_found[sel] = [" ".join(vals)]
    soa = records["SOA"]
    findings = []
    if not records["CAA"]:
        findings.append({"severity": "low", "title": "No CAA record", "detail": "No Certificate Authority Authorization record was returned; any CA may issue certificates for this domain.", "fix": "Publish a CAA record listing authorised CAs."})
    if not records["DNSKEY"] and not records["DS"]:
        findings.append({"severity": "low", "title": "No DNSSEC records observed", "detail": "No DNSKEY or DS record was returned at the apex.", "fix": "If your registrar supports it, sign the zone with DNSSEC."})
    return {"records": records, "spf": spf, "dmarc": dmarc, "dmarc_policy": dmarc_policy,
            "dkim_selectors_found": dkim_found,
            "dkim_selectors_checked": ["default", "google", "selector1", "selector2", "s1", "s2", "k1", "dkim"],
            "dnssec_present": bool(records["DNSKEY"] or records["DS"]),
            "soa": soa, "findings": findings,
            "note": "DKIM uses common public selectors only; unknown selectors will not be found. DNS responses reflect the resolver used by this service."}

def _http_security_report(domain):
    """One polite GET: expanded security-header posture with per-header grades."""
    try:
        response, body, addresses = fetch_site(domain)
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)[:180]}
    headers = {k.lower(): v for k, v in response.headers.items()}
    checks = {
        "strict-transport-security": ("HSTS", "medium"),
        "content-security-policy": ("Content-Security-Policy", "medium"),
        "x-frame-options": ("X-Frame-Options / frame-ancestors", "low"),
        "x-content-type-options": ("X-Content-Type-Options", "medium"),
        "referrer-policy": ("Referrer-Policy", "low"),
        "permissions-policy": ("Permissions-Policy", "low"),
        "cross-origin-opener-policy": ("Cross-Origin-Opener-Policy", "low"),
        "cross-origin-resource-policy": ("Cross-Origin-Resource-Policy", "low"),
        "cross-origin-embedder-policy": ("Cross-Origin-Embedder-Policy", "low"),
        "origin-agent-cluster": ("Origin-Agent-Cluster", "info"),
        "x-permitted-cross-domain-policies": ("X-Permitted-Cross-Domain-Policies", "info"),
    }
    report, present = {}, 0
    for key, (label, sev) in checks.items():
        value = headers.get(key)
        # CSP frame-ancestors also satisfies clickjacking protection.
        if key == "x-frame-options" and not value and "frame-ancestors" in (headers.get("content-security-policy") or "").lower():
            value = "via CSP frame-ancestors"
        report[label] = {"present": bool(value), "value": value}
        if value: present += 1
    findings = []
    for key, (label, sev) in checks.items():
        if not report[label]["present"] and sev in ("medium", "low"):
            findings.append({"severity": sev, "title": "Missing header: " + label,
                             "detail": "The final HTTPS response did not include " + label + ".",
                             "fix": "Configure the header at the web server, reverse proxy or application layer."})
    # HSTS quality note
    hsts = headers.get("strict-transport-security", "")
    hsts_note = None
    if hsts:
        hsts_note = ("includes includeSubDomains and preload" if "includesubdomains" in hsts.replace(" ", "").lower() and "preload" in hsts.lower()
                     else "present (check max-age >= 31536000 and includeSubDomains for full strength)")
    return {"status": response.status_code, "final_url": response.url, "resolved_addresses": addresses,
            "server": headers.get("server"), "x_powered_by": headers.get("x-powered-by"),
            "headers": report, "present_count": present, "total_checked": len(checks),
            "hsts_note": hsts_note, "findings": findings,
            "note": "Based on one GET request to the site root (redirects followed to HTTPS only). Headers may vary by path."}

DEEP_TECH_PATTERNS = [
    ("WordPress", r"wp-content|wp-includes|wp-json"), ("Drupal", r"/sites/(?:default|all)/files|drupal"),
    ("Joomla", r"/media/system/js/|joomla"), ("React", r"react(?:\.production)?\.min\.js|__react"), ("Next.js", r"/_next/static/"),
    ("Nuxt", r"__nuxt"), ("Vue.js", r"vue(?:\.runtime)?(?:\.global)?\.js|__vue"), ("Angular", r"ng-version|angular"),
    ("Svelte", r"svelte"), ("Laravel", r"(?:^|[\s\"'.,;])(?:laravel_session|XSRF-TOKEN)(?:[\s\"'.,;]|$)"), ("Django", r"(?:^|[\s\"'.,;])(?:csrftoken|django)(?:[\s\"'.,;]|$)"),
    ("Ruby on Rails", r"csrf-param|rails-ujs"), ("ASP.NET", r"__viewstate|x-aspnet-version"), ("PHP", r"phpsessid|phpversion"),
    ("Shopify", r"cdn\.shopify\.com|Shopify\.theme"), ("WooCommerce", r"woocommerce"), ("Magento", r"(?:^|[\s\"'`<>=/])mage/(?:js|version)|mage\.js|magento|mage_init"),
    ("Cloudflare", r"cloudflare|__cf_bm|cf-ray"), ("AWS / Amazon", r"server:.*(awselb|amazon)|x-amz-"),
    ("Google Analytics", r"googletagmanager|google-analytics|gtag\("), ("Google Tag Manager", r"googletagmanager\.com/gtm"),
    ("Facebook Pixel", r"fbevents\.js|connect\.facebook\.net"), ("Bootstrap", r"bootstrap(?:\.min)?\.css"),
    ("jQuery", r"jquery(?:\.min)?\.js"), ("Tailwind CSS", r"tailwind(?:css)?"), ("Font Awesome", r"font-?awesome"),
    ("reCAPTCHA", r"recaptcha"), ("Stripe", r"js\.stripe\.com|stripe\.js"), ("PayPal", r"paypal"),
    ("Mailchimp", r"mailchimp"), ("Intercom", r"widget\.intercom\.io|intercomApp|Intercom\(|api\.intercom\.io"), ("Hotjar", r"hotjar"),
    ("New Relic", r"newrelic|nr-spa"), ("Datadog", r"datadog"), ("Sentry", r"sentry"),
    ("Vercel", r"x-vercel|vercel"), ("Netlify", r"x-nf-request-id|netlify"), ("Heroku", r"x-heroku|herokuapp"),
    ("Nginx", r"(?:^|[\s\"'.,;])(?:nginx|openresty)(?:[\s\"'.,;]|$)"), ("Apache", r"(?:^|[\s\"'.,;])(?:apache|httpd)(?:[\s\"'.,;]|$)"), ("LiteSpeed", r"litespeed"),
    ("openresty", r"openresty"), ("IIS", r"microsoft-iis"), ("Express (Node)", r"x-powered-by:\s*express"),
]

def _deep_technology(domain):
    """Expanded tech detection from response headers, cookies and page source of one GET."""
    try:
        response, body, addresses = fetch_site(domain)
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)[:180]}
    headers = {k.lower(): v for k, v in response.headers.items()}
    haystack = body + " " + str(dict(response.headers)) + " " + " ".join(response.cookies.keys())
    detected = []
    for name, pattern in DEEP_TECH_PATTERNS:
        if re.search(pattern, haystack, re.I):
            detected.append(name)
    generator = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', body, re.I)
    if generator and generator.group(1) not in detected:
        detected.append("Generator tag: " + generator.group(1)[:80])
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', body, re.I)[:40]
    styles = re.findall(r'<link[^>]+href=["\']([^"\']+\.css[^"\']*)', body, re.I)[:40]
    js_libs = sorted(set(re.findall(r'(?:src|href)=["\'][^"\']*?(jquery|bootstrap|react|vue|angular|tailwind|font-?awesome)[^"\']*', body, re.I)))[:20]
    cookie_names = sorted(response.cookies.keys())[:30]
    return {"target": domain, "http_status": response.status_code, "resolved_addresses": addresses,
            "detected_hints": sorted(set(detected)), "detected_count": len(set(detected)),
            "generator_meta": generator.group(1) if generator else None,
            "server": headers.get("server"), "x_powered_by": headers.get("x-powered-by"),
            "via": headers.get("via"), "cookies": cookie_names,
            "script_paths": scripts, "stylesheet_paths": styles, "common_js_libs": js_libs,
            "confidence_note": "Heuristic fingerprints from headers, cookies and page source. They may be incomplete, outdated or spoofed; confirm versions from your own asset inventory before acting."}

def _wayback_check(domain):
    """Wayback Machine availability lookup (keyless Archive.org API)."""
    out = {"source": "Internet Archive Wayback Machine", "status": "not_available",
           "available": False, "closest_snapshot": None, "url": "https://archive.org/wayback/available?url=" + domain}
    try:
        r = requests.get("https://archive.org/wayback/available", params={"url": domain},
                         headers={"User-Agent": "CyberLord-Deep-Scan/1.0"}, timeout=12)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        out["reason"] = str(exc)[:180]
        return out
    snap = data.get("archived_snapshots", {}).get("closest") if isinstance(data, dict) else None
    out["status"] = "ok"
    out["available"] = bool(snap)
    if snap:
        out["closest_snapshot"] = {"timestamp": snap.get("timestamp"), "url": snap.get("url"), "status": snap.get("status")}
    out["note"] = "The availability API returns the closest capture; it is not a full history listing. Full history lives in the Wayback CDX index."
    return out

def deep_scan(domain):
    """Deep Scan orchestrator. Every section is passive and independently
    failure-tolerant: one source failing never blocks the others."""
    public_domain_addresses(domain)  # enforces the public-IP safety rule up front
    sections = {}
    try:
        sections["registration"] = _rdap_whois(domain)
    except Exception as exc:
        sections["registration"] = {"status": "error", "reason": str(exc)[:180]}
    try:
        sections["certificate_transparency"] = _ct_history(domain)
    except Exception as exc:
        sections["certificate_transparency"] = {"status": "error", "reason": str(exc)[:180]}
    try:
        sections["dns_deep"] = _deeper_dns(domain)
    except Exception as exc:
        sections["dns_deep"] = {"status": "error", "reason": str(exc)[:180]}
    try:
        sections["http_security"] = _http_security_report(domain)
    except Exception as exc:
        sections["http_security"] = {"status": "error", "reason": str(exc)[:180]}
    try:
        sections["technology"] = _deep_technology(domain)
    except Exception as exc:
        sections["technology"] = {"status": "error", "reason": str(exc)[:180]}
    try:
        sections["archive"] = _wayback_check(domain)
    except Exception as exc:
        sections["archive"] = {"status": "error", "reason": str(exc)[:180]}
    findings = []
    for key, section in sections.items():
        if isinstance(section, dict):
            for item in section.get("findings", []) or []:
                item = dict(item); item["section"] = key; findings.append(item)
    return {"target": domain, "tool": "deep_scan", "checked_at": datetime.now(timezone.utc).isoformat(),
            "sections": sections, "findings": findings,
            "scope_note": "Deep Scan uses only public, passive OSINT sources (RDAP, Certificate Transparency, public DNS, one polite HTTPS GET, Wayback availability API). No intrusive scanning, port probing, authentication attempts or brute force is performed. Results depend on third-party data availability and may be incomplete."}

def kali_worker_scan(domain, modules):
    base=os.getenv("KALI_WORKER_URL","").rstrip("/"); token=os.getenv("KALI_WORKER_TOKEN","")
    if not base or not token: return {"available":False,"message":"Kali scan worker is not connected. Configure KALI_WORKER_URL and KALI_WORKER_TOKEN after deploying the isolated Kali worker."}
    r=requests.post(base+"/scan",json={"target":domain,"modules":modules,"authorization_confirmed":True},headers={"Authorization":"Bearer "+token},timeout=180)
    r.raise_for_status()
    return r.json()

def kali_worker_phone_intel(phone_number):
    """Request passive numbering-plan enrichment from the separately hosted worker."""
    base=os.getenv("KALI_WORKER_URL","").rstrip("/"); token=os.getenv("KALI_WORKER_TOKEN","")
    if not base or not token:
        return {"available":False,"message":"Kali worker is not connected. Local numbering-plan information is still shown; connect the worker to enable this additional enrichment."}
    r=requests.post(base+"/phone-intel",json={"phone":phone_number,"default_region":"NG"},
        headers={"Authorization":"Bearer "+token},timeout=20)
    r.raise_for_status()
    return r.json()

@app.route("/")
def index():
    try:
        from reviews import get_store as _review_store
        review_summary = _review_store().public_summary(limit=6)
    except Exception:
        review_summary = {"average_rating": 0.0, "review_count": 0, "reviews": []}
    return render_template("index.html", review_summary=review_summary)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/pricing")
def pricing():
    return render_template("pricing.html")

SEO_PUBLIC_PAGES = [
    ("index", "https://cyberlord.name.ng/", "1.0", "daily"),
    ("about", "https://cyberlord.name.ng/about", "0.8", "monthly"),
    ("pricing", "https://cyberlord.name.ng/pricing", "0.8", "monthly"),
    ("faq", "https://cyberlord.name.ng/faq", "0.9", "weekly"),
    ("guide_email_compromised", "https://cyberlord.name.ng/guides/check-if-email-is-compromised", "0.9", "weekly"),
    ("guide_website_security", "https://cyberlord.name.ng/guides/website-security-check", "0.9", "weekly"),
    ("guide_spf_dmarc", "https://cyberlord.name.ng/guides/spf-dmarc-setup", "0.9", "weekly"),
    ("privacy", "https://cyberlord.name.ng/privacy", "0.5", "monthly"),
    ("terms", "https://cyberlord.name.ng/terms", "0.5", "monthly"),
    ("refund_policy", "https://cyberlord.name.ng/refund-policy", "0.5", "monthly"),
    ("contact", "https://cyberlord.name.ng/contact", "0.6", "monthly"),
]

@app.route("/faq")
def faq():
    return render_template("faq.html")

@app.route("/guides/check-if-email-is-compromised")
def guide_email_compromised():
    return render_template("guide_email_compromised.html")

@app.route("/guides/website-security-check")
def guide_website_security():
    return render_template("guide_website_security.html")

@app.route("/guides/spf-dmarc-setup")
def guide_spf_dmarc():
    return render_template("guide_spf_dmarc.html")

@app.route("/sitemap.xml")
def sitemap():
    today = datetime.now(timezone.utc).date().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for endpoint, loc, priority, changefreq in SEO_PUBLIC_PAGES:
        lines.append(f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>")
    lines.append("</urlset>")
    return app.response_class("\n".join(lines), mimetype="application/xml")

@app.route("/googlef3dfcc0a523f9481.html")
def google_search_console_verification():
    return send_file(os.path.join(app.root_path, "googlef3dfcc0a523f9481.html"))

@app.route("/robots.txt")
def robots():
    return app.response_class("User-agent: *\nAllow: /\nDisallow: /dashboard\nDisallow: /academy\nDisallow: /admin\nDisallow: /api/\nDisallow: /scan/\nDisallow: /history/\nDisallow: /payment/\nDisallow: /monitoring\nDisallow: /advanced-intelligence\nDisallow: /security-centre\nDisallow: /interaction-board\n\nSitemap: https://cyberlord.name.ng/sitemap.xml\n", mimetype="text/plain")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")

@app.route("/refund-policy")
def refund_policy():
    return render_template("refund_policy.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/register", methods=["GET","POST"])
@rate_limit("register")
def register():
    if request.method == "POST":
        email = form_str("email", 254).lower()
        password = form_str("password", 128)
        if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(password) < 10:
            flash("Enter a valid email and a password of at least 10 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(email=email); user.set_password(password)
            db.session.add(user); db.session.commit()
            login_user(user); return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET","POST"])
@rate_limit("login")
def login():
    if request.method == "POST":
        email = form_str("email", 254).lower()
        password = form_str("password", 128)
        # Existence check and password check both land on the same path, and
        # the dummy hash burn for unknown accounts keeps both timings close,
        # so attackers cannot tell which case failed. One message for every
        # failure, plus a fixed delay, plus the per-IP limiter above which
        # locks the address out after repeated failures.
        user = User.query.filter_by(email=email).first()
        ok = bool(user) and user.check_password(password)
        if not ok and not user:
            check_password_hash("pbkdf2:sha256:600000", password)
        if ok:
            login_user(user)
            # Per-user memory: stamp this visit so Cyber can greet a
            # returning user and knows when they last came back.
            try:
                from user_memory import get_store as _mem_store
                _mem_store().touch_visit(str(user.id), user.email)
                _store = _mem_store()
                row_count = len(_store.load(str(user.id)))
                session["cyber_memory_count"] = row_count
                session["cyber_welcome_back"] = bool(row_count > 1)
            except Exception:
                pass
            return redirect(url_for("dashboard"))
        time.sleep(LOGIN_FAIL_DELAY)
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout")
@login_required
def logout():
    logout_user(); return redirect(url_for("index"))

@app.route("/forgot-password", methods=["GET","POST"])
@rate_limit("forgot")
def forgot_password():
    if request.method == "POST":
        email = form_str("email", 254).lower()

        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(user.email, salt="password-reset")
            link = url_for("reset_password", token=token, _external=True)
            api_key = os.getenv("RESEND_API_KEY")
            sender = os.getenv("RESEND_FROM")
            if api_key and sender:
                try:
                    requests.post("https://api.resend.com/emails", headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"},
                        json={"from":sender,"to":[user.email],"subject":"CyberLord password reset","html":f'<p>Use this secure link to reset your password. It expires in 30 minutes.</p><p><a href="{link}">Reset password</a></p>'}, timeout=12).raise_for_status()
                except Exception:
                    app.logger.exception("Password reset email delivery failed")
            elif app.debug:
                app.logger.warning("Development reset link: %s", link)
        flash("If the account exists and email delivery is configured, a reset link will arrive shortly.", "info")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="forgot")

@app.route("/reset-password/<token>", methods=["GET","POST"])
def reset_password(token):
    try:
        email = serializer.loads(token, salt="password-reset", max_age=1800)
    except (BadSignature, SignatureExpired):
        flash("This reset link is invalid or has expired. Request a new one.", "error")
        return redirect(url_for("forgot_password"))
    user = User.query.filter_by(email=email).first()
    if not user: return redirect(url_for("forgot_password"))
    if request.method == "POST":
        password = form_str("password", 128)
        if len(password) < 10:
            flash("Use at least 10 characters.", "error")

        else:
            user.set_password(password); db.session.commit()
            flash("Password updated. Please sign in.", "success")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="reset")

@app.route("/dashboard")
@login_required
def dashboard():
    refresh_subscription(current_user)
    history = ScanHistory.query.filter_by(user_id=current_user.id).order_by(ScanHistory.created_at.desc()).limit(50).all()
    # Per-user memory: one greeting flag the templates can use. Greeting copy
    # stays short; the AI itself gets the full memory context on each request.
    _returning = bool(session.get("cyber_welcome_back"))
    return render_template("dashboard.html", plans=PLANS, tool_names=TOOL_NAMES, pro_tools=PRO_TOOLS, plus_tools=PLUS_TOOLS, history=history, tutor_pro=tutor_pro_active(current_user), tutor_remaining=tutor_remaining(current_user), tutor_limit=TUTOR_FREE_DAILY_LIMIT, tutor_pro_expires_at=getattr(current_user, "tutor_pro_expires_at", None), tutor_pro_status=tutor_pro_active(current_user), cyber_returning=_returning)

# Academy lessons and their exercise questions now live in academy_questions.py
# (add practitioner-level questions there; see the how-to at the top of that file).
# ACADEMY_LESSONS is imported from that module above.


@app.route("/academy")
@login_required
def academy():
    progress = {p.lesson_slug: p for p in AcademyProgress.query.filter_by(user_id=current_user.id).all()}
    courses = []
    for course in ACADEMY_COURSES:
        rows = []
        for item in course_lessons(course):
            row = dict(item)
            row["progress"] = progress.get(item["slug"])
            row["done"] = bool(row["progress"] and row["progress"].completed_at)
            rows.append(row)
        done = sum(1 for r in rows if r["done"])
        total = len(rows)
        pct = int(round(done / total * 100)) if total else 0
        plan = PLANS["pro" if int(course.get("plan", 0)) == 1 else "pro_plus" if int(course.get("plan", 0)) == 2 else "free"]
        courses.append({
            "course": course, "lessons": rows, "done": done, "total": total, "pct": pct,
            "locked": course_locked(course), "plan": plan,
        })
    total_done = sum(c["done"] for c in courses)
    total_all = sum(c["total"] for c in courses)
    completed_rows = [p for p in progress.values() if p.completed_at]
    xp_points = (len(completed_rows) * 100) + sum(max(0, min(100, int(p.best_score or 0))) // 10 * 2 for p in progress.values())
    badges = []
    if total_done >= 1: badges.append({"icon":"⚡","name":"First Steps","detail":"Completed your first lesson"})
    if total_done >= 5: badges.append({"icon":"🧭","name":"Path Finder","detail":"Completed five lessons"})
    if total_done >= 10: badges.append({"icon":"🛡️","name":"Security Learner","detail":"Completed ten lessons"})
    if any((p.best_score or 0) == 100 for p in completed_rows): badges.append({"icon":"🎯","name":"Perfect Score","detail":"Earned 100% on a lesson"})
    return render_template("academy.html", courses=courses, completed=total_done, total=total_all,
                           xp_points=xp_points, badges=badges)

@app.route("/academy/<slug>", methods=["GET", "POST"])
@login_required
def academy_lesson(slug):
    lesson = next((x for x in ACADEMY_LESSONS if x["slug"] == slug), None)
    if not lesson:
        abort(404)
    course = get_course_for_lesson(slug)
    if course and course_locked(course):
        plan = PLANS["pro" if int(course.get("plan", 0)) == 1 else "pro_plus"]
        return render_template("academy_locked.html", lesson=lesson, course=course, plan=plan), 403
    questions = lesson.get("questions") or []
    progress = AcademyProgress.query.filter_by(user_id=current_user.id, lesson_slug=slug).first()
    result = None
    if request.method == "POST":
        answers = {}
        for i, q in enumerate(questions):
            raw = request.form.get("answer_%d" % i, "-1")
            try:
                selected = int(raw)
            except (TypeError, ValueError):
                selected = -1
            if selected not in range(len(q.get("choices") or [])):
                selected = -1
            answers[i] = selected
        correct_count = sum(1 for i, q in enumerate(questions) if answers.get(i) == q.get("answer"))
        total = len(questions) or 1
        pct = int(round(correct_count / total * 100))
        if not progress:
            progress = AcademyProgress(user_id=current_user.id, lesson_slug=slug)
            db.session.add(progress)
        progress.best_score = max(progress.best_score or 0, pct)
        if pct == 100:
            progress.completed_at = datetime.utcnow()
        db.session.commit()
        # Per-user memory: remember completed lessons so Cyber can continue
        # with the user next time without making them redo finished work.
        if pct == 100:
            try:
                from user_memory import get_store as _mem_store2, lesson_completed_summary as _lcs
                _mem_store2().save(str(current_user.id), current_user.email, "progress",
                                   _lcs(lesson.get("title")), persona="tutor")
            except Exception:
                pass
        result = {"answers": answers, "correct_count": correct_count, "total": len(questions), "pct": pct,
                  "explain": [next((item for item in questions if item is q), {}).get("explain", "") for q in questions]}
    return render_template("academy_lesson.html", lesson=lesson, questions=questions, progress=progress, result=result, total=len(questions), course=course)


@app.route("/api/academy/quiz/generate", methods=["POST"])
@login_required
def academy_quiz_generate():
    """Create a fresh lesson-aligned quiz. AI providers are preferred; curated
    lesson questions are the offline fallback. Answer keys remain server-side."""
    body = request.get_json(silent=True) or {}
    slug = str(body.get("lesson_slug") or "").strip()
    lesson = next((x for x in ACADEMY_LESSONS if x["slug"] == slug), None)
    if not lesson:
        return jsonify(error="Choose a valid Academy lesson."), 404
    course = get_course_for_lesson(slug)
    if course and course_locked(course):
        return jsonify(error="This lesson requires an upgraded plan."), 403
    if rate_limited(key="academy-quiz:" + client_ip() + ":" + str(current_user.id), limit=5, window=300):
        return jsonify(error="You've generated several quizzes recently. Please wait a few minutes."), 429

    prompt = (
        "Create exactly 5 distinct multiple-choice assessment questions for a cybersecurity training lesson. "
        "Use only the lesson facts below. Vary question styles: concept, scenario, output interpretation, "
        "safe decision-making. Beginner-friendly but meaningful. Return ONLY valid JSON: "
        '{"questions":[{"question":"...","choices":["...","...","...","..."],"answer":0,"explain":"..."}]}. '
        "Each question must have exactly 4 choices, answer must be integer 0-3, explanations should teach. "
        "Do not include unsafe real-world attack instructions. "
        f"\nLESSON: {lesson.get('title')}\nDESCRIPTION: {lesson.get('desc')}\n"
        f"OBJECTIVES: {json.dumps(lesson.get('objectives', []))}\n"
        f"NOTES: {json.dumps(lesson.get('content', []))}\n"
        f"EXISTING QUESTION IDEAS (do not copy verbatim): {json.dumps([q.get('question','') for q in lesson.get('questions', [])])}"
    )
    generated = None
    provider = "practice-bank"

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = (os.getenv("GEMINI_VISION_MODEL", "gemini-3.8-flash").strip() if _has_vision_input else _gemini_model())
    if api_key:
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json={"contents":[{"role":"user","parts":[{"text":prompt}]}],
                      "generationConfig":{"temperature":0.85,"responseMimeType":"application/json","maxOutputTokens":1800}},
                timeout=(8, 35))
            resp.raise_for_status()
            parts = (resp.json().get("candidates") or [{}])[0].get("content",{}).get("parts",[])
            raw = "\n".join(p.get("text","") for p in parts if isinstance(p,dict))
            generated = json.loads(raw)
            provider = "gemini"
        except Exception as exc:
            app.logger.warning("Academy quiz Gemini generation failed: %s", str(exc)[:180])
    if not generated:
        groq_key = os.getenv("GROQ_API_KEY", "").strip()
        if groq_key:
            try:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization":"Bearer "+groq_key,"Content-Type":"application/json"},
                    json={"model":os.getenv("GROQ_MODEL","openai/gpt-oss-20b"),
                          "messages":[{"role":"system","content":"Return only valid JSON, no markdown."},
                                     {"role":"user","content":prompt}],
                          "temperature":0.85,"max_tokens":1800,"response_format":{"type":"json_object"}},
                    timeout=25)
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"]
                generated = json.loads(raw)
                provider = "groq"
            except Exception as exc:
                app.logger.warning("Academy quiz Groq generation failed: %s", str(exc)[:180])

    valid = []
    for q in (generated or {}).get("questions", []) if isinstance(generated, dict) else []:
        if not isinstance(q, dict): continue
        choices = q.get("choices")
        answer = q.get("answer")
        question = str(q.get("question") or "").strip()[:700]
        if (len(question) >= 12 and isinstance(choices, list) and len(choices) == 4
                and all(isinstance(c, str) and c.strip() for c in choices)
                and isinstance(answer, int) and answer in range(4)):
            valid.append({"question":question, "choices":[str(c)[:350] for c in choices],
                          "answer":answer, "explain":str(q.get("explain") or "")[:900]})
    if len(valid) < 3:
        # Offline fallback: rotate and shuffle the lesson's reviewed question bank.
        bank = list(lesson.get("questions") or [])
        if bank:
            shift = int(time.time() // 30) % max(1, len(bank))
            bank = bank[shift:] + bank[:shift]
            valid = [{"question":q["question"],"choices":list(q["choices"]),
                      "answer":int(q["answer"]),"explain":q.get("explain","")} for q in bank[:5]]
            provider = "practice-bank"
    if not valid:
        return jsonify(error="A quiz could not be prepared for this lesson. Please try again."), 503

    # Randomise choice order on every attempt; update the private answer key accordingly.
    rng = secrets.SystemRandom()
    for question in valid:
        pairs = list(enumerate(question["choices"]))
        rng.shuffle(pairs)
        question["choices"] = [choice for _, choice in pairs]
        question["answer"] = next(i for i, (old_index, _) in enumerate(pairs)
                                  if old_index == question["answer"])

    # Keep the private answer key in the signed session, never in the browser response.
    quiz_id = secrets.token_urlsafe(12)
    session["academy_quiz"] = {"id":quiz_id,"slug":slug,"user_id":current_user.id,
                               "questions":valid,"created":int(time.time())}
    session.modified = True
    return jsonify(quiz_id=quiz_id, provider=provider,
                   questions=[{"question":q["question"],"choices":q["choices"]} for q in valid],
                   message=("Fresh AI-generated questions" if provider in ("gemini","groq")
                            else "Practice mode: using the lesson question bank while AI generation is unavailable."))


@app.route("/api/academy/quiz/submit", methods=["POST"])
@login_required
def academy_quiz_submit():
    body = request.get_json(silent=True) or {}
    quiz = session.get("academy_quiz") or {}
    if (not quiz or quiz.get("id") != body.get("quiz_id")
            or quiz.get("user_id") != current_user.id
            or time.time() - int(quiz.get("created", 0)) > 1800):
        return jsonify(error="This quiz has expired. Generate a fresh quiz and try again."), 400
    lesson = next((x for x in ACADEMY_LESSONS if x["slug"] == quiz.get("slug")), None)
    if not lesson:
        return jsonify(error="Lesson not found."), 404
    course = get_course_for_lesson(quiz["slug"])
    if course and course_locked(course):
        return jsonify(error="Your course access has changed. Please refresh the page."), 403
    submitted = body.get("answers") or []
    qs = quiz.get("questions") or []
    correct = 0
    feedback = []
    for i, q in enumerate(qs):
        try: selected = int(submitted[i])
        except (TypeError, ValueError, IndexError): selected = -1
        ok = selected == q["answer"]
        correct += int(ok)
        feedback.append({"correct":ok,"correct_choice":q["answer"],"correct_answer":q["choices"][q["answer"]],"explain":q.get("explain","")})
    pct = int(round(correct / max(1,len(qs)) * 100))
    row = AcademyProgress.query.filter_by(user_id=current_user.id, lesson_slug=quiz["slug"]).first()
    if not row:
        row = AcademyProgress(user_id=current_user.id, lesson_slug=quiz["slug"])
        db.session.add(row)
    row.best_score = max(row.best_score or 0, pct)
    if pct >= 80 and not row.completed_at:
        row.completed_at = datetime.utcnow()
    db.session.commit()
    session.pop("academy_quiz", None)
    return jsonify(score=pct, correct=correct, total=len(qs), completed=pct >= 80,
                   feedback=feedback, best_score=row.best_score)


@app.route("/videos", methods=["GET"])
@login_required
def cyberlord_videos():
    """Free video discovery: uses YouTube's public search page and embeds user-selected videos.

    No YouTube API key, paid provider, or GPU is required. This does not generate original videos.
    """
    query = (request.args.get("q") or "").strip()[:160]
    video_input = (request.args.get("v") or "").strip()
    video_id = video_input
    # Accept a video ID or a standard YouTube/youtu.be URL, then validate the ID.
    if video_input.startswith(("https://", "http://")):
        try:
            parsed_video_url = urlparse(video_input)
            host = (parsed_video_url.hostname or "").lower()
            if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}:
                video_id = (parse_qs(parsed_video_url.query).get("v") or [""])[0]
                if not video_id and parsed_video_url.path.startswith("/embed/"):
                    video_id = parsed_video_url.path.split("/embed/", 1)[1].split("/", 1)[0]
            elif host == "youtu.be":
                video_id = parsed_video_url.path.strip("/").split("/", 1)[0]
            else:
                video_id = ""
        except Exception:
            video_id = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        video_id = ""
    return render_template("videos.html", video_query=query, video_id=video_id)


@app.route("/tutor")
@login_required
def tutor():
    """Full-page tutor dashboard. Uses the same /api/ai-assistant endpoint
    as the lesson panels, so lesson context and the GEMINI_API_KEY routing
    (with built-in fallback) are shared. Chat history is kept in the
    browser session (sessionStorage) by templates/tutor.html."""
    lesson_slug = (request.args.get("lesson") or "").strip()
    lesson = next((x for x in ACADEMY_LESSONS if x["slug"] == lesson_slug), None)
    return render_template("tutor.html", lesson_slug=lesson["slug"] if lesson else "", tutor_pro=tutor_pro_active(current_user), tutor_remaining=tutor_remaining(current_user), tutor_limit=TUTOR_FREE_DAILY_LIMIT, tutor_pro_expires_at=getattr(current_user, "tutor_pro_expires_at", None))


@app.route("/interaction-board")
@login_required
def interaction_board():
    posts = BoardPost.query.order_by(BoardPost.created_at.desc()).limit(60).all()
    reply_counts = {p.id: BoardReply.query.filter_by(post_id=p.id).count() for p in posts}
    authors = {u.id: u.email.split("@")[0] for u in User.query.filter(User.id.in_([p.user_id for p in posts])).all()} if posts else {}
    return render_template("interaction_board.html", posts=posts, reply_counts=reply_counts, authors=authors)

@app.route("/interaction-board/new", methods=["POST"])
@login_required
def interaction_board_new():
    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()
    category = (request.form.get("category") or "General").strip()
    if category not in {"General", "Learning", "Tools", "Web Security", "Networking", "Project Showcase"}:
        category = "General"
    if not 5 <= len(title) <= 140 or not 10 <= len(body) <= 5000:
        flash("Use a title of 5–140 characters and a post of 10–5,000 characters.", "error")
        return redirect(url_for("interaction_board"))
    db.session.add(BoardPost(user_id=current_user.id, title=title, body=body, category=category))
    db.session.commit()
    flash("Your discussion has been published.", "success")
    return redirect(url_for("interaction_board"))

@app.route("/interaction-board/<int:post_id>", methods=["GET", "POST"])
@login_required
def interaction_thread(post_id):
    post = BoardPost.query.get_or_404(post_id)
    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        if not 2 <= len(body) <= 3000:
            flash("A reply must be between 2 and 3,000 characters.", "error")
        else:
            db.session.add(BoardReply(post_id=post.id, user_id=current_user.id, body=body))
            db.session.commit()
            flash("Your reply has been added.", "success")
            return redirect(url_for("interaction_thread", post_id=post.id))
    replies = BoardReply.query.filter_by(post_id=post.id).order_by(BoardReply.created_at.asc()).all()
    user_ids = {post.user_id} | {r.user_id for r in replies}
    authors = {u.id: u.email.split("@")[0] for u in User.query.filter(User.id.in_(user_ids)).all()}
    return render_template("interaction_thread.html", post=post, replies=replies, authors=authors)

@app.route("/security-centre")
@login_required
def security_centre():
    items = ScanHistory.query.filter_by(user_id=current_user.id).order_by(ScanHistory.created_at.desc()).limit(12).all()
    total = ScanHistory.query.filter_by(user_id=current_user.id).count()
    domains = len({x.target.lower() for x in items if "." in x.target and "@" not in x.target})
    return render_template("security_centre.html", items=items, total=total, domains=domains)

@app.route("/email-exposure-check", methods=["GET", "POST"])
def email_exposure_check():
    """Public 'Has my email been leaked?' checker (free tier).

    No login required. Free viewers see the verdict plus a small teaser;
    signed-in PRO members get the full exposure record. Results are saved to
    scan history only for signed-in users (so their own checks are trackable),
    never for anonymous visitors.
    """
    result = None
    email_val = ""
    if request.method == "POST":
        email_val = (request.form.get("email") or "").strip()
        result = check_email_exposure(email_val)
        if result.get("status") == "ok" and current_user.is_authenticated:
            save_scan("email_exposure_check", email_val.lower(), result)
    is_pro = bool(current_user.is_authenticated and PLANS.get(current_user.plan, PLANS["free"])["rank"] >= 1)
    return render_template("email_exposure.html", result=result, email_val=email_val, is_pro=is_pro)

@app.route("/history/<int:scan_id>/delete", methods=["POST"])
@login_required
def delete_scan(scan_id):
    # A user can delete only their own scan-history record.
    item = ScanHistory.query.filter_by(id=scan_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    flash("Scan activity deleted.", "success")
    return redirect(url_for("dashboard") + "#activity")

@app.route("/history/<int:scan_id>/download")
@login_required
def download_scan(scan_id):
    item = ScanHistory.query.filter_by(id=scan_id, user_id=current_user.id).first_or_404()
    try:
        result = json.loads(item.result_json)
    except (TypeError, json.JSONDecodeError):
        result = {"raw_result": item.result_json}
    report = {
        "report_title": "CyberLord Domain Intelligence Scan Report",
        "scan_id": item.id,
        "tool": item.tool,
        "tool_name": TOOL_NAMES.get(item.tool, item.tool),
        "target": item.target,
        "scanned_at_utc": item.created_at.replace(tzinfo=timezone.utc).isoformat() if item.created_at.tzinfo is None else item.created_at.isoformat(),
        "account": current_user.email,
        "result": result,
        "disclaimer": "This report contains the results recorded when the scan ran. Findings depend on target visibility, provider availability and scan coverage. It is not a guarantee that a target is secure."
    }
    output_format = request.args.get("format", "json").lower()
    stamp = item.created_at.strftime("%Y%m%d-%H%M%S")
    safe_target = re.sub(r"[^A-Za-z0-9._-]+", "_", item.target)[:70] or "scan"
    if output_format == "pdf":
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                                topMargin=18*mm, bottomMargin=18*mm, title=report["report_title"])
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontSize=18, leading=22, spaceAfter=8))
        styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], fontSize=11, leading=14, spaceBefore=10, spaceAfter=5))
        styles.add(ParagraphStyle(name="SmallBody", parent=styles["BodyText"], fontSize=8, leading=11))
        story = [Paragraph(escape(report["report_title"]), styles["ReportTitle"]),
                 Paragraph("Authorized scan record · Generated by CyberLord", styles["SmallBody"]), Spacer(1, 8)]
        metadata = [["Scan ID", str(item.id)], ["Tool", str(report["tool_name"])],
                    ["Target", str(item.target)], ["Scanned at (UTC)", str(report["scanned_at_utc"])],
                    ["Account", str(current_user.email)]]
        table = Table([[Paragraph("<b>"+escape(k)+"</b>", styles["SmallBody"]), Paragraph(escape(v), styles["SmallBody"])] for k,v in metadata],
                      colWidths=[38*mm, 132*mm], hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (0,-1), colors.HexColor("#e9eef5")),
                                   ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#cbd5e1")),
                                   ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 6),
                                   ("RIGHTPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 5),
                                   ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
        story += [table, Paragraph("Scan results", styles["SectionHeading"])]
        result_text = json.dumps(result, indent=2, ensure_ascii=False, default=str)
        # Preformatted preserves JSON structure while escaping markup-sensitive characters.
        story.append(Preformatted(result_text, ParagraphStyle(name="JSON", fontName="Courier", fontSize=7, leading=9,
                                                              textColor=colors.HexColor("#172033"),
                                                              backColor=colors.HexColor("#f3f6fa"), borderPadding=7,
                                                              spaceAfter=8, wordWrap="CJK")))
        story += [Paragraph("Important note", styles["SectionHeading"]),
                  Paragraph(escape(report["disclaimer"]), styles["SmallBody"])]
        doc.build(story)
        pdf_buffer.seek(0)
        return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True,
                         download_name=f"cyberlord-{safe_target}-{stamp}.pdf")
    if output_format == "txt":
        content = (report["report_title"] + "\n" + "="*52 + "\n" +
            f"Tool: {report['tool_name']}\nTarget: {item.target}\nScanned at (UTC): {report['scanned_at_utc']}\nScan ID: {item.id}\n\n" +
            json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n\n" + report["disclaimer"])
        return send_file(BytesIO(content.encode("utf-8")), mimetype="text/plain; charset=utf-8", as_attachment=True,
            download_name=f"cyberlord-{safe_target}-{stamp}.txt")
    return send_file(BytesIO(json.dumps(report, indent=2, ensure_ascii=False, default=str).encode("utf-8")),
        mimetype="application/json", as_attachment=True, download_name=f"cyberlord-{safe_target}-{stamp}.json")

@app.route("/scan/<tool>", methods=["POST"])
@login_required
def run_tool(tool):
    if tool not in TOOL_NAMES: return jsonify(error="Unknown tool"), 404
    if not allowed_tool(tool): return jsonify(error="This tool requires a paid plan."), 403
    limit_resp = _check_rate("scan", request.endpoint or tool)
    if limit_resp is not None: return limit_resp
    target=form_str("target", 512)
    if request.form.get("authorized") != "on":
        return jsonify(error="Confirm that you own this target or have explicit permission to assess it."), 400

    try:
        if tool == "compare":
            parts=[x.strip() for x in target.split(",")]
            if len(parts)!=2: raise ValueError("Enter exactly two public domains separated by a comma.")
            first,second=map(normalize_domain,parts)
            a=scan_domain(first); b=scan_domain(second)
            result={"domains":[first,second],"comparison":{"dns_A":{"first":a["evidence"]["A"],"second":b["evidence"]["A"]},
                "dns_MX":{"first":a["evidence"]["MX"],"second":b["evidence"]["MX"]},
                "tls":{"first":a["evidence"].get("tls"),"second":b["evidence"].get("tls")},
                "http_status":{"first":a["evidence"].get("http",{}).get("status"),"second":b["evidence"].get("http",{}).get("status")},
                "security_findings":{"first":a["findings"],"second":b["findings"]}},"note":"Side-by-side public configuration comparison; not a risk ranking."}
        elif tool == "ip":
            result=ip_intelligence(target)
        elif tool == "phone":
            number=phonenumbers.parse(target,None if target.startswith("+") else "NG")
            if not phonenumbers.is_possible_number(number): raise ValueError("This phone number is not a possible number for its numbering region.")
            normalized=phonenumbers.format_number(number,phonenumbers.PhoneNumberFormat.E164)
            result={"international":phonenumbers.format_number(number,phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                "national":phonenumbers.format_number(number,phonenumbers.PhoneNumberFormat.NATIONAL),
                "e164":normalized,"valid":phonenumbers.is_valid_number(number),"possible":phonenumbers.is_possible_number(number),
                "region":phonenumbers.region_code_for_number(number),"number_type":str(phonenumbers.number_type(number)),
                "carrier_hint":phonenumbers.carrier.name_for_number(number,"en"),
                "timezone_hints":list(phonenumbers.timezone.time_zones_for_number(number)),
                "kali_worker_deep_intelligence":kali_worker_phone_intel(normalized),
                "coverage":"Passive numbering-plan metadata only. Carrier labels can be outdated, especially after number portability.",
                "privacy_limit":"No subscriber identity, live location, WhatsApp lookup, call/SMS interception, account access or ownership lookup is performed."}
        elif tool == "deep_scan":
            domain=normalize_domain(target)
            result=deep_scan(domain)
        elif tool in {"domain","dns","subdomains","technology","email","attack_surface","cve","port","breach","email_review"}:
            if tool == "email_review":
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",target): raise ValueError("Enter a valid email address.")
                domain=normalize_domain(target.split("@",1)[1]); posture=email_posture(domain)
                result={"email":target,"domain":domain,"syntax_valid":True,"domain_email_posture":posture,"mailbox_exists":None,"note":"No mailbox login or delivery test is performed; this does not verify that the individual mailbox exists."}
            elif tool == "breach":
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",target): raise ValueError("Enter a valid email address for Breach Exposure.")
                result = check_email_exposure(target)
                result["target"] = target
                result["provider_status"] = "connected" if result.get("status") == "ok" else "not_connected"
                if result.get("status") == "ok":
                    result["message"] = "Infostealer exposure verdict from Hudson Rock (free, keyless)."
                elif result.get("status") == "invalid":
                    raise ValueError(result["reason"])
                else:
                    result["message"] = "The exposure source is unavailable right now. This is not a clean result; no breach conclusion can be made until the source answers."
            else:
                domain=normalize_domain(target)
                if tool in {"domain","dns"}: result=scan_domain(domain)
                elif tool=="subdomains": result=scan_subdomains(domain)
                elif tool=="email": result=email_posture(domain)
                elif tool=="technology": result=technology_fingerprint(domain)
                elif tool=="attack_surface":
                    result={"target":domain,"domain_security":scan_domain(domain),"subdomains":scan_subdomains(domain),"technology":technology_fingerprint(domain),"kali_deep_scan":kali_worker_scan(domain,["whatweb","testssl","nmap"]),"scope_note":"Publicly exposed inventory only. Active checks run only on domains pre-approved in the isolated Kali worker allowlist."}
                elif tool=="port":
                    result={"target":domain,"kali_deep_scan":kali_worker_scan(domain,["nmap"]),"scope_note":"Limited TCP service identification only; worker enforces explicit domain allowlisting and public-IP checks. No exploit scripts or brute force."}
                elif tool=="cve":
                    tech=technology_fingerprint(domain)
                    result={"target":domain,"technology_evidence":tech,"cve_matches":[],"message":"No verified product/version pair was identified. CVE matches are intentionally withheld rather than guessed.","next_step":"Confirm exact product and version from authoritative asset inventory before mapping advisories."}
        save_scan(tool,target,result)
        return jsonify(result=result)
    except ValueError as e: return jsonify(error=str(e)),400
    except requests.RequestException as e:
        app.logger.warning("External scan provider unavailable: %s",e)
        return jsonify(error="A scan provider could not be reached. Check the target and provider connection."),502
    except Exception:
        app.logger.exception("Tool execution failed")
        return jsonify(error="The check could not be completed. Verify the target and try again."),500


def squad_api_base():
    """Squad's production API base. Use sandbox only when explicitly requested."""
    return "https://sandbox-api-d.squadco.com" if os.getenv("SQUAD_ENV", "live").lower() == "sandbox" else "https://api-d.squadco.com"


def squad_request(method, path, **kwargs):
    """Call Squad without ever logging the merchant secret."""
    secret = os.getenv("SQUAD_SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError("Squad is not configured: SQUAD_SECRET_KEY is missing or empty.")
    headers = kwargs.pop("headers", {})
    headers.update({"Authorization": "Bearer " + secret, "Content-Type": "application/json"})
    url = squad_api_base() + path
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    except requests.RequestException as exc:
        app.logger.error("SQUAD_API_CONNECTION_ERROR method=%s path=%s error=%s", method, path, str(exc)[:500])
        raise RuntimeError("Could not connect to Squad. Check Render outbound connectivity and try again.") from exc

    if not response.ok:
        # Squad's response body is useful for diagnosing 400/401 errors.
        # It is truncated and the Authorization header is never logged.
        body = (response.text or "")[:1200]
        app.logger.error("SQUAD_API_HTTP_ERROR method=%s path=%s status=%s response=%s",
                         method, path, response.status_code, body)
        raise RuntimeError("Squad API returned HTTP %s: %s" %
                           (response.status_code, body[:400] or "empty response"))

    try:
        payload = response.json()
    except ValueError as exc:
        app.logger.error("SQUAD_API_INVALID_JSON path=%s status=%s body=%s",
                         path, response.status_code, (response.text or "")[:500])
        raise RuntimeError("Squad returned an unreadable response.") from exc

    if payload.get("success") is False:
        message = str(payload.get("message") or payload.get("error") or "Squad rejected the request")
        app.logger.error("SQUAD_API_REJECTED path=%s message=%s", path, message[:800])
        raise RuntimeError("Squad rejected the request: " + message[:400])

    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    return data if isinstance(data, dict) else payload


def squad_verify(reference, payment):
    """Trust only Squad's server-side verify endpoint, never browser query parameters."""
    data = squad_request("GET", "/transaction/verify/" + reference)
    status = str(data.get("transaction_status", "")).lower()
    amount = data.get("transaction_amount", data.get("amount"))
    currency = str(data.get("transaction_currency_id", data.get("currency", ""))).upper()
    if status != "success":
        return False
    if int(amount or 0) != payment.amount or currency != "NGN":
        app.logger.warning("Squad payment mismatch for reference %s", reference)
        return False
    return True


@app.route("/payment/squad/initialize", methods=["POST"])
@login_required
def payment_squad_initialize():
    plan = request.form.get("plan", "")
    if plan not in ("pro", "pro_plus", "tutor_pro"):
        flash("Select a valid plan.", "error")
        return redirect(url_for("dashboard") + "#plans")
    if not os.getenv("SQUAD_SECRET_KEY", "").strip():
        flash("Online payment is not configured yet. Please contact support.", "error")
        return redirect(url_for("dashboard") + "#plans")
    reference = "CLSQ-" + secrets.token_urlsafe(18).replace("-", "").replace("_", "")
    amount = PLANS[plan]["ngn"] * 100
    payment = Payment(user_id=current_user.id, reference=reference, plan=plan,
                      amount=amount, currency="NGN", status="pending", network="squad")
    db.session.add(payment)
    db.session.commit()
    try:
        data = squad_request("POST", "/transaction/initiate", json={
            "email": current_user.email,
            "amount": amount,
            "currency": "NGN",
            "customer_name": getattr(current_user, "name", "") or current_user.email,
            "initiate_type": "inline",
            "transaction_ref": reference,
            "callback_url": url_for("payment_squad_callback", _external=True),
            "payment_channels": ["card", "bank", "ussd", "transfer"],
            "pass_charge": False,
            "metadata": {"user_id": current_user.id, "plan": plan}
        })
        checkout_url = (
            data.get("checkout_url") or data.get("payment_url") or
            data.get("authorization_url") or data.get("checkoutUrl") or data.get("url")
        )
        if not isinstance(checkout_url, str) or not checkout_url.startswith("https://"):
            app.logger.error("SQUAD_INIT_NO_CHECKOUT_URL reference=%s response_keys=%s",
                             reference, sorted(data.keys()) if isinstance(data, dict) else type(data).__name__)
            raise RuntimeError("Squad response did not contain a valid HTTPS checkout URL.")
        app.logger.info("SQUAD_INIT_SUCCESS reference=%s plan=%s", reference, plan)
        return redirect(checkout_url, code=303)
    except Exception as exc:
        payment.status = "failed"
        db.session.commit()
        app.logger.exception("SQUAD_INIT_FAILED reference=%s plan=%s error=%s",
                             reference, plan, str(exc)[:500])
        flash("Squad checkout could not start: " + str(exc)[:250], "error")
        return redirect(url_for("dashboard") + "#plans")


@app.route("/payment/squad/callback")
@login_required
def payment_squad_callback():
    reference = request.args.get("transaction_ref") or request.args.get("reference") or ""
    payment = Payment.query.filter_by(reference=reference, user_id=current_user.id, network="squad").first()
    if not payment:
        flash("Squad payment reference was not found.", "error")
        return redirect(url_for("dashboard") + "#plans")
    try:
        if payment.status != "success" and squad_verify(reference, payment):
            activate_subscription(current_user, payment)
            db.session.commit()
            flash("Payment verified by Squad. Your plan is active for 30 days.", "success")
        elif payment.status == "success":
            flash("Your payment is already confirmed.", "success")
        else:
            flash("Squad has not confirmed this payment yet. Refresh your dashboard shortly.", "warning")
    except Exception:
        app.logger.exception("Squad callback verification failed")
        flash("We could not verify the payment yet. Your plan has not been activated; please retry shortly.", "warning")
    return redirect(url_for("dashboard") + "#plans")


@app.route("/payment/squad/webhook", methods=["POST"])
def payment_squad_webhook():
    # Squad webhook is only a notification. Re-query Squad before granting value.
    event = request.get_json(silent=True) or {}
    body = event.get("Body") or event.get("body") or {}
    reference = event.get("TransactionRef") or event.get("transaction_ref") or body.get("transaction_ref")
    if not reference:
        return jsonify(received=True), 200
    payment = Payment.query.filter_by(reference=reference, network="squad").first()
    if not payment or payment.status == "success":
        return jsonify(received=True), 200
    try:
        if squad_verify(reference, payment):
            user = db.session.get(User, payment.user_id)
            if user:
                activate_subscription(user, payment)
                db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Squad webhook verification failed")
        return jsonify(received=False), 503
    return jsonify(received=True), 200

def _admin_csrf_token():
    token = session.get("admin_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token
    return token

def _admin_authenticated():
    return session.get("cyberlord_admin_authenticated") is True

def _require_admin():
    if not _admin_authenticated():
        abort(403)
    supplied = request.form.get("csrf_token", "")
    expected = session.get("admin_csrf_token", "")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected):
        abort(400, description="The security token expired. Refresh the page and try again.")

@app.route("/api/reviews", methods=["GET"])
def api_list_reviews():
    try:
        from reviews import get_store as _review_store
        return jsonify(_review_store().public_summary(limit=50))
    except Exception:
        return jsonify({"average_rating": 0.0, "review_count": 0, "reviews": []})


@app.route("/api/reviews", methods=["POST"])
def api_submit_review():
    limit_resp = _check_rate("review")
    if limit_resp is not None:
        return limit_resp
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form
    name = (payload.get("name") or "").strip() if hasattr(payload, "get") else ""
    text = (payload.get("text") or "").strip() if hasattr(payload, "get") else ""
    email = (payload.get("email") or "").strip() if hasattr(payload, "get") else ""
    rating = payload.get("rating") if hasattr(payload, "get") else None
    # Logged-in reviewers get their account email attached automatically.
    if current_user.is_authenticated and not email:
        email = current_user.email
    try:
        from reviews import get_store as _review_store
        ok, err, row = _review_store().submit(name, rating, text, email)
    except Exception:
        ok, err, row = False, "Could not save your review right now. Please try again.", None
    if not ok:
        return jsonify(error=err), 400
    if not request.is_json:
        flash("Thanks! Your review is waiting for approval and will show on this page once approved.", "success")
        return redirect(url_for("index") + "#reviews")
    return jsonify(
        message="Thanks! Your review is waiting for approval and will show on this page once approved.",
        status="pending", id=row["id"] if row else None
    ), 201


@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    """Private payment administration; separate from customer accounts and login."""
    if not _admin_authenticated() and request.method == "POST":
        supplied_csrf = request.form.get("csrf_token", "")
        expected_csrf = session.get("admin_csrf_token", "")
        if not supplied_csrf or not expected_csrf or not hmac.compare_digest(supplied_csrf, expected_csrf):
            abort(400, description="The security token expired. Refresh the page and try again.")
        configured_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        configured_password = os.getenv("ADMIN_PASSWORD", "")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not configured_email or not configured_password:
            flash("Admin access is not configured yet. Add ADMIN_EMAIL and ADMIN_PASSWORD in Render Environment.", "error")
        elif hmac.compare_digest(email, configured_email) and hmac.compare_digest(password, configured_password):
            session.clear()
            session["cyberlord_admin_authenticated"] = True
            session["admin_email"] = configured_email
            session["admin_csrf_token"] = secrets.token_urlsafe(32)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("The administrator email or password is incorrect.", "error")
    if not _admin_authenticated():
        return render_template("admin_login.html", csrf_token=_admin_csrf_token())

    status_filter = request.args.get("status", "pending")
    query = db.session.query(Payment, User.email).join(User, User.id == Payment.user_id)
    if status_filter in ("pending", "success", "rejected", "failed"):
        query = query.filter(Payment.status == status_filter)
    else:
        status_filter = "all"
    payments = query.order_by(Payment.created_at.desc()).limit(250).all()
    counts = {status: Payment.query.filter_by(status=status).count() for status in ("pending", "success", "rejected", "failed")}
    try:
        from reviews import get_store as _review_store
        review_counts = _review_store().status_counts()
    except Exception:
        review_counts = {"pending": 0, "approved": 0, "rejected": 0}
    receipt_payment_ids = {row.payment_id for row in BankReceipt.query.with_entities(BankReceipt.payment_id).all()}
    return render_template("admin_payments.html", payments=payments, counts=counts, status_filter=status_filter, csrf_token=_admin_csrf_token(), review_counts=review_counts, receipt_payment_ids=receipt_payment_ids)

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    _require_admin()
    session.clear()
    flash("You have signed out of the administrator area.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/payments/<int:payment_id>/receipt")
def admin_payment_receipt(payment_id):
    if not _admin_authenticated(): abort(403)
    payment = db.session.get(Payment, payment_id)
    receipt = BankReceipt.query.filter_by(payment_id=payment_id).first()
    if not payment or not receipt: abort(404)
    from flask import make_response
    response = make_response(receipt.data)
    response.headers["Content-Type"] = receipt.content_type
    response.headers["Content-Disposition"] = 'inline; filename="%s"' % re.sub(r"[^A-Za-z0-9._-]", "_", receipt.filename)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/admin/payments/<int:payment_id>/approve", methods=["POST"])
def admin_approve_bank_payment(payment_id):
    _require_admin()
    payment = db.session.get(Payment, payment_id)
    eligible_methods = {"squad"}
    if not payment or payment.currency != "NGN" or payment.network not in eligible_methods or payment.status != "pending":
        flash("This payment is not an eligible pending Squad payment.", "error")
        return redirect(url_for("admin_dashboard"))
    user = db.session.get(User, payment.user_id)
    if not user:
        flash("The customer account could not be found.", "error")
        return redirect(url_for("admin_dashboard"))
    activate_subscription(user, payment)
    flash(f"Payment #{payment.id} approved. {PLANS[payment.plan]['name']} is now active for the customer.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/payments/<int:payment_id>/reject", methods=["POST"])
def admin_reject_bank_payment(payment_id):
    _require_admin()
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.status != "pending":
        flash("This payment is not pending and cannot be rejected.", "error")
        return redirect(url_for("admin_dashboard"))
    payment.status = "rejected"
    db.session.commit()
    flash(f"Payment #{payment.id} has been rejected. No subscription was activated.", "success")
    return redirect(url_for("admin_dashboard"))




@app.route("/admin/reviews", methods=["GET"])
def admin_reviews():
    if not _admin_authenticated():
        return redirect(url_for("admin_dashboard"))
    status_filter = request.args.get("status", "pending")
    try:
        from reviews import get_store as _review_store
        reviews = _review_store().list_by_status(status_filter, limit=250)
        review_counts = _review_store().status_counts()
    except Exception:
        reviews, review_counts = [], {"pending": 0, "approved": 0, "rejected": 0}
    if status_filter not in ("pending", "approved", "rejected", "all"):
        status_filter = "pending"
    return render_template("admin_reviews.html", reviews=reviews, review_counts=review_counts, status_filter=status_filter, csrf_token=_admin_csrf_token())


@app.route("/admin/reviews/<int:review_id>/<action>", methods=["POST"])
def admin_moderate_review(review_id, action):
    _require_admin()
    new_status = {"approve": "approved", "reject": "rejected"}.get(action)
    if not new_status:
        flash("Unknown action.", "error")
        return redirect(url_for("admin_reviews"))
    try:
        from reviews import get_store as _review_store
        changed = _review_store().set_status(review_id, new_status)
    except Exception:
        changed = False
    if changed:
        flash(f"Review #{review_id} {new_status}.", "success")
    else:
        flash("That review could not be updated.", "error")
    return redirect(url_for("admin_reviews"))


def _lesson_questions_context(lesson, max_chars=8000):
    """Compact per-lesson quiz context for the tutor: exercise plus each question
    (text, correct answer letter + choice text, short explanation). Capped so the
    system prompt stays bounded; lives in system parts, not the 1800-char user
    message, so truncation never clips it."""
    if not lesson:
        return ""
    parts = []
    ex = str(lesson.get("exercise", "") or "").strip()
    if ex:
        parts.append("Exercise: " + ex[:300])
    letters = "ABCDEFGHIJ"
    out = []
    for i, q in enumerate(lesson.get("questions", []) or [], 1):
        if not isinstance(q, dict):
            continue
        choices = q.get("choices", []) or []
        ans = q.get("answer", 0)
        try:
            ans = int(ans)
        except Exception:
            ans = 0
        letter = letters[ans] if 0 <= ans < len(letters) else str(ans + 1)
        choice_text = str(choices[ans]) if 0 <= ans < len(choices) else ""
        line = f"Q{i}: {str(q.get('question','')).strip()[:200]}"
        if choice_text:
            line += f" Answer {letter}: {choice_text[:120]}"
        expl = str(q.get("explain", "") or q.get("explanation", "") or "").strip()
        if expl:
            line += f" Why: {expl[:180]}"
        out.append(line)
    if out:
        parts.append("Lesson quiz questions:" + chr(10) + chr(10).join(out))
    block = chr(10).join(parts).strip()
    if len(block) > max_chars:
        block = block[:max_chars].rsplit(chr(10), 1)[0]
    return block



# --- Live info for main persona (ai-live-info), Gemini-gated ---
# Guardrail: never ground cybersecurity. Reuses the fallback's cyber key
# list so main + "what is nmap" still redirects to the tutor with no search.
try:
    from zoneinfo import ZoneInfo as _ZoneInfo
    _LAGOS_TZ = _ZoneInfo("Africa/Lagos")
except Exception:
    _LAGOS_TZ = timezone(timedelta(hours=1), "Africa/Lagos")

_LIVE_CYBER_KEYS = (
    "nmap", "wireshark", "burp", "metasploit", "sqlmap", "gobuster", "nikto", "searchsploit", "john the ripper", "hashcat",
    "cybersecurity", "cyber security", "penetration test", "pen test", "ethical hacker", "ethical hacking", "phishing", "malware", "ransomware",
    "vulnerability", "exploit", "cve", "cvss", "owasp", "xss", "sql injection", "zero day", "rootkit", "botnet", "ddos",
    "social engineering", "2fa", "mfa", "two factor", "firewall", "cryptography", "encryption", "tls", "https", "dns",
    "tcp", "udp", "subnet", "port scan", "kali", "linux", "ssh", "password manager", "strong password",
    "bug bounty", "bugbounty", "incident response", "forensics", "threat intelligence", "mitre", "zero trust",
    "api security", "cloud security", "container", "kubernetes", "wifi security", "wireless", "android", "mobile security",
    "git", "github secrets", "code injection", "how do i hack", "hack into", "break into", "course",
)
_LIVE_SITE_KEYS = (
    "cyberlord", "pro plus", "how much is pro", "subscription", "payment",
    "deep scan", "interaction board", "security centre", "advanced intelligence", "academy", "tutor",
)
_LIVE_TRIGGER_KEYS = (
    "latest", "today", "tonight", "news", "headline", "headlines", "top stories", "weather", "forecast",
    "temperature", "rain", "sunny", "cloudy", "humidity", "climate",
    "score", "scores", "result", "results", "football", "soccer", "basketball", "tennis", "cricket", "match",
    "price", "prices", "cost", "usd", "naira", "ngn", "bitcoin", "btc", "ethereum", "eth", "stock", "shares",
    "exchange rate", "dollar", "election", "politic", "who won", "current", "now", "live", "update", "updates",
    "trending", "trend", "happening", "recent", "break", "score line", "lagos", "abuja", "nigeria",
)

_LIVE_IMAGE_KEYS = ("picture", "pictures", "image", "images", "photo", "photos", "pic", "pics", "puctures", "wallpaper", "show me a", "show me an")
_LIVE_WEATHER_KEYS = ("weather", "forecast", "wether", "wheather", "temperature", "rain", "sunny", "cloudy", "humidity", "climate")
_LIVE_NEWS_KEYS = ("news", "headline", "headlines", "top stories", "latest news", "what is happening", "newz")

# Per-user memory: try to persist an explicit "remember this" fact before
# anything else runs in the AI path. Returns a short confirmation reply, or
# None when the user did not ask to remember anything. Anonymous handled by
# the @login_required wrapper on the caller; still guarded here.
def _memory_store():
    from user_memory import get_store
    return get_store()

def _user_memory_context(priority_note=None, query=""):
    """Short, query-relevant system context for the logged-in user, or empty for anon."""
    if not current_user or not current_user.is_authenticated:
        return ""
    try:
        from artificial_brain import retrieve_relevant_memories
        rows = _memory_store().load(str(current_user.id), limit=20)
        selected = retrieve_relevant_memories(rows, query or priority_note or "", limit=6)
        summary = "; ".join(str(row.get("summary") or "") for row in selected if row.get("summary"))
    except Exception:
        try:
            summary = _memory_store().context_summary(str(current_user.id), current_user.email)
        except Exception:
            return ""
    if not summary:
        return ""
    from user_memory import compose_system_context
    return compose_system_context(current_user.email, summary)

def _maybe_persist_remember(text):
    if not current_user or not current_user.is_authenticated:
        return None
    try:
        from user_memory import extract_remember
        fact = extract_remember(text)
        if not fact:
            return None
        _memory_store().save(str(current_user.id), current_user.email, "preference", fact)
        return "Got it, I will remember: %s. Welcome back anytime and I will carry on from here." % fact
    except Exception:
        return None

@app.route("/api/brain/teach", methods=["POST"])
@login_required
def artificial_brain_teach():
    """Save user-approved private knowledge for this account; this is retrieval learning, not model-weight training."""
    if rate_limited(key="brainteach:" + str(current_user.id), limit=8, window=300):
        return jsonify(error="Brain training is limited to 8 notes every 5 minutes."), 429
    body = request.get_json(silent=True) or {}
    note = str(body.get("note") or "").strip()
    topic = str(body.get("topic") or "User-approved knowledge").strip()[:100]
    if len(note) < 12:
        return jsonify(error="Add a little more detail (at least 12 characters)."), 400
    if len(note) > 1800:
        return jsonify(error="Each knowledge note is limited to 1,800 characters. Split longer material into smaller notes."), 400
    try:
        saved = _memory_store().save(str(current_user.id), current_user.email, "knowledge", note, topic=topic, persona="shared")
        if not saved:
            return jsonify(error="CyberLord could not save this note. Check the database connection and try again."), 503
        return jsonify(ok=True, message="Saved to your private CyberLord knowledge memory. It can be retrieved in Dashboard AI, Tutor and linked messaging chats.", scope="private_account_memory", model_retrained=False)
    except Exception as exc:
        app.logger.warning("Artificial brain knowledge save failed: %s", str(exc)[:140])
        return jsonify(error="The knowledge note could not be saved."), 503


def _gemini_model():
    # Valid stable Gemini names per Google docs 14 Nov 2026.
    # gemini-3.5-flash is deprecated (auto-routed to gemini-3.6-flash),
    # gemini-2.5-flash is deprecated (auto-routed to gemini-3.5-flash-lite),
    # gemini-3.5-flash-lite is REAL stable, gemini-3.8-flash is REAL stable.
    m = (os.getenv("GEMINI_MODEL", "") or "").strip()
    if m in ("gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.7-flash"):
        m = ""
    return m or "gemini-3.5-flash-lite"

def _main_live_guard(q):
    """Return ('cyber'|'site'|'images'|'weather'|'news'|'live'|None) for main persona."""
    low = (q or "").lower()
    if any(k in low for k in _LIVE_CYBER_KEYS):
        return "cyber"
    if any(k in low for k in _LIVE_SITE_KEYS):
        return "site"
    # A request to create/edit a visual must reach the AI + image generator;
    # only retrieval requests such as "find/show photos" use Wikimedia lookup.
    if any(k in low for k in _LIVE_IMAGE_KEYS) and not _image_generation_intent(low):
        return "images"
    if any(k in low for k in _LIVE_WEATHER_KEYS):
        return "weather"
    if any(k in low for k in _LIVE_NEWS_KEYS):
        return "news"
    if any(k in low for k in _LIVE_TRIGGER_KEYS) or _TIME_QUESTION_RE.search(low):
        return "live"
    return None


_TIME_QUESTION_RE = re.compile(r"(what[\'\s]+(?:time|day|date)|whats[\'\s]+(?:the[\'\s]+)?(?:time|day|date)|current[\'\s]+(?:time|date|day)|time[\'\s]+is[\'\s]+it|date[\'\s]+is[\'\s]+it|day[\'\s]+is[\'\s]+it|what[\'\s]+is[\'\s]+(?:the[\'\s]+)?current|whats[\'\s]+the[\'\s]+time|what[\'\s]+is[\'\s]+the[\'\s]+time|what[\'\s]+time[\'\s]+is[\'\s]+it|tell[\'\s]+me[\'\s]+the[\'\s]+time|exact[\'\s]+time|todays[\'\s]+date|today[\'\s]+s[\'\s]+date)", re.I)

def _current_datetime_line():
    now = datetime.now(_LAGOS_TZ)
    return "Today is " + now.strftime("%A, %B %d, %Y") + ", " + now.strftime("%-I:%M %p").lstrip("0") + " (Lagos time)"

@app.route("/api/ai-assistant", methods=["POST"])
@login_required
def ai_assistant():
    """Optional LLM assistant. Without a key it uses the curated built-in knowledge base (cyberlord_ai.py), which is not a live LLM. Provider chain: Gemini (gemini-3.5-flash-lite default, or valid GEMINI_MODEL) -> Groq (openai/gpt-oss-20b) -> built-in base. On any failure it silently falls back to the next provider, then to the built-in base, so the site stays fully functional without a key."""
    now = time.time()
    window = session.get("ai_rate_window", [])
    window = [stamp for stamp in window if now - stamp < 60]
    if len(window) >= 20:
        return jsonify(error="You're sending messages quickly. Please wait a moment and try again."), 429
    window.append(now)
    session["ai_rate_window"] = window

    body = request.get_json(silent=True) or {}
    messages = list(body.get("messages", []) or [])
    fallback_latest = next((m.get("content", "") for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str)), "")
    _prior_ai_answers = "\n\n".join(
        str(m.get("content", "")) for m in messages[-12:]
        if isinstance(m, dict) and m.get("role") in ("assistant", "model") and isinstance(m.get("content"), str)
    )[-5000:]
    # Per-user memory: an explicit "remember this/remember me as X" is saved
    # and confirmed immediately, before any provider spends a call on it.
    _remember_reply = _maybe_persist_remember(fallback_latest)
    if _remember_reply:
        _persona_for_remember = str(body.get("persona") or body.get("mode") or "").strip().lower()
        if _persona_for_remember not in ("tutor", "main"):
            _persona_for_remember = "tutor" if (body.get("lesson_slug") or body.get("lesson")) else "main"
        return jsonify(reply=_remember_reply, mode="user-memory", persona=_persona_for_remember, live_sources=[])
    _user_mem_ctx = _user_memory_context(query=fallback_latest)
    lesson_slug = body.get("lesson_slug") or body.get("lesson") or ""
    # Persona flag: "tutor" = academy tutor surfaces (lesson panels + /tutor
    # page, always carry a lesson_slug); "main" = dashboard assistant, broad.
    persona = str(body.get("persona") or body.get("mode") or "").strip().lower()
    if persona not in ("tutor", "main"):
        persona = "tutor" if lesson_slug else "main"
    # Live info guardrail (main persona only, Gemini grounding only).
    # cyber -> hard tutor-redirect, never search; site -> unchanged behaviour;
    # live -> Gemini google_search grounding.
    _live_guard = _main_live_guard(fallback_latest) if persona == "main" else None
    _tutor_image_search = persona == "tutor" and _main_live_guard(fallback_latest) == "images"
    _tutor_web_search = persona == "tutor" and any(term in (fallback_latest or "").lower() for term in (
        "search the web", "search online", "find online", "latest", "current", "recent",
        "official documentation", "sources", "look up", "research online"))
    if _tutor_image_search:
        try:
            from cyberlord_ai import fetch_images as _tutor_fetch_images
            _found_images = _tutor_fetch_images(fallback_latest, limit=4)
            return jsonify(reply="Here are some relevant pictures I found for your lesson.", mode="images", persona=persona,
                           images=_found_images, live_sources=["Wikimedia Commons"] if _found_images else [])
        except Exception as _img_exc:
            app.logger.warning("Tutor image search failed: %s", str(_img_exc)[:160])
    if persona == "main" and _live_guard == "cyber":
        return jsonify(reply="That is one for the tutor, head to the Academy tutor and they will walk you through it. The Academy covers Cybersecurity Foundations, Web Application Security, Network Security, Email & Phishing Defense, Digital Forensics & Incident Response, and Career Path & Certifications, so pick the course that matches your question and the tutor will help step by step.", mode="tutor-redirect", persona=persona, live_sources=[])
    if persona == "main":
        _low_q = (fallback_latest or "").lower()
        if _TIME_QUESTION_RE.search(_low_q):
            _now = datetime.now(_LAGOS_TZ)
            _exact = _now.strftime("Today is %A, %B %d, %Y, and the exact time is %-I:%M %p").lstrip("0")
            return jsonify(reply=_exact + " (Lagos time). It is the current time in Lagos, Nigeria.", mode="datetime-direct", persona=persona, live_sources=["Server clock (Africa/Lagos)"])
        if _live_guard == "images":
            from cyberlord_ai import fetch_images as _fi
            _imgs = _fi(fallback_latest, limit=4)
            _txt = "Here are some pictures I found for you." if _imgs else "I searched Wikimedia Commons and could not find a free picture for that just now. Try a different subject."
            return jsonify(reply=_txt, mode="images", persona=persona, images=_imgs, live_sources=["Wikimedia Commons"] if _imgs else [])
        if _live_guard in ("weather", "news"):
            from cyberlord_ai import fetch_live_fact as _flf
            _kind, _fact = _flf(fallback_latest)
            if _kind and _fact:
                return jsonify(reply=_fact, mode=_kind + "-direct", persona=persona, live_sources=["Open-Meteo" if _kind == "weather" else "Google News RSS"])
    # Tutor Pro gating: free tutor is limited, Tutor Pro is unlimited.
    # The main (dashboard) assistant is never limited by this.
    if persona == "tutor":
        if not tutor_pro_active(current_user) and tutor_usage_today(current_user) >= TUTOR_FREE_DAILY_LIMIT:
            return jsonify(error="You have used your free tutor questions for today (%d). Upgrade to Tutor Pro for unlimited tutor questions." % TUTOR_FREE_DAILY_LIMIT, tutor_pro=False, tutor_remaining=0, upgrade_url=url_for("dashboard") + "#plans"), 429
        record_tutor_use(current_user)
    lesson = None
    lesson_questions_block = ""
    if lesson_slug:
        lesson = next((x for x in ACADEMY_LESSONS if x["slug"] == str(lesson_slug).strip()), None)
        if lesson:
            lesson_questions_block = _lesson_questions_context(lesson)
            if persona == "tutor":
                context = (
                    "You are the CyberLord Academy Tutor. "
                    "Answer ONLY about the academy's lesson content and course topics: "
                    "the current lesson's material first, other academy topics second. "
                    "If asked something off-academy (weather, sport, general trivia, anything not taught here), "
                    "do NOT refuse flatly and never sound robotic. Redirect cleverly instead: tie the question "
                    "back to a cybersecurity or lesson angle (\"nice question - in this lesson's world, that'd be "
                    "... but let's stay on [topic]: ...\") or pull it back to a related lesson concept. "
                    "Keep it natural, human and short. Lesson: '" + str(lesson.get("title", "")) + "' (" + str(lesson.get("level", "")) + "). "
                    "Lesson description: " + str(lesson.get("desc", "")) + ". "
                    "Key points: " + " ".join(lesson.get("content", []) or []) + ". "
                    "Quiz rule: when a student asks about a lesson quiz question, you may "
                    "discuss and explain it, but reveal the correct answer only if they ask to check "
                    "their answer or have already attempted it; otherwise keep answers hidden so they learn. "
                    "Teach in plain, beginner-friendly steps; never give account/payment/scan results. "
                    "Safety: defensive and authorised-lab guidance only. "
                    + (" " + _user_mem_ctx if _user_mem_ctx else "")
                )
            else:
                context = (
                    "You are Cyber, the main CyberLord AI, the friendly general dashboard assistant for the CyberLord website. ""CREATOR RECOGNITION: If asked who created, built, developed, or founded CyberLord AI, CyberLord, or this assistant, answer accurately: 'CyberLord was created by Ogbonna Michael Chinedu in a research lab.' Do not substitute another person, company, or lab name, and do not invent a formal lab name. " "You have swagger: warm, sharp, a little playful and confident. Never robotic, never stiff. ""LANGUAGE RULE: you ALWAYS answer in clear, standard English first. You may understand questions written in Nigerian Pidgin (broken English), but your replies stay in plain, clear English. "
                    "You are NOT a cybersecurity-only bot and NOT the academy tutor. "
                    "LANGUAGE RULE: you ALWAYS answer in clear, standard English first. You may understand questions written in Nigerian Pidgin (broken English), but your replies stay in plain, clear English. "
                    "You are NOT a cybersecurity-only bot and NOT the academy tutor. "
                    "Chat naturally on ANY everyday topic: greetings, small talk, general knowledge, advice, "
                    "brainstorming, planning, everyday questions, and anything else the user asks. "
                    "Do NOT redirect non-cybersecurity topics back to cybersecurity and do NOT force a security angle. "
                    "You can also answer about the CyberLord website itself: it offers domain scans, deep scan, "
                    "CyberLord Academy, the AI tutor, the interaction board, the security centre, and advanced "
                    "intelligence. Pricing is Free NGN 0, Pro NGN 6,300, Pro Plus NGN 12,600, Tutor Pro NGN 6,300. "
                    "Answer truthfully and concisely in clear standard English, with a warm and playful tone, like a sharp friend. ALWAYS answer in clear standard English first. "
                    "If you do not actually know, say so plainly in one line instead of guessing or inventing. "
                    "IMPORTANT: You must NEVER answer cybersecurity or cyber-course questions yourself. If the user question is about cybersecurity, hacking, penetration testing, security tools (like nmap, wireshark, burp, metasploit, sqlmap), vulnerabilities, malware, phishing, hardening, or any Academy course or lesson topic, do NOT answer it. Instead reply with a short friendly redirect, for example: That is one for the tutor, head to the Academy tutor and they will walk you through it. and point them to the Academy tutor or the relevant course page (for example Cybersecurity Foundations, Web Application Security, Network Security, Email & Phishing Defense, Digital Forensics & Incident Response, or Career Path & Certifications). Keep the redirect warm and brief, one or two sentences. "
                    " " + _current_datetime_line() + ". "
                    "The user is also studying lesson '" + str(lesson.get("title", "")) + "'; only refer to it if it fits the conversation. "
                    "Never invent CyberLord account, payment, scan or subscription status. "
                    + (" " + _user_mem_ctx if _user_mem_ctx else "")
                )
            messages = [{"role": "user", "content": context}] + messages
    else:
        if persona == "main":
            messages = [{"role": "user", "content": (
                "You are Cyber, the main CyberLord AI, the friendly general dashboard assistant for the CyberLord website. ""CREATOR RECOGNITION: If asked who created, built, developed, or founded CyberLord AI, CyberLord, or this assistant, answer accurately: 'CyberLord was created by Ogbonna Michael Chinedu in a research lab.' Do not substitute another person, company, or lab name, and do not invent a formal lab name. " "You have swagger: warm, sharp, a little playful and confident. Never robotic, never stiff. ""LANGUAGE RULE: you ALWAYS answer in clear, standard English first. You may understand questions written in Nigerian Pidgin (broken English), but your replies stay in plain, clear English. "
                    "You are NOT a cybersecurity-only bot and NOT the academy tutor. "
                "LANGUAGE RULE: you ALWAYS answer in clear, standard English first. You may understand questions written in Nigerian Pidgin (broken English), but your replies stay in plain, clear English. "
                    "You are NOT a cybersecurity-only bot and NOT the academy tutor. "
                "Chat naturally on ANY everyday topic: greetings, small talk, general knowledge, advice, "
                "brainstorming, planning, everyday questions, and anything else the user asks. "
                "Do NOT redirect non-cybersecurity topics back to cybersecurity and do NOT force a security angle. "
                "You can also answer about the CyberLord website itself: it offers domain scans, deep scan, "
                "CyberLord Academy, the AI tutor, the interaction board, the security centre, and advanced "
                "intelligence. Pricing is Free NGN 0, Pro NGN 6,300, Pro Plus NGN 12,600, Tutor Pro NGN 6,300. "
                "IMPORTANT: You must NEVER answer cybersecurity or cyber-course questions yourself. If the user question is about cybersecurity, hacking, penetration testing, security tools (like nmap, wireshark, burp, metasploit, sqlmap), vulnerabilities, malware, phishing, hardening, or any Academy course or lesson topic, do NOT answer it. Instead reply with a short friendly redirect, for example: That is one for the tutor, head to the Academy tutor and they will walk you through it. and point them to the Academy tutor or the relevant course page (for example Cybersecurity Foundations, Web Application Security, Network Security, Email & Phishing Defense, Digital Forensics & Incident Response, or Career Path & Certifications). Keep the redirect warm and brief, one or two sentences. "
                "Answer truthfully and concisely with a warm, human tone, like a helpful friend. "
                "If you do not actually know, say so plainly in one line instead of guessing or inventing a wrong answer. "
                "Never invent CyberLord account, payment, scan or subscription status. "
                + _current_datetime_line() + "."
                + (" " + _user_mem_ctx if _user_mem_ctx else "")
            )}] + messages
        else:
            messages = [{"role": "user", "content": (
                "You are the CyberLord Academy Tutor. Answer ONLY about the academy's lesson content and course topics. "
                "If asked something off-academy, do NOT refuse flatly: redirect cleverly, tying the question back to a "
                "cybersecurity or lesson angle, or pull it back to a related lesson concept. "
                "Keep it natural, human and short. "
                "CyberLord includes built-in image and short-video generation tools. If asked to create an image, picture, diagram, infographic or video, do not claim you cannot; provide a concise visual/scene brief so the application can generate and attach it when the provider is configured. "
                + (" " + _user_mem_ctx if _user_mem_ctx else "")
            )}] + messages
    if not isinstance(messages, list):
        return jsonify(error="Invalid conversation format."), 400

    # One shared artificial-brain orchestration layer for Dashboard, Tutor and
    # linked WhatsApp/Telegram messages (they call this same endpoint).
    try:
        from artificial_brain import build_brain_instruction
        _brain_memory_rows = _memory_store().load(str(current_user.id), limit=20) if current_user.is_authenticated else []
        _brain_instruction = build_brain_instruction(fallback_latest, persona=persona, memory_rows=_brain_memory_rows)
        messages = [{"role": "user", "content": _brain_instruction}] + messages
    except Exception as _brain_exc:
        app.logger.warning("Artificial brain orchestration fallback: %s", str(_brain_exc)[:120])

    # Keep a short, bounded history and accept only plain-text user/assistant turns.
    contents = []
    _has_vision_input = False
    for item in messages[-12:]:
        if not isinstance(item, dict):
            continue
        content = item.get("content", "")
        if not isinstance(content, str):
            continue
        content = content.strip()[:1800]
        role = item.get("role")
        if role == "user":
            gemini_role = "user"
        elif role in ("assistant", "model"):
            gemini_role = "model"
        else:
            continue
        parts = [{"text": content}] if content else []
        attached_images = item.get("images", []) if isinstance(item.get("images"), list) else []
        for image in attached_images[:4]:
            if not isinstance(image, dict):
                continue
            mime = str(image.get("mime_type") or image.get("mimeType") or "")
            data = str(image.get("data") or "")
            if mime not in ("image/jpeg", "image/png", "image/webp") or not data or len(data) > 35_000_000:
                continue
            try:
                raw = base64.b64decode(data, validate=True)
                prepared = _normalize_image_for_ai(raw, mime)
                if prepared:
                    parts.append({"inline_data": {"mime_type": prepared["mime_type"], "data": prepared["data"]}})
                    _has_vision_input = True
            except Exception:
                continue
        if not parts:
            continue
        if contents and contents[-1]["role"] == gemini_role and not attached_images:
            contents[-1]["parts"][0]["text"] += "\n\n" + content
        else:
            contents.append({"role": gemini_role, "parts": parts})
    if not contents or contents[-1]["role"] != "user":
        return jsonify(error="Please enter a question."), 400

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = _gemini_model()
    if api_key:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            if persona == "tutor":
                system_line = (
                    "You are the CyberLord Academy Tutor. Answer ONLY about the academy's lesson content ""CREATOR RECOGNITION: If asked who created, built, developed, or founded CyberLord AI, CyberLord, or this assistant, answer accurately: 'CyberLord was created by Ogbonna Michael Chinedu in a research lab.' Do not substitute another person, company, or lab name, and do not invent a formal lab name. " 
                    "and course topics (current lesson first, other academy topics second). If asked "
                    "something off-academy, do NOT refuse flatly: redirect cleverly, tying the question "
                    "back to a cybersecurity or lesson angle, or pull it back to a related lesson concept. "
                    "Natural, human, short. "
                    "MEDIA CAPABILITIES: You can request image and short video creation through CyberLord's built-in media tools. "
                    "When the user asks for an image, use the application media tools and do not merely say that you found or generated pictures unless actual image results are attached. "
                    "When the user requests a video, do not write a scene brief or continue with an unrelated lesson. The application handles video generation. Give only a short status: if queued, say exactly \"Building your video now.\" If it cannot be queued, clearly say video generation could not be started. Never claim a video is rendering unless a job was successfully queued. "
                    "Keep all generated educational visuals relevant to cybersecurity and safe learning. "
                    "Quiz rule: when a student asks about a lesson quiz question, you may discuss and "
                    "explain it, but reveal the correct answer only if they ask to check their answer or "
                    "have already attempted it; otherwise keep answers hidden so they learn."
                )
            else:
                system_line = (
                    "You are Cyber, the main CyberLord AI, the friendly general dashboard assistant for the CyberLord website. ""CREATOR RECOGNITION: If asked who created, built, developed, or founded CyberLord AI, CyberLord, or this assistant, answer accurately: 'CyberLord was created by Ogbonna Michael Chinedu in a research lab.' Do not substitute another person, company, or lab name, and do not invent a formal lab name. " "You have swagger: warm, sharp, a little playful and confident. Never robotic, never stiff. ""LANGUAGE RULE: you ALWAYS answer in clear, standard English first. You may understand questions written in Nigerian Pidgin (broken English), but your replies stay in plain, clear English. "
                    "You are NOT a cybersecurity-only bot and NOT the academy tutor. "
                    "You are NOT a cybersecurity-only bot and NOT the academy tutor. Chat naturally on ANY "
                    "everyday topic: greetings, small talk, general knowledge, advice, brainstorming, planning, "
                    "everyday questions, and anything else. Do NOT redirect non-cybersecurity topics back to "
                    "cybersecurity and do NOT force a security angle. You can also answer about the CyberLord "
                    "website itself: it offers domain scans, deep scan, CyberLord Academy, the AI tutor, the "
                    "interaction board, the security centre, and advanced intelligence. Pricing is Free NGN 0, "
                    "Pro NGN 6,300, Pro Plus NGN 12,600, Tutor Pro NGN 6,300. " "IMPORTANT: You must NEVER answer cybersecurity or cyber-course questions yourself. If the user question is about cybersecurity, hacking, penetration testing, security tools (like nmap, wireshark, burp, metasploit, sqlmap), vulnerabilities, malware, phishing, hardening, or any Academy course or lesson topic, do NOT answer it. Instead reply with a short friendly redirect, for example: That is one for the tutor, head to the Academy tutor and they will walk you through it. and point them to the Academy tutor or the relevant course page (for example Cybersecurity Foundations, Web Application Security, Network Security, Email & Phishing Defense, Digital Forensics & Incident Response, or Career Path & Certifications). Keep the redirect warm and brief, one or two sentences. " "Answer truthfully and concisely with a warm, human tone, "
                    "like a helpful friend. If you do not actually know, say so plainly in one line instead of "
                    "guessing or inventing. The security guardrails below apply only to security-related requests; "
                    "for general chat, just answer normally. "
                    "For current real-world info (news, weather, prices, sports scores) you may use Google Search grounding when enabled. " + _current_datetime_line() + ". "
                    "When the user asks for an image, diagram, infographic or visual, answer their question clearly; the server will create the requested visual from your answer and show it in the chat. "
                )
            _sys_parts = [{"text": (
                    system_line +
                    "Give clear, accurate, beginner-friendly explanations. Prefer practical, "
                    "step-by-step defensive guidance. Support authorised security testing only; "
                    "do not help compromise systems, steal credentials, evade detection, deploy "
                    "malware, or access data without permission. For dual-use questions, keep "
                    "the answer bounded to a legal lab or defensive validation. Never claim "
                    "you performed a scan or verified a live target unless a tool result is supplied. "
                    "Do not invent CyberLord account, payment, scan or subscription status. "
                    "Do not request passwords, OTPs, API keys, wallet seed phrases or private keys. "
                    "If uncertain, say so and recommend checking primary documentation."
                )}]
            if _has_vision_input:
                _sys_parts.append({"text": (
                    "IMAGE ANALYSIS MODE: One or more actual image attachments are included in the latest user message. "
                    "You MUST inspect those image pixels before answering. Do not guess from the user's wording, filename, "
                    "conversation history, or assumptions. Describe only details visibly supported by the image. "
                    "Separate direct observations from uncertain interpretations. If text is too small, blurred, cropped, "
                    "or unreadable, say exactly that instead of inventing it. If multiple images are attached, identify "
                    "them as Image 1, Image 2, etc. Answer the user's specific question about the attached image. "
                    "If the image is not actually visible to you, say you cannot access it and do not fabricate a description. "
                    "For screenshots, distinguish visible UI text from your interpretation; quote text only when legible."
                )})
            if lesson_questions_block and persona == "tutor":
                _sys_parts.append({"text": "Current lesson exercise and quiz questions (with correct answers and short explanations) for this tutor session:" + chr(10) + lesson_questions_block})
            if _user_mem_ctx:
                _sys_parts.append({"text": _user_mem_ctx})
            payload = {
                "systemInstruction": {"parts": _sys_parts},
                "contents": contents,
                "generationConfig": {"temperature": 0.55, "maxOutputTokens": 1200, "candidateCount": 1},
            }
            # Gemini Google Search grounding for main persona live questions only.
            # Docs: REST generateContent uses tools=[{"google_search":{}}] (generateContent API). JS/Vertex uses googleSearch camelCase. Old code used googleSearch for weather/news, which the REST generateContent API rejects with 400, so grounded calls failed while plain calls (no tools) succeeded. Use google_search for all live guards. If a grounded request is rejected, retry once without tools before falling back to Groq/built-in, so chat still answers.
            if _live_guard in ("live", "weather", "news") or _tutor_web_search:
                payload["tools"] = [{"google_search": {}}]
            # Gemini can take longer than a short web-request timeout and may
            # return temporary 429/5xx capacity errors. Retry only transient
            # failures a limited number of times with exponential backoff.
            response = None
            for attempt in range(3):
                try:
                    response = requests.post(
                        endpoint,
                        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                        json=payload,
                        timeout=(10, 60),
                    )
                    if response.status_code not in (408, 429, 500, 502, 503, 504):
                        response.raise_for_status()
                        break
                    if attempt == 2:
                        response.raise_for_status()
                    app.logger.warning(
                        "Gemini temporary HTTP %s; retrying attempt %s/3",
                        response.status_code, attempt + 2
                    )
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as retry_exc:
                    if attempt == 2:
                        raise
                    app.logger.warning(
                        "Gemini connection/timeout issue; retrying attempt %s/3: %s",
                        attempt + 2, str(retry_exc)[:160]
                    )
                time.sleep(2 ** attempt)
            if response is None:
                raise RuntimeError("Gemini request did not produce a response.")
            data = response.json()
            candidates = data.get("candidates") or []
            parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
            reply = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
            if not reply:
                raise ValueError("Gemini returned an empty response.")
            _images = []
            try:
                _meta = candidates[0].get("groundingMetadata") or {}
                for _ch in ((_meta.get("groundingChunks") or []) + (_meta.get("webImages") or [])):
                    _u = (_ch.get("web") or {}).get("uri") or _ch.get("uri") or ""
                    if _u.startswith("http"):
                        _images.append({"url": _u, "thumb": _u, "title": (_ch.get("web") or {}).get("title", "")})
            except Exception:
                pass
            _ls = ["Google Search grounding"] if (_live_guard in ("live", "weather", "news") or _tutor_web_search) else "Gemini response; verify important security findings against primary sources"
            _response_payload = _with_generated_images(
                {"reply": reply, "mode": "gemini", "model": model, "persona": persona,
                 "live_sources": _ls, "images": _images[:4]},
                fallback_latest, (_prior_ai_answers + "\n\n" + reply).strip(),
                next((m.get("images", []) for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "user" and m.get("images")), None),
                persona=persona,
            )
            return jsonify(**_response_payload)
        except Exception as exc:
            # If grounding was attached and the API rejected it, retry once plain (no tools) so only the search fails, not the whole chat.
            _grounded_exc = exc
            if "payload" in locals() and isinstance(payload, dict) and payload.pop("tools", None):
                try:
                    _r = requests.post(endpoint, headers={"Content-Type":"application/json","x-goog-api-key":api_key}, json=payload, timeout=(10,60))
                    _r.raise_for_status()
                    _d = _r.json()
                    _c = _d.get("candidates") or []
                    _parts = ((_c[0].get("content") or {}).get("parts") or []) if _c else []
                    _reply = "\n".join(_p.get("text","") for _p in _parts if isinstance(_p, dict)).strip()
                    if _reply:
                        app.logger.warning("Gemini grounding rejected, plain retry succeeded: %s", str(_grounded_exc)[:180])
                        _retry_payload = _with_generated_images(
                            {"reply": _reply, "mode": "gemini", "model": model, "persona": persona,
                             "live_sources": ["Gemini response; search grounding unavailable"], "images": []},
                            fallback_latest, (_prior_ai_answers + "\n\n" + _reply).strip(),
                            next((m.get("images", []) for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "user" and m.get("images")), None),
                            persona=persona,
                        )
                        return jsonify(**_retry_payload)
                except Exception:
                    pass
            app.logger.warning("Gemini API unavailable; trying next provider: %s", str(exc)[:240])

    if _has_vision_input:
        return jsonify(error="Image understanding requires Gemini vision. Add GEMINI_API_KEY in Render Environment and try again."), 503

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip() or "openai/gpt-oss-20b"
    if groq_key:
        try:
            groq_system = (
                "You are the CyberLord Academy Tutor. Answer ONLY about the academy's lesson content ""CREATOR RECOGNITION: If asked who created, built, developed, or founded CyberLord AI, CyberLord, or this assistant, answer accurately: 'CyberLord was created by Ogbonna Michael Chinedu in a research lab.' Do not substitute another person, company, or lab name, and do not invent a formal lab name. " 
                "and course topics (current lesson first, other academy topics second). If asked "
                "something off-academy, do NOT refuse flatly: redirect cleverly, tying the question "
                "back to a cybersecurity or lesson angle, or pull it back to a related lesson concept. "
                "Natural, human, short. "
                "MEDIA CAPABILITIES: CyberLord has built-in image and short-video generation tools. When asked to generate/create/draw/design an image, picture, diagram, infographic or illustration, give a concise visual brief and NEVER claim you cannot generate or export images. The application will attach generated media when its provider is configured. For video requests, describe the intended scenes briefly and let the application attempt generation; do not claim the capability does not exist. "
                "Keep generated educational visuals relevant to cybersecurity and safe learning. "
                "Quiz rule: when a student asks about a lesson quiz question, you may discuss and "
                "explain it, but reveal the correct answer only if they ask to check their answer or "
                "have already attempted it; otherwise keep answers hidden so they learn."
            ) if persona == "tutor" else (
                "You are Cyber, the main CyberLord AI, the friendly general dashboard assistant for the CyberLord website. ""CREATOR RECOGNITION: If asked who created, built, developed, or founded CyberLord AI, CyberLord, or this assistant, answer accurately: 'CyberLord was created by Ogbonna Michael Chinedu in a research lab.' Do not substitute another person, company, or lab name, and do not invent a formal lab name. " "You have swagger: warm, sharp, a little playful and confident. Never robotic, never stiff. ""LANGUAGE RULE: you ALWAYS answer in clear, standard English first. You may understand questions written in Nigerian Pidgin (broken English), but your replies stay in plain, clear English. "
                    "You are NOT a cybersecurity-only bot and NOT the academy tutor. "
                "You are NOT a cybersecurity-only bot and NOT the academy tutor. Chat naturally on ANY "
                "everyday topic: greetings, small talk, general knowledge, advice, brainstorming, planning, "
                "everyday questions, and anything else. Do NOT redirect non-cybersecurity topics back to "
                "cybersecurity and do NOT force a security angle. You can also answer about the CyberLord "
                "website itself: it offers domain scans, deep scan, CyberLord Academy, the AI tutor, the "
                "interaction board, the security centre, and advanced intelligence. Pricing is Free NGN 0, "
                "Pro NGN 6,300, Pro Plus NGN 12,600, Tutor Pro NGN 6,300. " "IMPORTANT: You must NEVER answer cybersecurity or cyber-course questions yourself. If the user question is about cybersecurity, hacking, penetration testing, security tools (like nmap, wireshark, burp, metasploit, sqlmap), vulnerabilities, malware, phishing, hardening, or any Academy course or lesson topic, do NOT answer it. Instead reply with a short friendly redirect, for example: That is one for the tutor, head to the Academy tutor and they will walk you through it. and point them to the Academy tutor or the relevant course page (for example Cybersecurity Foundations, Web Application Security, Network Security, Email & Phishing Defense, Digital Forensics & Incident Response, or Career Path & Certifications). Keep the redirect warm and brief, one or two sentences. " "Answer truthfully and concisely with swagger, "
                "like a sharp friend who knows the streets of Lagos. If you do not actually know, say so plainly in one line instead of "
                "guessing or inventing. The security guardrails below apply only to security-related requests; "
                "for general chat, just answer normally. " + _current_datetime_line() + ". "
                "When the user asks for an image, diagram, infographic or visual, answer clearly; the server will create the requested visual from your answer and show it in the chat. "
            )
            if lesson_questions_block and persona == "tutor":
                groq_system += chr(10) + "Current lesson exercise and quiz questions (with correct answers and short explanations):" + chr(10) + lesson_questions_block
            if _user_mem_ctx:
                groq_system += chr(10) + _user_mem_ctx
            # Groq path: no live fetch. Gemini grounding is the only live path (owner scope).
            convo = [{"role": "system", "content": (
                groq_system +
                "Give clear, accurate, beginner-friendly explanations. Prefer practical, "
                "step-by-step defensive guidance. Support authorised security testing only; "
                "do not help compromise systems, steal credentials, evade detection, deploy "
                "malware, or access data without permission. For dual-use questions, keep "
                "the answer bounded to a legal lab or defensive validation. Never claim "
                "you performed a scan or verified a live target unless a tool result is supplied. "
                "Do not invent CyberLord account, payment, scan or subscription status. "
                "Do not request passwords, OTPs, API keys, wallet seed phrases or private keys. "
                "If uncertain, say so and recommend checking primary documentation."
            )}]
            for item in contents:
                convo.append({"role": "assistant" if item["role"] == "model" else "user",
                              "content": item["parts"][0]["text"]})
            groq_payload = {"model": groq_model, "messages": convo,
                            "temperature": 0.55, "max_tokens": 1200}
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + groq_key},
                json=groq_payload, timeout=12)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            reply = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
            if not reply:
                raise ValueError("Groq returned an empty response.")
            _groq_payload = _with_generated_images(
                {"reply": reply, "mode": "groq", "model": groq_model, "persona": persona,
                 "live_sources": "Groq response; verify important security findings against primary sources"},
                fallback_latest, (_prior_ai_answers + "\n\n" + reply).strip(),
                next((m.get("images", []) for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "user" and m.get("images")), None),
                persona=persona,
            )
            return jsonify(**_groq_payload)
        except Exception as exc:
            app.logger.warning("Groq API unavailable; using local CyberLord knowledge fallback: %s", str(exc)[:240])

    # Keep the service useful if no key is configured or every provider fails.
    try:
        from cyberlord_ai import answer
        latest = next(item["parts"][0]["text"] for item in reversed(contents) if item["role"] == "user")
        fallback_history = []
        for item in contents:
            fallback_history.append({"role": "assistant" if item["role"] == "model" else "user",
                                     "content": item["parts"][0]["text"]})
        reply = answer(fallback_latest, fallback_history, persona=persona, lesson=lesson)
        _fb_images = []
        _fb_sources = "NIST NVD and CISA KEV when reachable"
        if persona == "main":
            try:
                from cyberlord_ai import fetch_images as _fi2, fetch_live_fact as _flf2
                if _live_guard == "images":
                    _fb_images = _fi2(fallback_latest, limit=4)
                    _fb_sources = ["Wikimedia Commons"] if _fb_images else []
                elif _live_guard in ("weather", "news"):
                    _k, _f = _flf2(fallback_latest)
                    if _k:
                        _fb_sources = ["Open-Meteo" if _k == "weather" else "Google News RSS"]
            except Exception:
                pass
        _fallback_payload = _with_generated_images(
            {"reply": reply, "mode": "built-in-fallback", "persona": persona,
             "tutor_pro": tutor_pro_active(current_user) if persona == "tutor" else None,
             "tutor_remaining": tutor_remaining(current_user) if persona == "tutor" else None,
             "live_sources": _fb_sources, "images": _fb_images},
            fallback_latest, (_prior_ai_answers + "\n\n" + reply).strip(),
            next((m.get("images", []) for m in reversed(messages) if isinstance(m, dict) and m.get("role") == "user" and m.get("images")), None),
            persona=persona,
        )
        return jsonify(**_fallback_payload)
    except Exception:
        app.logger.exception("CyberLord assistant error")
        return jsonify(error="CyberLord AI is temporarily unavailable. Please try again shortly."), 500



@app.route("/api/agnes-video/<job_id>", methods=["GET"])
@login_required
def agnes_video_status(job_id):
    from agnes_video import get_job
    job = get_job(job_id, owner_id=str(current_user.id))
    if not job:
        return jsonify(error="Video job not found or access denied."), 404
    if job.get("status") == "completed":
        job["preview_url"] = url_for("agnes_video_preview", job_id=job_id)
        job["download_url"] = url_for("agnes_video_download", job_id=job_id)
    return jsonify(job)


@app.route("/api/agnes-video/<job_id>/preview", methods=["GET"])
@login_required
def agnes_video_preview(job_id):
    from agnes_video import video_bytes
    from flask import Response
    job = __import__("agnes_video").get_job(job_id, owner_id=str(current_user.id))
    media = video_bytes(job_id) if job else None
    if not media:
        return jsonify(error="Video is not ready."), 404
    raw, mime, filename = media
    return Response(raw, mimetype=mime, headers={"Content-Disposition": "inline; filename=\"%s\"" % filename,
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@app.route("/api/agnes-video/<job_id>/download", methods=["GET"])
@login_required
def agnes_video_download(job_id):
    from agnes_video import video_bytes
    from flask import Response
    job = __import__("agnes_video").get_job(job_id, owner_id=str(current_user.id))
    media = video_bytes(job_id) if job else None
    if not media:
        return jsonify(error="Video is not ready."), 404
    raw, mime, filename = media
    return Response(raw, mimetype=mime, headers={"Content-Disposition": "attachment; filename=\"%s\"" % filename,
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@app.route("/account/messaging", methods=["GET", "POST"])
@login_required
def messaging_account_settings():
    csrf = session.get("messaging_csrf")
    if not csrf:
        csrf = secrets.token_urlsafe(32)
        session["messaging_csrf"] = csrf
    if request.method == "POST":
        supplied = request.form.get("csrf_token", "")
        if not supplied or not hmac.compare_digest(supplied, csrf): abort(400)
        now = datetime.utcnow()
        # Only the most recently generated outstanding code remains valid.
        MessagingLinkCode.query.filter_by(user_id=current_user.id, used_at=None).update({"used_at": now})
        code = "%08d" % secrets.randbelow(100000000)
        row = MessagingLinkCode(user_id=current_user.id,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=now + timedelta(minutes=10))
        db.session.add(row)
        db.session.commit()
        session["messaging_link_code"] = code
        return redirect(url_for("messaging_account_settings"))
    code = session.pop("messaging_link_code", None)
    linked = MessagingAccount.query.filter_by(user_id=current_user.id).order_by(MessagingAccount.linked_at.desc()).all()
    return render_template("messaging_account.html", link_code=code, linked_accounts=linked, csrf_token=csrf)


@app.route("/account/messaging/unlink/<int:link_id>", methods=["POST"])
@login_required
def messaging_unlink(link_id):
    supplied = request.form.get("csrf_token", "")
    expected = session.get("messaging_csrf", "")
    if not supplied or not expected or not hmac.compare_digest(supplied, expected): abort(400)
    row = MessagingAccount.query.filter_by(id=link_id, user_id=current_user.id).first_or_404()
    db.session.delete(row)
    db.session.commit()
    flash("Messaging account disconnected.", "success")
    return redirect(url_for("messaging_account_settings"))


def _consume_messaging_link_code(channel, external_id, code):
    if not isinstance(code, str) or not re.fullmatch(r"\d{8}", code.strip()):
        return False, "Enter the eight-digit code from your CyberLord account settings."
    if rate_limited(key="messaging-link:" + channel + ":" + str(external_id), limit=5, window=600):
        return False, "Too many link attempts. Wait 10 minutes and generate a fresh code."
    digest = hashlib.sha256(code.strip().encode()).hexdigest()
    row = MessagingLinkCode.query.filter_by(code_hash=digest, used_at=None).with_for_update().first()
    now = datetime.utcnow()
    if not row or row.expires_at <= now:
        return False, "That link code is invalid or expired. Generate a new one at CyberLord → Account → Messaging."
    existing = MessagingAccount.query.filter_by(channel=channel, external_id=str(external_id)).first()
    if existing and existing.user_id != row.user_id:
        return False, "This messaging account is already linked to another CyberLord account. Contact support to change it."
    # A user may link one account per channel; replace their old mapping only after a valid code is supplied.
    old = MessagingAccount.query.filter_by(channel=channel, user_id=row.user_id).first()
    if old and old.external_id != str(external_id):
        db.session.delete(old)
    if not existing:
        db.session.add(MessagingAccount(channel=channel, external_id=str(external_id), user_id=row.user_id))
    row.used_at = now
    db.session.commit()
    return True, "Your %s account is now securely linked to CyberLord. Use /tutor for Academy Tutor or /main for Dashboard AI." % channel.title()


# ---------------------------------------------------------------------------
# Official WhatsApp Cloud API + Telegram bot adapters.
# Both channels reuse the existing AI assistant implementation; they do not
# create a second AI engine or alter the dashboard/tutor web experience.
# ---------------------------------------------------------------------------
_MESSAGING_HISTORY_LOCK = threading.Lock()


@app.route("/api/ai-image", methods=["POST"])
@app.route("/api/tutor-image", methods=["POST"])
@login_required
def ai_image_generate():
    """Shared authenticated image generation/editing endpoint for Dashboard and Tutor."""
    body = request.get_json(silent=True) or {}
    prompt = str(body.get("prompt") or "").strip()
    if not prompt or len(prompt) > 1800:
        return jsonify(error="Enter an image description (up to 1,800 characters)."), 400
    images = []
    for image in (body.get("images") or [])[:4]:
        if not isinstance(image, dict):
            continue
        mime, data = str(image.get("mime_type") or ""), str(image.get("data") or "")
        if mime not in ("image/jpeg", "image/png", "image/webp") or not data or len(data) > 35_000_000:
            continue
        try:
            raw = base64.b64decode(data, validate=True)
            prepared = _normalize_image_for_ai(raw, mime)
            if prepared:
                images.append(prepared)
        except Exception:
            continue
    generated, note = _generate_image_result(prompt, images)
    if not generated:
        return jsonify(error=note or "Image generation is temporarily unavailable."), 502
    return jsonify(ok=True, text=note, images=generated)


def _messaging_state(channel, external_id):
    row = MessagingState.query.filter_by(channel=channel, external_id=str(external_id)).first()
    if not row:
        row = MessagingState(channel=channel, external_id=str(external_id), persona="main", history_json="[]")
        db.session.add(row)
        db.session.commit()
    try:
        history = json.loads(row.history_json or "[]")
        if not isinstance(history, list): history = []
    except Exception:
        history = []
    return row, history


def _messaging_is_duplicate(channel, message_id):
    if not message_id:
        return False
    try:
        db.session.add(MessagingEvent(channel=channel, event_id=str(message_id)[:180]))
        db.session.commit()
        return False
    except Exception:
        db.session.rollback()
        return True


def _run_messaging_ai(channel, external_id, text, persona, user_id=None, images=None):
    # Linked channels share one account-level history per persona. Unlinked
    # chats remain isolated to their provider chat ID.
    if user_id is not None:
        history_channel = "account"
        history_external_id = "%s:%s" % (user_id, persona or "main")
    else:
        history_channel = channel
        history_external_id = external_id
    row, history = _messaging_state(history_channel, history_external_id)
    user_item = {"role": "user", "content": text}
    if images:
        user_item["images"] = images[:2]
    messages = history + [user_item]
    payload = {"messages": messages[-12:], "persona": persona}
    if persona == "tutor" and not user_id:
        message = "To use the Academy Tutor here, first sign in to CyberLord and link this chat. Visit Account → Messaging on the website, generate a one-time code, then send /link followed by that code here."
        return message, history, {"reply": message, "generated_images": []}
    # Reuse the actual authenticated website user's subscription and daily quota.
    with app.test_request_context("/api/ai-assistant", method="POST", json=payload):
        if user_id is not None:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        app.preprocess_request()  # load Flask-Login current_user from the test session
        response = ai_assistant.__wrapped__()
        if isinstance(response, tuple): response = response[0]
        result = response.get_json(silent=True) if hasattr(response, "get_json") else None
    if not result or not result.get("reply"):
        return (result or {}).get("error", "CyberLord AI is temporarily unavailable."), history, result or {}
    updated = (messages + [{"role": "assistant", "content": str(result["reply"])}])[-12:]
    persisted = [{k: v for k, v in item.items() if k != "images"} for item in updated]
    row.history_json = json.dumps(persisted)
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return str(result["reply"]), updated, result


def _messaging_command(text, current_persona):
    clean = (text or "").strip()
    low = clean.lower()
    if low in ("/tutor", "tutor", "/academy"):
        return "tutor", "CyberLord Academy Tutor selected. Ask your cybersecurity or course question."
    if low in ("/main", "main", "/dashboard"):
        return "main", "CyberLord Dashboard AI selected. Ask me anything."
    if low in ("/start", "/help", "help"):
        return current_persona, (
            "Welcome to CyberLord. Send a message to chat with the AI.\n"
            "Use /link 12345678 to connect your signed-in website account.\n"
            "Ask naturally for a picture, diagram or several variations; attach a picture with edit instructions.\n"
            "Use /main for Dashboard AI, /tutor for Academy Tutor, /reset to clear history, or /unlink to disconnect."
        )
    if low == "/reset":
        return current_persona, "Conversation context cleared. What would you like to ask?"
    return current_persona, None


def _messaging_account(channel, external_id):
    return MessagingAccount.query.filter_by(channel=channel, external_id=str(external_id)).first()


def _handle_messaging_text(channel, external_id, event_id, text_in):
    if _messaging_is_duplicate(channel, event_id):
        return None
    row, history = _messaging_state(channel, external_id)
    clean = (text_in or "").strip()
    low = clean.lower()
    if low.startswith("/link "):
        ok, reply = _consume_messaging_link_code(channel, external_id, clean.split(None, 1)[1])
        return reply
    if low == "/link":
        return "Generate a fresh one-time code from Account → Messaging on the CyberLord website, then send /link followed by the eight-digit code."
    if low == "/unlink":
        linked = _messaging_account(channel, external_id)
        if linked:
            db.session.delete(linked)
        row.persona = "main"
        row.history_json = "[]"
        db.session.commit()
        return "This chat has been disconnected from your CyberLord account and its saved chat context has been cleared."
    linked = _messaging_account(channel, external_id)
    user_id = linked.user_id if linked else None
    persona = row.persona or "main"
    if low in ("/tutor", "tutor", "/academy", "/main", "main", "/dashboard"):
        persona, reply = _messaging_command(clean, persona)
        row.persona = persona; db.session.commit()
        if persona == "tutor" and not _messaging_account(channel, external_id):
            return "Academy Tutor requires your signed-in CyberLord account. Open Account → Messaging on cyberlord.name.ng, generate an eight-digit code, then send /link CODE here."
        return reply
    if low in ("/start", "/help", "help"):
        return _messaging_command(clean, persona)[1]
    if low == "/reset":
        row.history_json = "[]"
        if linked:
            shared = MessagingState.query.filter_by(
                channel="account", external_id="%s:%s" % (linked.user_id, persona or "main")
            ).first()
            if shared:
                shared.history_json = "[]"
        db.session.commit()
        return _messaging_command(clean, persona)[1]
    if persona == "tutor" and not linked:
        return "Tutor access requires a linked CyberLord account. Sign in at cyberlord.name.ng, open Account → Messaging, generate a code, then send /link 12345678 here."
    reply, _, _result = _run_messaging_ai(channel, external_id, clean, persona, user_id=user_id)
    return reply

def _send_telegram_message(chat_id, text):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        app.logger.error("Telegram bot is not configured: TELEGRAM_BOT_TOKEN is missing")
        return False
    try:
        response = requests.post(
            "https://api.telegram.org/bot%s/sendMessage" % token,
            json={"chat_id": chat_id, "text": str(text)[:4000]}, timeout=15)
        response.raise_for_status()
        return True
    except Exception as exc:
        app.logger.warning("Telegram message delivery failed: %s", str(exc)[:180])
        return False


def _send_whatsapp_message(to, text):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    version = os.getenv("WHATSAPP_API_VERSION", "v26.0").strip() or "v26.0"
    if not token or not phone_id:
        app.logger.error("WhatsApp is not configured: access token or phone number ID is missing")
        return False
    try:
        response = requests.post(
            "https://graph.facebook.com/%s/%s/messages" % (version, phone_id),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "recipient_type": "individual",
                  "to": str(to), "type": "text", "text": {"preview_url": False, "body": str(text)[:4000]}},
            timeout=15)
        response.raise_for_status()
        return True
    except Exception as exc:
        app.logger.warning("WhatsApp message delivery failed: %s", str(exc)[:180])
        return False


def _generate_cloudflare_image_result(prompt, reference_images=None):
    """Fallback image generation through Cloudflare Workers AI's free daily allocation."""
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if not account_id or not token:
        return None, "No image provider is configured. Add GEMINI_API_KEY or CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in Render."
    if reference_images:
        return None, "The Cloudflare free image fallback currently supports creating images from text, not editing uploaded reference images. Configure Gemini for image editing."
    model = os.getenv("CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell").strip()
    try:
        response = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            json={"prompt": str(prompt)[:2000], "steps": 4}, timeout=(10, 120))
        if not response.ok:
            try:
                detail = str((response.json().get("errors") or [{}])[0].get("message") or "")
            except Exception:
                detail = ""
            app.logger.warning("Cloudflare image provider HTTP %s: %s", response.status_code, detail[:180])
            if response.status_code == 429:
                return None, "Cloudflare's free daily AI allowance or rate limit has been reached. Try again after the allowance resets."
            return None, "Cloudflare image generation failed. Check the account ID, Workers AI token permissions, model access and Render logs."
        payload = response.json()
        result = payload.get("result") or {}
        encoded = result.get("image") if isinstance(result, dict) else None
        if not encoded and isinstance(result, str):
            encoded = result
        if not encoded:
            return None, "Cloudflare returned no image. Check the selected Workers AI model and account quota."
        return [{"mime_type": "image/jpeg", "data": encoded}], "Image generated using Cloudflare Workers AI."
    except Exception as exc:
        app.logger.warning("Cloudflare image generation failed: %s", str(exc)[:180])
        return None, "Could not reach Cloudflare image generation. Please try again shortly."


def _generate_image_result(prompt, reference_images=None):
    """Gemini-first image pipeline with Cloudflare Workers AI text-to-image fallback."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return _generate_cloudflare_image_result(prompt, reference_images)
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image").strip()
    parts = [{"text": "Generate or edit the image as requested. Prompt: " + str(prompt)[:1800]}]
    for image in (reference_images or [])[:4]:
        if not isinstance(image, dict):
            continue
        mime = str(image.get("mime_type") or "")
        data = str(image.get("data") or "")
        if mime not in ("image/jpeg", "image/png", "image/webp") or not data or len(data) > 35_000_000:
            continue
        try:
            raw = base64.b64decode(data, validate=True)
            prepared = _normalize_image_for_ai(raw, mime)
            if prepared:
                parts.append({"inline_data": {"mime_type": prepared["mime_type"], "data": prepared["data"]}})
        except Exception:
            continue
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json={"contents": [{"role": "user", "parts": parts}],
                  "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
            timeout=(10, 120))
        if not response.ok:
            try:
                provider_message = (response.json().get("error") or {}).get("message", "")
            except Exception:
                provider_message = ""
            app.logger.warning("Gemini image provider returned HTTP %s: %s", response.status_code, provider_message[:180])
            if response.status_code in (401, 403):
                return _generate_cloudflare_image_result(prompt, reference_images)
            if response.status_code == 429:
                return _generate_cloudflare_image_result(prompt, reference_images)
            return _generate_cloudflare_image_result(prompt, reference_images)
        payload = response.json()
        candidates = payload.get("candidates") or []
        text_parts, images = [], []
        for part in ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []:
            if part.get("text"):
                text_parts.append(part["text"])
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                if mime in ("image/png", "image/jpeg", "image/webp"):
                    images.append({"mime_type": mime, "data": inline["data"]})
        if not images:
            block_reason = ((payload.get("promptFeedback") or {}).get("blockReason") or "")
            if block_reason:
                return None, "The image request was blocked by the provider's safety filter. Try a different description."
            return _generate_cloudflare_image_result(prompt, reference_images)
        return images, "\n".join(text_parts).strip() or "Your image is ready."
    except requests.RequestException as exc:
        app.logger.warning("Gemini image generation request failed: %s", str(exc)[:180])
        return _generate_cloudflare_image_result(prompt, reference_images)
    except Exception as exc:
        app.logger.warning("Gemini image generation failed: %s", str(exc)[:180])
        return _generate_cloudflare_image_result(prompt, reference_images)


def _image_generation_intent(user_text):
    """Detect an intentional request for a visual without a separate Create button."""
    text = str(user_text or "").strip().lower()
    if not text:
        return False
    patterns = (
        r"\b(generate|create|draw|make|design|produce|render|illustrate|visuali[sz]e)\b.{0,90}\b(image|picture|photo|illustration|logo|poster|artwork|diagram|infographic|chart|visual)\b",
        r"\b(turn|convert|transform)\b.{0,90}\b(into|to)\b.{0,30}\b(image|picture|diagram|infographic|visual)\b",
        r"\b(show|explain|teach)\b.{0,90}\b(with|as|using)\b.{0,30}\b(diagram|illustration|infographic|picture|visual)\b",
        r"\b(make|create|generate|draw)\b.{0,50}\b(from|based on)\b.{0,50}\b(answer|explanation|above|this)\b",
        r"\b(make|create|generate|draw)\b.{0,50}\b(this|that|your answer|your explanation)\b.{0,50}\b(image|picture|visual|diagram)\b",
        r"\b(edit|modify|change|transform|redesign)\b.{0,80}\b(this|the|attached|uploaded)?\s*(image|picture|photo)\b",
        r"\b(i want|i need)\b.{0,70}\b(image|picture|illustration|logo|poster|diagram|infographic|visual)\b",
        r"\b(show me|can you show|could you show)\b.{0,60}\b(diagram|infographic|visualization|visual)\b",
    )
    return any(re.search(pattern, text, re.I | re.S) for pattern in patterns)


def _requested_image_count(user_text):
    """Allow batches, but cap each message to protect provider quota and latency."""
    text = str(user_text or "").lower()
    match = re.search(r"\b([1-9])\s*(?:images?|pictures?|versions?|variations?)\b", text)
    if match:
        return min(4, max(1, int(match.group(1))))
    if re.search(r"\b(many|multiple|several|a few|different versions|variations)\b", text):
        return 4
    return 1


def _generate_images_from_answer(user_text, assistant_reply, reference_images=None):
    """Create requested visuals using both the user's request and the actual AI answer."""
    if not _image_generation_intent(user_text):
        return [], None
    if not os.getenv("GEMINI_API_KEY", "").strip():
        return [], "Image generation is not configured yet. Add GEMINI_API_KEY in Render Environment."
    # The model answer is included as source material, so requests such as
    # 'turn your explanation into a diagram' are grounded in what Gemini said.
    prompt = (
        "Create a polished, accurate visual based on the user's request and the AI's answer. "
        "Use the answer as the source of truth; do not add unsupported facts. "
        "Make labels readable, layout clear, and avoid tiny text.\nUSER REQUEST: "
        + str(user_text or "")[:1200] + "\nAI ANSWER / SOURCE MATERIAL: "
        + str(assistant_reply or "")[:5000]
    )
    images, note = [], None
    count = _requested_image_count(user_text)
    for index in range(count):
        generated, current_note = _generate_image_result(
            prompt + ("\nCreate a distinct visual variation, version %d of %d." % (index + 1, count) if count > 1 else ""),
            reference_images if index == 0 else None,
        )
        if generated:
            images.extend(generated[:1])
        elif not images:
            note = current_note
            break
    return images, note


def _file_generation_intent(user_text):
    text = str(user_text or "").lower()
    if not text.strip() or re.search(r"\b(how (?:do|can|should) i|how to|explain how|steps? to|teach me how)\b", text):
        return False
    return bool(re.search(
        r"\b(create|make|generate|prepare|export|save|turn|convert|download|put)\b.{0,100}\b(file|document|pdf|word|docx|spreadsheet|excel|xlsx|powerpoint|pptx|slides?|csv|text file|report)\b"
        r"|\b(as|in)\s+(a\s+)?(pdf|word document|docx|spreadsheet|excel|xlsx|powerpoint|pptx|csv|txt)\b",
        text, re.I | re.S))


def _requested_file_format(user_text):
    text = str(user_text or "").lower()
    if re.search(r"\b(powerpoint|pptx|slides?)\b", text): return "pptx"
    if re.search(r"\b(excel|spreadsheet|xlsx)\b", text): return "xlsx"
    if re.search(r"\bcsv\b", text): return "csv"
    if re.search(r"\b(word|docx)\b", text): return "docx"
    if re.search(r"\b(txt|plain text|text file)\b", text): return "txt"
    if re.search(r"\b(markdown|\.md)\b", text): return "md"
    return "pdf"


def _build_generated_file(user_text, assistant_reply):
    """Create a downloadable file using the actual assistant answer as its source."""
    if not _file_generation_intent(user_text):
        return None, None
    fmt = _requested_file_format(user_text)
    title = "CyberLord AI Output"
    content = str(assistant_reply or "").strip() or "No content was generated."
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", re.sub(r"\.[a-zA-Z0-9]+", "", str(user_text or ""))[:48]).strip("-")
    stem = (safe or "cyberlord-document")[:48]
    try:
        stream = BytesIO()
        if fmt == "pdf":
            styles = getSampleStyleSheet()
            story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 8)]
            for block in re.split(r"\n\s*\n", content):
                clean = escape(block).replace("\n", "<br/>")
                story.extend([Paragraph(clean, styles["BodyText"]), Spacer(1, 7)])
            doc = SimpleDocTemplate(stream, pagesize=A4, title=title, author="CyberLord AI")
            doc.build(story)
            mime, ext = "application/pdf", "pdf"
        elif fmt == "docx":
            from docx import Document
            doc = Document(); doc.add_heading(title, 0)
            for block in content.splitlines():
                line = block.strip()
                if not line: continue
                if line.startswith("# "): doc.add_heading(line[2:], level=1)
                elif line.startswith("## "): doc.add_heading(line[3:], level=2)
                elif line.startswith(("- ", "* ")): doc.add_paragraph(line[2:], style="List Bullet")
                else: doc.add_paragraph(line)
            doc.save(stream); mime, ext = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
        elif fmt == "xlsx":
            from openpyxl import Workbook
            wb = Workbook(); ws = wb.active; ws.title = "CyberLord Output"
            ws.append(["CyberLord AI Output"]); ws.append(["Content"])
            for line in content.splitlines() or [content]: ws.append([line])
            ws.column_dimensions["A"].width = 110
            wb.save(stream); mime, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
        elif fmt == "pptx":
            from pptx import Presentation
            from pptx.util import Inches, Pt
            prs = Presentation(); chunks = [x.strip() for x in re.split(r"\n\s*\n", content) if x.strip()]
            first = prs.slides.add_slide(prs.slide_layouts[0]); first.shapes.title.text = title
            first.placeholders[1].text = "Prepared by CyberLord AI"
            for index, chunk in enumerate(chunks[:20], 1):
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                lines = chunk.splitlines(); heading = lines[0][:90]
                slide.shapes.title.text = heading
                tf = slide.placeholders[1].text_frame; tf.clear()
                for line in (lines[1:] or [chunk])[:12]:
                    para = tf.add_paragraph(); para.text = line[:450]; para.font.size = Pt(18)
            prs.save(stream); mime, ext = "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"
        elif fmt == "csv":
            text_stream = __import__("io").StringIO(); writer = csv.writer(text_stream)
            writer.writerow(["CyberLord AI Output"]); writer.writerow(["Content"])
            for line in content.splitlines() or [content]: writer.writerow([line])
            stream.write(text_stream.getvalue().encode("utf-8-sig")); mime, ext = "text/csv", "csv"
        else:
            stream.write(content.encode("utf-8")); mime, ext = ("text/markdown", "md") if fmt == "md" else ("text/plain", "txt")
        encoded = base64.b64encode(stream.getvalue()).decode("ascii")
        return {"filename": f"{stem}.{ext}", "mime_type": mime, "data": encoded}, None
    except ImportError as exc:
        app.logger.warning("Optional document package missing: %s", str(exc)[:120])
        return None, "This file format needs its document package installed. Check the current Render deployment and requirements.txt."
    except Exception as exc:
        app.logger.warning("CyberLord file generation failed: %s", str(exc)[:180])
        return None, "I could not create that file. Please try again or choose PDF, DOCX, XLSX, PPTX, CSV or TXT."


def _video_generation_intent(user_text):
    text = str(user_text or "").lower()
    if re.search(r"\b(how (?:do|can|should) i|how to|explain how|steps? to|teach me how)\b", text):
        return False
    patterns = (
        r"\b(make|create|generate|produce|render|turn .* into|animate)\b.{0,100}\b(video|movie|clip|animation|trailer)\b",
        r"\b(video|movie|clip|animation)\b.{0,70}\b(generate|create|make|produce)\b",
        r"\banimate\b.{0,60}\b(this|that|the|attached|uploaded)?\s*(image|picture|photo)\b",
        r"\b(make|create|generate)\b.{0,80}\b(video|clip)\b.{0,80}\b(from|using|with)\b.{0,40}\b(image|picture|photo)\b",
    )
    return any(re.search(pattern, text, re.I | re.S) for pattern in patterns)


def _video_discovery_intent(user_text):
    text = str(user_text or "").lower()
    if _video_generation_intent(text):
        return False
    return bool(re.search(
        r"\b(find|search for|show me|recommend|look for|get me|any)\b.{0,90}\b(video|videos|tutorial|tutorials|youtube)\b"
        r"|\b(video|videos|tutorial|tutorials)\b.{0,70}\b(about|on|for|related to)\b",
        text, re.I | re.S
    ))


def _video_search_query(user_text, persona="main"):
    query = re.sub(r"\s+", " ", str(user_text or "")).strip()
    query = re.sub(r"(?i)\b(please|can you|could you|find|search for|show me|recommend|look for|get me|any|youtube|videos?|tutorials?)\b", " ", query)
    query = re.sub(r"\s+", " ", query).strip(" .,!?")
    if persona == "tutor" and query:
        query += " cybersecurity educational lesson"
    return (query or ("cybersecurity tutorial" if persona == "tutor" else "educational videos"))[:160]


def _attach_video_discovery(response_payload, user_text, persona="main"):
    query = _video_search_query(user_text, persona)
    search_url = "https://www.youtube.com/results?search_query=" + requests.utils.quote(query)
    try:
        from super_mode import youtube_search
        result = youtube_search(query, limit=6)
        items = result.get("items") or []
        response_payload["video_search"] = {"query": query, "items": items, "search_url": search_url, "source": "YouTube"}
        if not result.get("configured"):
            response_payload["video_search"]["setup_note"] = "YouTube previews need the optional YOUTUBE_API_KEY. The direct YouTube search link works without it."
        response_payload["reply"] = (
            "I found some videos for you. Choose one below to play it here."
            if items else "I can open YouTube results for that topic. Select the search button below."
        )
    except Exception as exc:
        app.logger.warning("Chat video discovery failed: %s", str(exc)[:160])
        response_payload["video_search"] = {"query": query, "items": [], "search_url": search_url, "source": "YouTube"}
        response_payload["reply"] = "I couldn't load video previews right now. You can still open the YouTube search below."


def _generate_video_from_answer(user_text, assistant_reply, reference_images=None, owner_id=None, persona="main"):
    """Queue video generation for either AI persona through the same optional provider."""
    image_attached = next((item for item in (reference_images or []) if isinstance(item, dict) and item.get("data")), None)
    image_animation_request = bool(image_attached and re.search(r"\b(animate|make|create|generate|turn|bring)\b", str(user_text or ""), re.I)
                                   and not re.search(r"\b(how to|how do i|teach me how|explain how)\b", str(user_text or ""), re.I))
    if not (_video_generation_intent(user_text) or image_animation_request):
        return None, None
    if not os.getenv("AGNES_API_KEY", "").strip():
        return None, "Original AI video generation is currently unavailable. I can find relevant existing videos instead."
    try:
        from agnes_video import start_video_job
        if persona == "tutor":
            duty = "Create a short, beginner-friendly CyberLord Academy cybersecurity education video. Focus on defensive, lawful learning and safe lab-only examples."
        else:
            duty = "Create a polished short educational or creative video for the user's general topic. Keep it accurate, suitable for a broad audience, and visually coherent."
        prompt = (
            duty + " Use the assistant answer as factual context, translate it into clear visual scenes, "
            "and avoid long blocks of on-screen text. USER REQUEST: " + str(user_text)[:1200] +
            "\nASSISTANT ANSWER: " + str(assistant_reply)[:3000]
        )
        job_id = start_video_job(prompt, owner_id=owner_id, image=image_attached)
        app.logger.info("Video job queued: persona=%s job=%s image_attached=%s", persona, job_id[:8], bool(image_attached))
        return {"job_id": job_id, "status": "queued"}, None
    except Exception as exc:
        app.logger.exception("Shared video job could not be queued: %s", str(exc)[:180])
        return None, "Original AI video generation could not be started. I can find relevant existing videos instead."


def _with_generated_images(response_payload, user_text, assistant_reply, reference_images=None, persona="main"):
    """Attach generated media and YouTube discovery to either AI persona."""
    if _video_discovery_intent(user_text):
        _attach_video_discovery(response_payload, user_text, persona)
    generated, note = _generate_images_from_answer(user_text, assistant_reply, reference_images)
    if generated:
        response_payload["generated_images"] = generated[:4]
        response_payload["image_generation"] = "complete"
    elif note:
        response_payload["image_generation_note"] = note
    generated_file, file_note = _build_generated_file(user_text, assistant_reply)
    if generated_file:
        response_payload["generated_files"] = [generated_file]
        response_payload["file_generation"] = "complete"
    elif file_note:
        response_payload["file_generation_note"] = file_note
    generated_video, video_note = _generate_video_from_answer(
        user_text, assistant_reply, reference_images,
        owner_id=(str(current_user.id) if current_user.is_authenticated else None),
        persona=persona,
    )
    if generated_video:
        response_payload["video_generation_job_id"] = generated_video["job_id"]
        response_payload["video_generation"] = "queued"
        response_payload["video_generation_note"] = "Building your video now."
        # Replace verbose model-written scene briefs and unrelated follow-up text.
        response_payload["reply"] = "Building your video now."
    elif video_note:
        response_payload["video_generation_note"] = video_note
        if _video_generation_intent(user_text):
            # Never imply a render is underway if the provider did not accept a job.
            response_payload["reply"] = str(video_note)
            _attach_video_discovery(response_payload, user_text, persona)
    return response_payload

def _send_telegram_photo(chat_id, image, caption="Generated by CyberLord"):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    try:
        raw = base64.b64decode(image["data"])
        response = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption[:900]},
            files={"photo": ("cyberlord-image.png", raw, image.get("mime_type", "image/png"))}, timeout=45)
        response.raise_for_status()
        return True
    except Exception as exc:
        app.logger.warning("Telegram image send failed: %s", str(exc)[:160])
        return False


def _send_whatsapp_photo(to, image, caption="Generated by CyberLord"):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    version = os.getenv("WHATSAPP_API_VERSION", "v26.0").strip()
    if not token or not phone_id: return False
    try:
        raw = base64.b64decode(image["data"])
        upload = requests.post(f"https://graph.facebook.com/{version}/{phone_id}/media",
            headers={"Authorization": "Bearer " + token},
            data={"messaging_product": "whatsapp", "type": image.get("mime_type", "image/png")},
            files={"file": ("cyberlord-image.png", raw, image.get("mime_type", "image/png"))}, timeout=45)
        upload.raise_for_status()
        media_id = upload.json().get("id")
        if not media_id: return False
        sent = requests.post(f"https://graph.facebook.com/{version}/{phone_id}/messages",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            json={"messaging_product":"whatsapp","to":str(to),"type":"image",
                  "image":{"id":media_id,"caption":caption[:900]}}, timeout=20)
        sent.raise_for_status()
        return True
    except Exception as exc:
        app.logger.warning("WhatsApp image send failed: %s", str(exc)[:160])
        return False


def _send_telegram_file(chat_id, item, caption="Created by CyberLord", video=False):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    method = "sendVideo" if video else "sendDocument"
    field = "video" if video else "document"
    try:
        raw = base64.b64decode(item.get("data", ""), validate=True)
        mime = item.get("mime_type") or ("video/mp4" if video else "application/octet-stream")
        filename = item.get("filename") or ("cyberlord-video.mp4" if video else "cyberlord-file")
        response = requests.post(f"https://api.telegram.org/bot{token}/{method}",
            data={"chat_id": chat_id, "caption": caption[:900]},
            files={field: (filename, raw, mime)}, timeout=90)
        response.raise_for_status(); return True
    except Exception as exc:
        app.logger.warning("Telegram media send failed: %s", str(exc)[:160]); return False


def _send_whatsapp_file(to, item, caption="Created by CyberLord", video=False):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    version = os.getenv("WHATSAPP_API_VERSION", "v26.0").strip()
    if not token or not phone_id: return False
    try:
        raw = base64.b64decode(item.get("data", ""), validate=True)
        mime = item.get("mime_type") or ("video/mp4" if video else "application/octet-stream")
        filename = item.get("filename") or ("cyberlord-video.mp4" if video else "cyberlord-file")
        upload = requests.post(f"https://graph.facebook.com/{version}/{phone_id}/media",
            headers={"Authorization": "Bearer " + token},
            data={"messaging_product": "whatsapp", "type": mime},
            files={"file": (filename, raw, mime)}, timeout=90)
        upload.raise_for_status(); media_id = upload.json().get("id")
        if not media_id: return False
        kind = "video" if video else "document"
        detail = {"id": media_id, "caption": caption[:900]}
        if not video: detail["filename"] = filename
        sent = requests.post(f"https://graph.facebook.com/{version}/{phone_id}/messages",
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": str(to), "type": kind, kind: detail}, timeout=30)
        sent.raise_for_status(); return True
    except Exception as exc:
        app.logger.warning("WhatsApp media send failed: %s", str(exc)[:160]); return False


def _image_generation_prompt(text):
    clean = (text or "").strip()
    match = re.match(
        r"(?is)^\s*(?:/image\s+|(?:please\s+)?(?:generate|create|draw|make|design)\s+(?:me\s+)?(?:an?\s+)?(?:image|picture|illustration|logo|poster|artwork)(?:\s+of|\s+for)?\s+|(?:please\s+)?(?:edit|modify|change|transform)\s+(?:this\s+)?(?:image|picture|photo)(?:\s+(?:to|into|by))?\s+)(.+)$",
        clean)
    return match.group(1).strip() if match else None


def _messaging_search_images_to_media(items, limit=4):
    """Turn image-search thumbnail URLs into validated base64 media for chat channels."""
    media_items = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        image_url = str(item.get("thumb") or item.get("thumbnail") or "")
        if not image_url.startswith("https://"):
            continue
        try:
            response = requests.get(image_url, timeout=12, headers={"User-Agent": "CyberLord/1.0"})
            response.raise_for_status()
            raw = response.content
            if not raw or len(raw) > 8 * 1024 * 1024:
                continue
            normalized = _normalize_image_for_ai(raw, response.headers.get("Content-Type", ""))
            if normalized and normalized.get("data"):
                normalized["filename"] = "cyberlord-image.jpg"
                normalized["title"] = str(item.get("title") or "Image")[:160]
                media_items.append(normalized)
        except Exception as exc:
            app.logger.warning("Messaging image result download failed: %s", str(exc)[:140])
    return media_items


def _process_messaging_event(channel, external_id, event_id, text_in="", images=None):
    """Provider-neutral CyberLord message processor.

    Platform webhooks should normalize provider payloads and call this function.
    It owns de-duplication, persona/account routing, vision analysis and image
    generation; provider adapters are responsible only for authentication,
    downloading media and delivering the returned result.

    Returns a dictionary with: duplicate, text, images, and generated.
    Images use {mime_type, data} with base64-encoded bytes.
    """
    channel = re.sub(r"[^a-z0-9_-]", "", str(channel or "").lower())[:16]
    external_id = str(external_id or "")[:180]
    event_id = str(event_id or "")[:180]
    clean = str(text_in or "").strip()[:1800]
    attached = [img for img in (images or [])[:4]
                if isinstance(img, dict)
                and img.get("mime_type") in ("image/jpeg", "image/png", "image/webp")
                and isinstance(img.get("data"), str)
                and len(img.get("data", "")) <= 7_000_000]
    if not channel or not external_id or not event_id:
        return {"duplicate": False, "text": "This message could not be processed.", "images": [], "generated": False}
    # Keep /image as an optional direct command. Natural-language image requests
    # go through the AI first so the generated picture can use its actual answer.
    generation_prompt = _image_generation_prompt(clean) if clean.lower().startswith("/image ") else None
    is_control_message = clean.startswith("/") or clean.lower() in ("tutor", "academy", "main", "dashboard", "help")
    if not is_control_message:
        if _messaging_is_duplicate(channel, event_id):
            return {"duplicate": True, "text": None, "images": [], "generated": False}

    if generation_prompt:
        generated, note = [], None
        for index in range(_requested_image_count(clean)):
            batch, current_note = _generate_image_result(
                generation_prompt + (" Create distinct variation %d." % (index + 1) if _requested_image_count(clean) > 1 else ""),
                attached if index == 0 else None,
            )
            if batch:
                generated.extend(batch[:1])
            elif not generated:
                note = current_note
                break
        return {"duplicate": False, "text": note or ("Generated %d image(s)." % len(generated)), "images": generated[:4], "generated": bool(generated)}

    # Slash commands and account-management controls keep their existing handler.
    if is_control_message:
        reply = _handle_messaging_text(channel, external_id, event_id, clean)
        return {"duplicate": reply is None, "text": reply, "images": [], "generated": False}

    row, _history = _messaging_state(channel, external_id)
    linked = _messaging_account(channel, external_id)
    question = clean or "Please analyse this picture and explain what you can see."
    reply, _updated, ai_result = _run_messaging_ai(
        channel, external_id, question, row.persona or "main",
        linked.user_id if linked else None, attached or None)
    generated = ai_result.get("generated_images") or []
    # Image-search responses use {url, thumb, title}; messaging delivery requires
    # actual image bytes. Download and validate those thumbnails before sending.
    if not generated and ai_result.get("mode") == "images":
        generated = _messaging_search_images_to_media(ai_result.get("images") or [], limit=4)
    generated_files = ai_result.get("generated_files") or []
    generated_videos = ai_result.get("generated_videos") or []
    video_job_id = ai_result.get("video_generation_job_id")
    if video_job_id and channel in ("telegram", "whatsapp"):
        def _deliver_when_ready():
            try:
                from agnes_video import wait_for_job, video_bytes
                completed = wait_for_job(video_job_id)
                media = video_bytes(video_job_id) if completed and completed.get("status") == "completed" else None
                if media:
                    raw, mime, filename = media
                    item = {"data": base64.b64encode(raw).decode("ascii"), "mime_type": mime, "filename": filename}
                    if channel == "telegram":
                        _send_telegram_file(external_id, item, "Your CyberLord video is ready.", True)
                    else:
                        _send_whatsapp_file(external_id, item, "Your CyberLord video is ready.", True)
                else:
                    error = (completed or {}).get("error") or "Agnes could not complete the video request."
                    sender = _send_telegram_message if channel == "telegram" else _send_whatsapp_message
                    sender(external_id, "CyberLord video generation failed: " + str(error)[:250])
            except Exception as exc:
                app.logger.warning("Messaging video delivery failed: %s", str(exc)[:160])
        threading.Thread(target=_deliver_when_ready, daemon=True, name="cyberlord-video-delivery").start()
    notes = [ai_result.get(k) for k in ("image_generation_note", "file_generation_note", "video_generation_note") if ai_result.get(k)]
    if ai_result.get("mode") == "images" and not generated:
        reply = "I found image results, but couldn't download them to send in this chat. Please try another search."
    if notes:
        reply = str(reply) + "\n\n" + "\n".join(str(note) for note in notes)
    return {"duplicate": False, "text": reply, "images": generated[:4],
            "files": generated_files[:2], "videos": generated_videos[:1],
            "generated": bool(generated or generated_files or generated_videos)}


def _deliver_messaging_result(result, send_text, send_image, send_file=None, send_video=None):
    """Deliver a provider-neutral result through provider-specific callbacks."""
    if not isinstance(result, dict) or result.get("duplicate"):
        return False
    delivered = False
    if result.get("text"):
        delivered = bool(send_text(result["text"])) or delivered
    for generated_image in result.get("images") or []:
        delivered = bool(send_image(generated_image, result.get("text") or "Generated by CyberLord")) or delivered
    if send_file:
        for generated_file in result.get("files") or []:
            delivered = bool(send_file(generated_file, result.get("text") or "Created by CyberLord")) or delivered
    if send_video:
        for generated_video in result.get("videos") or []:
            delivered = bool(send_video(generated_video, result.get("text") or "Generated by CyberLord")) or delivered
    return delivered


def _telegram_download_image(file_id):
    """Download and normalize a Telegram photo for the shared AI vision pipeline.

    Telegram's file endpoint may return a generic Content-Type such as
    application/octet-stream. Do not reject a valid image based only on that
    header: inspect the actual image bytes with Pillow and re-encode them.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not file_id:
        app.logger.warning("Telegram image download skipped: bot token or file_id missing")
        return None
    try:
        meta = requests.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id}, timeout=15,
        )
        meta.raise_for_status()
        payload = meta.json()
        if not payload.get("ok"):
            app.logger.warning("Telegram getFile returned not-ok: %s", str(payload)[:180])
            return None
        path = (payload.get("result") or {}).get("file_path")
        if not path:
            app.logger.warning("Telegram getFile response did not include file_path")
            return None
        media = requests.get(
            f"https://api.telegram.org/file/bot{token}/{path}", timeout=30,
        )
        media.raise_for_status()
        raw = media.content
        if not raw or len(raw) > 20 * 1024 * 1024:
            app.logger.warning("Telegram image has invalid size: %s bytes", len(raw or b""))
            return None

        # Verify the content itself, rather than trusting Telegram/proxy MIME headers.
        try:
            with Image.open(BytesIO(raw)) as candidate:
                image_format = (candidate.format or "").upper()
                candidate.verify()
        except Exception as image_exc:
            app.logger.warning(
                "Telegram attachment is not a readable image (content-type=%s): %s",
                media.headers.get("Content-Type", "unknown"), str(image_exc)[:140],
            )
            return None
        if image_format not in ("JPEG", "JPG", "PNG", "WEBP"):
            app.logger.warning("Telegram image format is not supported: %s", image_format)
            return None
        normalized = _normalize_image_for_ai(raw, "image/jpeg" if image_format in ("JPEG", "JPG") else "image/" + image_format.lower())
        if not normalized:
            app.logger.warning("Telegram image normalization returned no image (format=%s)", image_format)
        return normalized
    except Exception as exc:
        app.logger.warning("Telegram image download failed: %s", str(exc)[:180])
        return None


def _telegram_download_audio(file_id):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not file_id: return None
    try:
        meta = requests.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=12); meta.raise_for_status()
        path = (meta.json().get("result") or {}).get("file_path")
        if not path: return None
        media = requests.get(f"https://api.telegram.org/file/bot{token}/{path}", timeout=30); media.raise_for_status()
        mime = media.headers.get("Content-Type", "audio/ogg").split(";")[0].lower()
        if len(media.content) > 15 * 1024 * 1024: return None
        return media.content, mime
    except Exception as exc:
        app.logger.warning("Telegram audio download failed: %s", str(exc)[:150]); return None


def _whatsapp_download_audio(media_id):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip(); version = os.getenv("WHATSAPP_API_VERSION", "v26.0").strip()
    if not token or not media_id: return None
    try:
        meta = requests.get(f"https://graph.facebook.com/{version}/{media_id}", headers={"Authorization": "Bearer " + token}, timeout=12); meta.raise_for_status()
        media_url = meta.json().get("url")
        if not media_url: return None
        media = requests.get(media_url, headers={"Authorization": "Bearer " + token}, timeout=30); media.raise_for_status()
        mime = media.headers.get("Content-Type", "audio/ogg").split(";")[0].lower()
        if len(media.content) > 15 * 1024 * 1024: return None
        return media.content, mime
    except Exception as exc:
        app.logger.warning("WhatsApp audio download failed: %s", str(exc)[:150]); return None


def _whatsapp_download_image(media_id):
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    version = os.getenv("WHATSAPP_API_VERSION", "v26.0").strip()
    if not token or not media_id: return None
    try:
        meta = requests.get(f"https://graph.facebook.com/{version}/{media_id}", headers={"Authorization": "Bearer " + token}, timeout=12)
        meta.raise_for_status()
        media_url = meta.json().get("url")
        if not media_url: return None
        media = requests.get(media_url, headers={"Authorization": "Bearer " + token}, timeout=20)
        media.raise_for_status()
        mime = media.headers.get("Content-Type", "image/jpeg").split(";")[0].lower()
        if mime not in ("image/jpeg", "image/png", "image/webp") or len(media.content) > 20 * 1024 * 1024: return None
        return _normalize_image_for_ai(media.content, mime)
    except Exception as exc:
        app.logger.warning("WhatsApp image download failed: %s", str(exc)[:160])
        return None


@app.route("/api/channel/message", methods=["POST"])
def universal_channel_message():
    """Authenticated provider-neutral endpoint for future platform adapters.

    Sign the exact raw request body with HMAC-SHA256 using
    CYBERLORD_CHANNEL_WEBHOOK_SECRET and send X-CyberLord-Signature: sha256=<hex>.
    """
    secret = os.getenv("CYBERLORD_CHANNEL_WEBHOOK_SECRET", "").strip()
    signature = request.headers.get("X-CyberLord-Signature", "")
    if not secret:
        return jsonify(ok=False, error="Universal channel endpoint is not configured."), 503
    expected = "sha256=" + hmac.new(secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return jsonify(ok=False, error="Invalid channel signature."), 403
    body = request.get_json(silent=True) or {}
    channel = str(body.get("channel") or "")
    if channel.lower() in ("telegram", "whatsapp", "web", "dashboard", "tutor"):
        return jsonify(ok=False, error="Use the dedicated adapter for this existing channel."), 400
    result = _process_messaging_event(
        channel, body.get("external_id"), body.get("event_id"),
        body.get("text", ""), body.get("images") or [])
    return jsonify(ok=True, result=result), 200


@app.route("/webhooks/telegram", methods=["POST"])
def telegram_webhook():
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        return jsonify(ok=False, error="Webhook not configured or unauthorized"), 403
    update = request.get_json(silent=True) or {}
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text_in = message.get("text") or message.get("caption") or ""
    photos = message.get("photo") or []
    if not chat_id:
        return jsonify(ok=True, ignored=True)
    image = None
    voice = message.get("voice") or message.get("audio")
    if voice:
        downloaded = _telegram_download_audio(voice.get("file_id"))
        if not downloaded:
            _send_telegram_message(chat_id, "I could not download that voice note. Please try a shorter OGG, MP3 or M4A recording.")
            return jsonify(ok=True)
        raw_audio, audio_mime = downloaded
        try:
            transcript = _gemini_transcribe_audio_bytes(raw_audio, audio_mime)
        except Exception as exc:
            app.logger.warning("Telegram voice transcription failed: %s", str(exc)[:150]); transcript = None
        if not transcript:
            _send_telegram_message(chat_id, "I could not transcribe that voice note. Please try again or send text.")
            return jsonify(ok=True)
        text_in = (text_in + "\n" + transcript).strip()
    if photos:
        image = _telegram_download_image(photos[-1].get("file_id"))
        if not image:
            _send_telegram_message(chat_id, "I couldn't read that image. Please send a JPG, PNG or WEBP image up to 20 MB.")
            return jsonify(ok=True)
    event_id = str(chat_id) + ":" + str(message.get("message_id"))
    result = _process_messaging_event("telegram", chat_id, event_id, text_in, [image] if image else None)
    _deliver_messaging_result(result,
        lambda text: _send_telegram_message(chat_id, text),
        lambda img, caption: _send_telegram_photo(chat_id, img, caption),
        lambda item, caption: _send_telegram_file(chat_id, item, caption, False),
        lambda item, caption: _send_telegram_file(chat_id, item, caption, True))
    return jsonify(ok=True)


@app.route("/webhooks/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    if request.method == "GET":
        mode = request.args.get("hub.mode", "")
        token = request.args.get("hub.verify_token", "")
        challenge = request.args.get("hub.challenge", "")
        if verify_token and mode == "subscribe" and hmac.compare_digest(token, verify_token):
            return challenge, 200, {"Content-Type": "text/plain"}
        return "Webhook verification failed", 403
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    if not app_secret:
        return jsonify(ok=False, error="WhatsApp webhook signature verification is not configured"), 503
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(app_secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return jsonify(ok=False, error="Invalid signature"), 403
    payload = request.get_json(silent=True) or {}
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            for message in value.get("messages", []):
                sender = message.get("from")
                msg_type = message.get("type")
                text_in = ((message.get("text") or {}).get("body") or
                           (message.get("image") or {}).get("caption") or "")
                if not sender:
                    continue
                if msg_type == "audio":
                    downloaded = _whatsapp_download_audio((message.get("audio") or {}).get("id"))
                    if not downloaded:
                        _send_whatsapp_message(sender, "I could not download that voice note. Please try a shorter supported audio recording.")
                        continue
                    raw_audio, audio_mime = downloaded
                    try:
                        transcript = _gemini_transcribe_audio_bytes(raw_audio, audio_mime)
                    except Exception as exc:
                        app.logger.warning("WhatsApp voice transcription failed: %s", str(exc)[:150]); transcript = None
                    if not transcript:
                        _send_whatsapp_message(sender, "I could not transcribe that voice note. Please try again or send text.")
                        continue
                    result = _process_messaging_event("whatsapp", sender, message.get("id"), transcript)
                    _deliver_messaging_result(result,
                        lambda text: _send_whatsapp_message(sender, text),
                        lambda img, caption: _send_whatsapp_photo(sender, img, caption),
                        lambda item, caption: _send_whatsapp_file(sender, item, caption, False),
                        lambda item, caption: _send_whatsapp_file(sender, item, caption, True))
                elif msg_type == "image":
                    image = _whatsapp_download_image((message.get("image") or {}).get("id"))
                    if not image:
                        _send_whatsapp_message(sender, "I couldn't read that image. Please send a JPG, PNG or WEBP image up to 20 MB.")
                        continue
                    result = _process_messaging_event("whatsapp", sender, message.get("id"), text_in, [image])
                    _deliver_messaging_result(result,
                        lambda text: _send_whatsapp_message(sender, text),
                        lambda img, caption: _send_whatsapp_photo(sender, img, caption),
                        lambda item, caption: _send_whatsapp_file(sender, item, caption, False),
                        lambda item, caption: _send_whatsapp_file(sender, item, caption, True))
                elif msg_type == "text" and text_in.strip():
                    result = _process_messaging_event("whatsapp", sender, message.get("id"), text_in)
                    _deliver_messaging_result(result,
                        lambda text: _send_whatsapp_message(sender, text),
                        lambda img, caption: _send_whatsapp_photo(sender, img, caption),
                        lambda item, caption: _send_whatsapp_file(sender, item, caption, False),
                        lambda item, caption: _send_whatsapp_file(sender, item, caption, True))
    return jsonify(ok=True)


def monitoring_limits(user):
    refresh_subscription(user)
    rank = PLANS.get(user.plan, PLANS["free"])["rank"]
    if rank < 1:
        return 0, None
    return (1, 24) if rank == 1 else (5, 6)

def send_monitoring_email(to_email, subject, body):
    api_key, sender = os.getenv("RESEND_API_KEY", ""), os.getenv("RESEND_FROM", "")
    if not api_key or not sender:
        return False
    try:
        response = requests.post("https://api.resend.com/emails",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            json={"from": sender, "to": [to_email], "subject": subject, "text": body}, timeout=15)
        response.raise_for_status()
        return True
    except Exception:
        app.logger.exception("Monitoring email delivery failed")
        return False

@app.route("/monitoring", methods=["GET", "POST"])
@login_required
def monitoring():
    limit, interval_hours = monitoring_limits(current_user)
    if request.method == "POST":
        if limit == 0:
            flash("Automated monitoring requires PRO or PRO PLUS.", "warning")
            return redirect(url_for("dashboard") + "#plans")
        try:
            domain = normalize_domain(request.form.get("domain", ""))
            existing = MonitoredDomain.query.filter_by(user_id=current_user.id, domain=domain).first()
            if existing:
                flash("That domain is already in your monitoring list.", "warning")
            else:
                count = MonitoredDomain.query.filter_by(user_id=current_user.id).count()
                if count >= limit:
                    flash(f"Your {PLANS[current_user.plan]['name']} plan allows {limit} monitored domain(s).", "warning")
                else:
                    token = "cyberlord-verify=" + secrets.token_urlsafe(24)
                    db.session.add(MonitoredDomain(user_id=current_user.id, domain=domain,
                        verification_token=token, verified=False, enabled=True))
                    db.session.commit()
                    flash("Domain added. Publish the DNS TXT record shown below, then verify ownership.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    items = MonitoredDomain.query.filter_by(user_id=current_user.id).order_by(MonitoredDomain.created_at.desc()).all()
    alerts = MonitoringAlert.query.filter_by(user_id=current_user.id).order_by(MonitoringAlert.created_at.desc()).limit(30).all()
    return render_template("monitoring.html", items=items, alerts=alerts, limit=limit,
        interval_hours=interval_hours, plan_name=PLANS.get(current_user.plan, PLANS["free"])["name"])

@app.route("/monitoring/<int:item_id>/verify", methods=["POST"])
@login_required
def verify_monitored_domain(item_id):
    item = MonitoredDomain.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    try:
        answers = dns.resolver.resolve("_cyberlord-verification." + item.domain, "TXT", lifetime=5)
        found = any(item.verification_token in "".join(
            part.decode() if isinstance(part, bytes) else str(part) for part in answer.strings
        ) for answer in answers)
        if not found:
            flash("Verification TXT record was not found. Check the record name and value, then retry.", "warning")
        else:
            item.verified = True
            item.last_status = "verified_waiting_for_first_check"
            item.next_check_at = datetime.utcnow()
            db.session.commit()
            flash("Domain ownership verified. Scheduled monitoring is enabled.", "success")
    except Exception:
        flash("Could not verify the TXT record yet. DNS may need time to propagate.", "warning")
    return redirect(url_for("monitoring"))

@app.route("/monitoring/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_monitored_domain(item_id):
    item = MonitoredDomain.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    MonitoringAlert.query.filter_by(monitored_domain_id=item.id, user_id=current_user.id).delete()
    db.session.delete(item)
    db.session.commit()
    flash("Domain removed from monitoring.", "success")
    return redirect(url_for("monitoring"))

@app.route("/monitoring/alerts/<int:alert_id>/read", methods=["POST"])
@login_required
def read_monitoring_alert(alert_id):
    alert = MonitoringAlert.query.filter_by(id=alert_id, user_id=current_user.id).first_or_404()
    alert.read_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("monitoring") + "#alerts")


def monitoring_snapshot(domain):
    """Collect passive DNS and TLS observations only; no port scan, exploit, or redirect following."""
    addresses = public_domain_addresses(domain)
    snapshot = {"target": domain, "dns": {}, "tls": None}
    for record in ("A", "AAAA", "MX", "NS", "TXT", "CAA"):
        snapshot["dns"][record] = dns_records(domain, record)
    snapshot["resolved_public_addresses"] = addresses
    try:
        snapshot["tls"] = tls_details(domain)
    except Exception as exc:
        snapshot["tls"] = {"status": "not_verified", "reason": str(exc)[:160]}
    return snapshot

def monitoring_fingerprint(scan_result):
    normalized = json.loads(json.dumps(scan_result, default=str))
    normalized.pop("checked_at", None)
    evidence = normalized.get("evidence", {})
    if isinstance(evidence.get("tls"), dict):
        evidence["tls"].pop("days_until_expiry", None)
    if isinstance(evidence.get("http"), dict):
        evidence["http"].pop("html_sample_length", None)
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

def run_due_monitoring_checks(batch_size=10):
    now = datetime.utcnow()
    due = MonitoredDomain.query.filter_by(verified=True, enabled=True).filter(
        or_(MonitoredDomain.next_check_at.is_(None), MonitoredDomain.next_check_at <= now)
    ).order_by(MonitoredDomain.next_check_at.asc()).limit(batch_size).all()
    for item in due:
        user = db.session.get(User, item.user_id)
        if not user:
            item.enabled = False
            continue
        allowance, interval_hours = monitoring_limits(user)
        if allowance == 0:
            item.enabled = False
            item.last_status = "plan_expired"
            db.session.commit()
            continue
        active_domains = MonitoredDomain.query.filter_by(user_id=user.id, verified=True, enabled=True).order_by(MonitoredDomain.created_at.asc(), MonitoredDomain.id.asc()).all()
        allowed_ids = {domain_row.id for domain_row in active_domains[:allowance]}
        if item.id not in allowed_ids:
            item.enabled = False
            item.last_status = "plan_limit_exceeded"
            db.session.commit()
            continue
        try:
            result = monitoring_snapshot(item.domain)
            fingerprint = monitoring_fingerprint(result)
            old = item.last_fingerprint
            item.last_fingerprint = fingerprint
            item.last_checked_at = now
            item.next_check_at = now + timedelta(hours=interval_hours)
            item.last_status = "checked" if result.get("tls", {}).get("status") == "verified" else "checked_with_warnings"
            if old and old != fingerprint:
                alert = MonitoringAlert(user_id=user.id, monitored_domain_id=item.id,
                    domain=item.domain, title="Public security configuration changed",
                    detail="CyberLord observed a change in DNS, TLS or HTTP security data. Review the latest Domain Security Scan and compare it with previous results. A change alone does not prove an attack.",
                    severity="medium")
                db.session.add(alert)
                db.session.flush()
                send_monitoring_email(user.email, "CyberLord monitoring alert: " + item.domain,
                    alert.title + "\n" + alert.detail)
            db.session.commit()
        except Exception as exc:
            app.logger.warning("Scheduled monitoring failed for %s: %s", item.domain, str(exc)[:180])
            item.last_checked_at = now
            item.next_check_at = now + timedelta(hours=min(interval_hours, 6))
            item.last_status = "check_failed"
            db.session.commit()



# ---------------------------------------------------------------------------
# CyberLord Advanced Intelligence: passive, public-data investigations
# ---------------------------------------------------------------------------
ADVANCED_TOOLS = {
    "footprint": "Digital Footprint Investigator",
    "api_hunter": "Shadow API Hunter",
    "impersonation": "Website Impersonation Detector",
}

class _PublicPageParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.title_parts=[]; self.in_title=False; self.scripts=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag.lower()=="title": self.in_title=True
        if tag.lower()=="script" and a.get("src"): self.scripts.append(a["src"])
        if tag.lower()=="a" and a.get("href"): self.links.append(a["href"])
    def handle_endtag(self, tag):
        if tag.lower()=="title": self.in_title=False
    def handle_data(self, data):
        if self.in_title and data.strip(): self.title_parts.append(data.strip())

def _safe_public_fetch(domain, path="/"):
    """Fetch one public HTTPS resource without following redirects."""
    addresses=public_domain_addresses(domain)
    url="https://"+domain+path
    try:
        r=requests.get(url, timeout=6, allow_redirects=False, stream=True,
            headers={"User-Agent":"CyberLord-Defensive-Intelligence/1.0"})
        body=r.raw.read(180000, decode_content=True).decode(r.encoding or "utf-8", errors="replace")
        return r, body, addresses
    except requests.RequestException as exc:
        return None, "", addresses

def _passive_footprint(domain):
    addresses=public_domain_addresses(domain)
    records={kind:dns_records(domain,kind) for kind in ("A","AAAA","MX","NS","TXT","CAA")}
    tls={"checked":False,"issuer":"Not inspected by this passive module"}
    try:
        r, body, resolved=_safe_public_fetch(domain)
        page={"http_status":r.status_code if r else None,
              "server_header":(r.headers.get("Server") if r else None),
              "security_headers":({h:r.headers.get(h) for h in ("strict-transport-security","content-security-policy","x-content-type-options","x-frame-options","referrer-policy") if r.headers.get(h)} if r else {}),
              "redirect_location":(r.headers.get("Location") if r else None)}
    except Exception as exc:
        page={"warning":str(exc)}
    certs=[]
    try:
        q=requests.get("https://crt.sh/",params={"q":"%."+domain,"output":"json"},timeout=8,headers={"User-Agent":"CyberLord-Defensive-Intelligence/1.0"})
        if q.ok:
            seen=set()
            for row in q.json()[:250]:
                for name in str(row.get("name_value","")).splitlines():
                    name=name.strip().lower().lstrip("*.")
                    if name.endswith("."+domain) and name not in seen:
                        seen.add(name); certs.append(name)
            certs=sorted(certs)[:100]
    except Exception: pass
    return {"domain":domain,"resolved_ips":addresses,"dns_records":records,"certificate_transparency_subdomains":certs,
            "http_observation":page,"scope_note":"Passive public DNS, certificate-transparency and one-page HTTP observations only. No port scan or exploitation was performed."}

def _shadow_api_hunt(domain):
    r, body, addresses=_safe_public_fetch(domain)
    if not r:
        raise ValueError("The public HTTPS page could not be fetched. Check the domain and try again.")
    parser=_PublicPageParser(); parser.feed(body)
    base="https://"+domain
    candidates=["/openapi.json","/swagger.json","/api-docs","/api-docs/","/swagger/","/swagger-ui/","/docs","/openapi.yaml","/graphql","/.well-known/openapi.json"]
    found=[]
    for path in candidates:
        try:
            rr, content, _=_safe_public_fetch(domain,path)
            if rr and rr.status_code in (200,401,403) and (path in ("/graphql",) or "openapi" in path or "swagger" in path or "graphql" in content[:3000].lower() or "swagger" in content[:3000].lower()):
                found.append({"path":path,"status":rr.status_code,"content_type":rr.headers.get("Content-Type","unknown"),"note":"Endpoint responds; authentication and authorization were not tested."})
        except Exception: pass
    js_assets=[]
    for src in parser.scripts[:25]:
        if src.startswith("//"): continue
        if src.startswith("/"): js_assets.append(base+src)
        elif src.startswith("http://") or src.startswith("https://"): continue
        else: js_assets.append(base+"/"+src.lstrip("./"))
    api_hints=set()
    # Report route-like strings only; never return token/secret values.
    import re as _re
    for match in _re.findall(r"[\"']((?:/api/|/v[0-9]+/)[A-Za-z0-9_./{}?=&-]{1,120})[\"']",body): api_hints.add(match[:120])
    for asset in js_assets[:12]:
        try:
            u=urlparse(asset)
            if u.hostname!=domain: continue
            rr=requests.get(asset,timeout=5,allow_redirects=False,headers={"User-Agent":"CyberLord-Defensive-Intelligence/1.0"})
            if rr.ok:
                for match in _re.findall(r"[\"']((?:/api/|/v[0-9]+/)[A-Za-z0-9_./{}?=&-]{1,120})[\"']",rr.text[:250000]): api_hints.add(match[:120])
        except requests.RequestException: pass
    return {"domain":domain,"resolved_ips":addresses,"page_title":" ".join(parser.title_parts)[:180],
            "api_documentation_or_routes":found,"public_javascript_assets":js_assets[:25],"route_hints_from_public_code":sorted(api_hints)[:80],
            "scope_note":"Passive checks of public pages and common documentation paths. No authentication bypass, fuzzing, data access or exploit attempts."}

def _impersonation_candidates(domain):
    import itertools
    # Treat the first DNS label as the brand, preserving multi-part suffixes such as name.ng.
    parts=domain.split(".")
    root=parts[0]
    suffix=".".join(parts[1:])
    variants=set()
    for i in range(len(root)):
        variants.add(root[:i]+root[i+1:])
        if i+1<len(root): variants.add(root[:i]+root[i+1]+root[i]+root[i+2:])
    for ch in "abcdefghijklmnopqrstuvwxyz0123456789":
        variants.add(root+ch); variants.add(ch+root)
    for old,new in (("o","0"),("i","1"),("l","1"),("e","3"),("a","4")):
        if old in root: variants.add(root.replace(old,new,1))
    candidates=[]
    for v in sorted(variants):
        if v and v!=root and len(v)<=63 and re.fullmatch(r"[a-z0-9-]+",v):
            candidates.append(v+"."+suffix)
    results=[]
    for candidate in candidates[:35]:
        try:
            ips=public_domain_addresses(candidate)
            results.append({"domain":candidate,"dns_resolves":True,"public_ips":ips,"name_similarity":round(SequenceMatcher(None,domain,candidate).ratio(),3),"risk":"Review"})
        except Exception:
            results.append({"domain":candidate,"dns_resolves":False,"public_ips":[],"name_similarity":round(SequenceMatcher(None,domain,candidate).ratio(),3),"risk":"No DNS response observed"})
    results.sort(key=lambda x:(not x["dns_resolves"],-x["name_similarity"]))
    return {"brand_domain":domain,"lookalike_candidates_checked":len(results),"potentially_registered_candidates":[x for x in results if x["dns_resolves"]],
            "all_candidates":results,"scope_note":"Heuristic typo candidates checked through public DNS only. DNS resolution does not prove malicious intent, brand ownership or impersonation."}

@app.route("/advanced-intelligence", methods=["GET"])
@login_required
def advanced_intelligence():
    refresh_subscription(current_user)
    unlocked=PLANS.get(current_user.plan,PLANS["free"])["rank"]>=2
    return render_template("advanced_intelligence.html", tools=ADVANCED_TOOLS, unlocked=unlocked, plans=PLANS)

@app.route("/advanced-intelligence/<tool>", methods=["POST"])
@login_required
def run_advanced_intelligence(tool):
    if tool not in ADVANCED_TOOLS: abort(404)
    if not allowed_tool("attack_surface"):
        return jsonify(ok=False,error="These advanced investigations require PRO PLUS."),403
    limit_resp = _check_rate("scan", request.endpoint or tool)
    if limit_resp is not None: return limit_resp
    if request.form.get("authorized")!="yes":
        return jsonify(ok=False,error="Confirm that you own this domain or have permission to investigate it."),400
    try:
        domain=normalize_domain(form_str("domain", 254))
        if tool=="footprint": result=_passive_footprint(domain)

        elif tool=="api_hunter": result=_shadow_api_hunt(domain)
        else: result=_impersonation_candidates(domain)
        save_scan("advanced_"+tool,domain,result)
        return jsonify(ok=True,tool=ADVANCED_TOOLS[tool],target=domain,result=result)
    except (ValueError, requests.RequestException) as exc:
        return jsonify(ok=False,error=str(exc)),400
    except Exception:
        app.logger.exception("Advanced intelligence module failed")
        return jsonify(ok=False,error="The investigation could not be completed. Please try again later."),500


# ---------------------------------------------------------------------------
# Academy Training Terminal + Code Lab (Tutor Pro)
#
# Safety model (deliberate, keep it this way):
# * Terminal: strict whitelist executor. No shell, no subprocess, no real
#   network, no real filesystem. Every command is parsed and answered from a
#   fixed in-memory practice-lab model. Unknown / hostile input is rejected.
#   The only "targets" are the built-in lab hosts; any other host is refused.
# * Code Lab: small Python snippets only, run in a separate child process
#   with a hard timeout, CPU/RLIMIT, no network (socket blocked), and the
#   working directory is an empty temp dir that is deleted afterwards.
#   Forbidden modules / attributes are blocked before execution by an AST
#   check, and the child also installs a blocked-import guard.
# ---------------------------------------------------------------------------
import ast as _ast
import resource as _resource
import sys as _sys
import tempfile as _tempfile

# NOTE: The Academy Training Terminal is now a REAL in-browser terminal.
# Its command execution happens entirely in the visitor's browser (xterm.js
# shell + Pyodide Python + in-browser virtual filesystem), so the server
# NEVER receives or executes user shell commands. The old server-side
# whitelist simulator (/api/terminal/run -> terminal_execute) has been
# removed entirely: no request path lets user input reach a server shell,
# subprocess, or the real filesystem. See TERMINAL_SETUP.md.

@app.route("/academy/terminal")
@login_required
def academy_terminal():
    return render_template("terminal.html", tutor_pro=tutor_pro_active(current_user))


# --- Code Lab: sandboxed Python snippets (Tutor Pro) ---

CODE_LAB_MAX_CHARS = 4000
CODE_LAB_TIMEOUT = 5
_CODE_FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "socket", "ctypes", "importlib", "pathlib",
    "shutil", "pty", "multiprocessing", "threading", "requests", "urllib",
    "http", "ftplib", "telnetlib", "webbrowser", "runpy", "inspect",
    "builtins", "pkgutil", "code", "codeop",
}
_CODE_FORBIDDEN_ATTRS = {
    "system", "popen", "exec", "eval", "open", "compile", "__import__",
    "fork", "spawn", "execv", "execve", "kill", "remove", "unlink", "rmdir",
    "mkdir", "makedirs", "rename", "chmod", "chown", "symlink", "link",
    "socket", "connect", "urlopen", "request", "getattr",
}


def _code_lab_check(source):
    """AST screen. Returns (ok, reason)."""
    if len(source) > CODE_LAB_MAX_CHARS:
        return False, "Code too long (max %d characters)." % CODE_LAB_MAX_CHARS
    try:
        tree = _ast.parse(source)
    except SyntaxError as e:
        return False, "Syntax error: %s" % e
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                if root in _CODE_FORBIDDEN_MODULES:
                    return False, "Import of '%s' is not allowed in the Code Lab." % root
        elif isinstance(node, _ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _CODE_FORBIDDEN_MODULES:
                return False, "Import of '%s' is not allowed in the Code Lab." % root
        elif isinstance(node, _ast.Attribute):
            if node.attr in _CODE_FORBIDDEN_ATTRS or node.attr.startswith("__"):
                return False, "Use of '%s' is not allowed in the Code Lab." % node.attr
        elif isinstance(node, _ast.Name):
            if node.id in _CODE_FORBIDDEN_ATTRS or node.id in ("__import__", "eval", "exec", "open", "compile"):
                return False, "Use of '%s' is not allowed in the Code Lab." % node.id
        elif isinstance(node, _ast.Constant) and isinstance(node.value, str):
            low = node.value.lower()
            if "os.system" in low or "subprocess" in low or "__import__" in low:
                return False, "That pattern is not allowed in the Code Lab."
    return True, ""


_CHILD = (
    "import builtins, sys, os, resource\n"
    "resource.setrlimit(resource.RLIMIT_CPU, (5, 5))\n"
    "resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))\n"
    "resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))\n"
    "resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))\n"
    "try:\n"
    "    import socket\n"
    "    socket.socket = None\n"
    "    socket.create_connection = None\n"
    "except Exception:\n"
    "    pass\n"
    "_blocked = {'os', 'sys', 'subprocess', 'socket', 'ctypes', 'importlib', 'pathlib', 'shutil', 'requests', 'urllib', 'http', 'multiprocessing', 'pty'}\n"
    "_real_import = builtins.__import__\n"
    "_real_open = builtins.open\n"
    "_real_compile = builtins.compile\n"
    "_real_print = builtins.print\n"
    "def _guard(name, *a, **k):\n"
    "    root = name.split('.')[0] if name else ''\n"
    "    if root in _blocked:\n"
    "        raise ImportError('blocked in Code Lab sandbox: ' + root)\n"
    "    return _real_import(name, *a, **k)\n"
    "os.chdir(os.environ.get('CODE_LAB_CWD', '.'))\n"
    "with _real_open('snippet.py', 'r') as _f:\n"
    "    _src = _f.read()\n"
    "_b = dict(vars(builtins))\n"
    "_b['__import__'] = _guard\n"
    "_b['open'] = None\n"
    "_b['eval'] = None\n"
    "_b['exec'] = None\n"
    "_b['compile'] = None\n"
    "_b['print'] = _real_print\n"
    "try:\n"
    "    _code = _real_compile(_src, 'snippet.py', 'exec')\n"
    "    exec(_code, {'__builtins__': _b, '__name__': '__main__'})\n"
    "except Exception as _e:\n"
    "    _real_print('Error: %s: %s' % (type(_e).__name__, _e))\n"
)


def run_sandboxed_code(source):
    """Run a snippet in a child process. Returns (stdout, stderr, timed_out)."""
    ok, reason = _code_lab_check(source)
    if not ok:
        return "", reason, False
    with _tempfile.TemporaryDirectory(prefix="codelab-") as td:
        with open(os.path.join(td, "snippet.py"), "w") as f:
            f.write(source)
        env = {"PATH": "/usr/bin:/bin", "CODE_LAB_CWD": td, "PYTHONNOUSERSITE": "1"}
        try:
            proc = subprocess.run(
                [_sys.executable, "-I", "-c", _CHILD],
                cwd=td, env=env, capture_output=True, text=True,
                timeout=CODE_LAB_TIMEOUT,
            )
            out = (proc.stdout or "")[:4000]
            err = (proc.stderr or "")[:2000]
            return out, err, False
        except subprocess.TimeoutExpired:
            return "Timed out after %d seconds. The Code Lab sandbox stopped your code." % CODE_LAB_TIMEOUT, "", True


@app.route("/code-lab")
@login_required
def code_lab():
    return render_template("code_lab.html", tutor_pro=tutor_pro_active(current_user))


@app.route("/api/code-lab/run", methods=["POST"])
@login_required
def code_lab_run():
    if not tutor_pro_active(current_user):
        return jsonify(ok=False, error="Code Lab is a Tutor Pro feature. Upgrade to Tutor Pro for unlimited tutor questions, voice, and Code Lab access.", tutor_pro=False, upgrade_url=url_for("dashboard") + "#plans"), 403
    if rate_limited(key="codelab:" + client_ip() + ":" + str(current_user.id), limit=20, window=60):
        return jsonify(ok=False, error="Too many Code Lab runs. Wait a moment and try again."), 429
    body = request.get_json(silent=True) or {}
    source = str(body.get("code") or "")
    if not source.strip():
        return jsonify(ok=False, error="Paste some Python code first."), 400
    out, err, timed_out = run_sandboxed_code(source)
    return jsonify(ok=True, output=out, stderr=err, timed_out=timed_out)


@app.route("/super-mode")
@login_required
def super_mode():
    # Legacy URL: all capabilities now live in the normal CyberLord AI chat.
    return redirect(url_for("dashboard"))


def _super_mode_gemini(prompt, content, timeout=35):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None, "AI document analysis needs GEMINI_API_KEY configured in Render Environment."
    model = _gemini_model()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"system_instruction": {"parts": [{"text": "You are CyberLord Super Mode. Analyse only the supplied content. Do not invent missing facts. Quote or identify the relevant section when possible. State uncertainty clearly."}]},
               "contents": [{"role": "user", "parts": [{"text": (prompt + "\n\nSOURCE CONTENT:\n" + content)[:36000]}]}],
               "generationConfig": {"temperature": 0.2}}
    try:
        response = requests.post(endpoint, params={"key": key}, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        answer = "".join(part.get("text", "") for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []) if isinstance(part, dict))
        return (answer.strip() or None), (None if answer.strip() else "The AI provider returned no analysis.")
    except Exception as exc:
        app.logger.warning("Super Mode Gemini request failed: %s", str(exc)[:180])
        return None, "AI analysis is temporarily unavailable. Check Gemini access, quota and Render logs."


def _super_mode_gemini_media(prompt, raw, mime, timeout=90):
    """Analyse an uploaded PDF/video using Gemini's multimodal inline input."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None, "This feature needs GEMINI_API_KEY configured in Render."
    if not raw or len(raw) > 20 * 1024 * 1024:
        return None, "Media uploads must be under 20 MB."
    model = _gemini_model()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"system_instruction": {"parts": [{"text": "You are CyberLord. Describe only what is supported by the supplied media. For OCR, preserve exact wording and mark uncertain characters. For video, distinguish visible events from inference and do not invent timestamps."}]},
               "contents": [{"role": "user", "parts": [{"text": prompt}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode("ascii")}}]},],
               "generationConfig": {"temperature": 0.1}}
    try:
        response = requests.post(endpoint, params={"key": key}, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        answer = "".join(part.get("text", "") for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []) if isinstance(part, dict)).strip()
        return (answer or None), (None if answer else "The AI provider returned no media analysis.")
    except Exception as exc:
        app.logger.warning("Super Mode media analysis failed: %s", str(exc)[:180])
        return None, "Media analysis failed. Check Gemini model access, quota and Render logs."


def _gemini_transcribe_audio_bytes(raw, mime):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key: return None
    model = os.getenv("GEMINI_AUDIO_MODEL", _gemini_model()).strip()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"contents": [{"role": "user", "parts": [
        {"text": "Transcribe this audio accurately in its original language. Return only spoken words. Mark unclear speech rather than guessing."},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode("ascii")}}
    ]}], "generationConfig": {"temperature": 0.1}}
    response = requests.post(endpoint, params={"key": key}, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    result = "".join(x.get("text", "") for x in data.get("candidates", [{}])[0].get("content", {}).get("parts", []) if isinstance(x, dict)).strip()
    return result or None


def _gemini_speech_bytes(text):
    """Generate spoken reply audio where the configured Gemini model supports TTS."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key: return None
    model = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts").strip()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"contents": [{"parts": [{"text": "Speak clearly and naturally: " + str(text or "")[:3500]}]}],
               "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": os.getenv("GEMINI_TTS_VOICE", "Kore")}}}}}
    try:
        r = requests.post(endpoint, params={"key": key}, json=payload, timeout=60); r.raise_for_status()
        parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "audio/L16;rate=24000"
                raw = base64.b64decode(inline["data"])
                if "L16" in mime or "pcm" in mime.lower():
                    wav_out = BytesIO()
                    with wave.open(wav_out, "wb") as wav_file:
                        wav_file.setnchannels(1); wav_file.setsampwidth(2); wav_file.setframerate(24000); wav_file.writeframes(raw)
                    raw = wav_out.getvalue(); mime = "audio/wav"
                return {"data": base64.b64encode(raw).decode("ascii"), "mime_type": mime}
    except Exception as exc:
        app.logger.warning("Gemini speech generation unavailable: %s", str(exc)[:160])
    return None


@app.route("/api/large-upload/initiate", methods=["POST"])
@login_required
def large_upload_initiate():
    body = request.get_json(silent=True) or {}
    filename = os.path.basename(str(body.get("filename") or "upload"))[:180]
    mime = str(body.get("mime_type") or "application/octet-stream").split(";")[0].lower()
    try:
        size = int(body.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if size <= 0 or size > CYBERLORD_LARGE_FILE_MAX_BYTES:
        return jsonify(error=f"File must be between 1 byte and {CYBERLORD_LARGE_FILE_MAX_BYTES // (1024**3)} GB."), 400
    if not _large_upload_allowed(filename, mime):
        return jsonify(error="Supported files: MP4, MOV, WEBM, MPEG, PDF, JPG, PNG, WEBP, MP3, WAV, M4A, OGG, DOCX, XLSX, PPTX, TXT, MD and CSV."), 400
    if os.path.splitext(filename)[1].lower() in {".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv"} and size > 50 * 1024 * 1024:
        return jsonify(error="Office and text documents are limited to 50 MB. Video, audio, PDF and image files may use the configured 2 GB limit where provider limits permit."), 400
    s3 = _large_upload_s3()
    if not s3:
        return jsonify(error="File uploads are temporarily unavailable. Please try again later."), 503
    key = f"private-user-uploads/{current_user.id}/{secrets.token_urlsafe(24)}-{re.sub(r'[^A-Za-z0-9._-]', '_', filename)}"
    try:
        result = s3.create_multipart_upload(Bucket=_large_upload_bucket(), Key=key, ContentType=mime,
                                            Metadata={"owner": str(current_user.id), "original-size": str(size)})
        return jsonify(ok=True, key=key, upload_id=result["UploadId"], part_size=CYBERLORD_MULTIPART_PART_BYTES,
                       max_bytes=CYBERLORD_LARGE_FILE_MAX_BYTES)
    except Exception as exc:
        app.logger.warning("B2 multipart initiation failed: %s", str(exc)[:160])
        return jsonify(error="Could not start the secure upload. Please try again later."), 503


@app.route("/api/large-upload/sign-part", methods=["POST"])
@login_required
def large_upload_sign_part():
    body = request.get_json(silent=True) or {}
    key, upload_id = str(body.get("key") or ""), str(body.get("upload_id") or "")
    try: part = int(body.get("part_number"))
    except (TypeError, ValueError): part = 0
    if not key.startswith(f"private-user-uploads/{current_user.id}/") or not upload_id or not 1 <= part <= 150:
        return jsonify(error="Invalid upload part."), 400
    s3 = _large_upload_s3()
    if not s3: return jsonify(error="File upload service is temporarily unavailable."), 503
    try:
        url = s3.generate_presigned_url("upload_part", Params={"Bucket": _large_upload_bucket(), "Key": key,
            "UploadId": upload_id, "PartNumber": part}, ExpiresIn=3600)
        return jsonify(ok=True, url=url)
    except Exception as exc:
        app.logger.warning("B2 part signing failed: %s", str(exc)[:160])
        return jsonify(error="Could not prepare this upload part."), 503


@app.route("/api/large-upload/list-parts", methods=["POST"])
@login_required
def large_upload_list_parts():
    """Return completed part receipts so the browser can resume after reload."""
    body = request.get_json(silent=True) or {}
    key, upload_id = str(body.get("key") or ""), str(body.get("upload_id") or "")
    if not key.startswith(f"private-user-uploads/{current_user.id}/") or not upload_id:
        return jsonify(error="Invalid upload session."), 400
    s3 = _large_upload_s3()
    if not s3: return jsonify(error="File upload service is temporarily unavailable."), 503
    try:
        response = s3.list_parts(Bucket=_large_upload_bucket(), Key=key, UploadId=upload_id, MaxParts=1000)
        parts = [{"PartNumber": int(p["PartNumber"]), "ETag": str(p["ETag"])} for p in response.get("Parts", [])]
        return jsonify(ok=True, parts=parts)
    except Exception as exc:
        app.logger.warning("Multipart resume lookup failed: %s", str(exc)[:140])
        return jsonify(error="This upload session cannot be resumed. Start a new upload."), 404


@app.route("/api/large-upload/complete", methods=["POST"])
@login_required
def large_upload_complete():
    body = request.get_json(silent=True) or {}
    key, upload_id = str(body.get("key") or ""), str(body.get("upload_id") or "")
    parts = body.get("parts") or []
    if not key.startswith(f"private-user-uploads/{current_user.id}/") or not upload_id or not isinstance(parts, list) or not parts:
        return jsonify(error="Invalid multipart completion request."), 400
    try:
        clean = [{"PartNumber": int(x["PartNumber"]), "ETag": str(x["ETag"])} for x in parts]
        if len(clean) > 150 or any(not x["ETag"] for x in clean): raise ValueError("invalid parts")
        clean.sort(key=lambda x: x["PartNumber"])
        if [x["PartNumber"] for x in clean] != list(range(1, len(clean) + 1)):
            raise ValueError("multipart parts must be consecutive")
        s3 = _large_upload_s3()
        if not s3: return jsonify(error="File upload service is temporarily unavailable."), 503
        s3.complete_multipart_upload(Bucket=_large_upload_bucket(), Key=key, UploadId=upload_id,
                                     MultipartUpload={"Parts": clean})
        head = s3.head_object(Bucket=_large_upload_bucket(), Key=key)
        if int(head.get("ContentLength", 0)) > CYBERLORD_LARGE_FILE_MAX_BYTES:
            s3.delete_object(Bucket=_large_upload_bucket(), Key=key)
            return jsonify(error="The completed file exceeds the configured limit."), 400
        return jsonify(ok=True, key=key, size=head.get("ContentLength", 0))
    except Exception as exc:
        app.logger.warning("B2 multipart completion failed: %s", str(exc)[:160])
        return jsonify(error="Upload could not be completed. Please retry the upload."), 400


def _gemini_upload_b2_file(key, owner_id):
    """Stream a private B2 object into Gemini's resumable Files API without buffering it in RAM."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    s3 = _large_upload_s3()
    if not api_key or not s3: return None, "Gemini or large-file storage is not configured."
    if not key.startswith(f"private-user-uploads/{owner_id}/"): return None, "This upload does not belong to your account."
    try:
        obj = s3.get_object(Bucket=_large_upload_bucket(), Key=key)
        size = int(obj["ContentLength"])
        mime = obj.get("ContentType", "application/octet-stream")
        if size <= 0 or size > CYBERLORD_LARGE_FILE_MAX_BYTES: return None, "The file exceeds the configured upload limit."
        start = requests.post("https://generativelanguage.googleapis.com/upload/v1beta/files",
            params={"key": api_key}, headers={"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                     "X-Goog-Upload-Header-Content-Length": str(size), "X-Goog-Upload-Header-Content-Type": mime,
                     "Content-Type": "application/json"}, json={"file": {"display_name": "CyberLord private upload"}}, timeout=45)
        start.raise_for_status()
        upload_url = start.headers.get("X-Goog-Upload-URL")
        if not upload_url: return None, "Gemini did not return a resumable upload URL."
        body = obj["Body"]
        def chunks():
            while True:
                chunk = body.read(8 * 1024 * 1024)
                if not chunk: break
                yield chunk
        uploaded = requests.post(upload_url, headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize",
            "Content-Length": str(size)}, data=chunks(), timeout=(60, 3600))
        uploaded.raise_for_status()
        file_data = uploaded.json().get("file", {})
        uri = file_data.get("uri")
        if not uri: return None, "Gemini did not confirm the uploaded file."
        return {"uri": uri, "mime_type": mime, "name": file_data.get("name")}, None
    except Exception as exc:
        app.logger.warning("Gemini large-file transfer failed: %s", str(exc)[:180])
        return None, "The file reached storage, but Gemini could not process it. Check Gemini file limits, quota and Render logs."


def _analyse_gemini_file(question, file_info):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = _gemini_model()
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"system_instruction": {"parts": [{"text": "You are CyberLord. Analyse only the supplied file. Distinguish visible evidence from inference, do not invent facts, and state when content is unclear or too large to inspect fully."}]},
        "contents": [{"role": "user", "parts": [{"text": question}, {"file_data": {"mime_type": file_info["mime_type"], "file_uri": file_info["uri"]}}]}],
        "generationConfig": {"temperature": 0.1}}
    response = requests.post(endpoint, params={"key": key}, json=payload, timeout=300)
    response.raise_for_status()
    data = response.json()
    answer = "".join(part.get("text", "") for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []) if isinstance(part, dict)).strip()
    return answer or None


@app.route("/api/large-upload/analyse", methods=["POST"])
@login_required
def large_upload_analyse():
    body = request.get_json(silent=True) or {}
    key = str(body.get("key") or "")
    question = str(body.get("question") or "Analyse this file carefully and summarise its important content.")[:1200]
    if not key.startswith(f"private-user-uploads/{current_user.id}/"):
        return jsonify(error="This upload does not belong to your account."), 403
    if rate_limited(key="largeanalyse:" + str(current_user.id), limit=5, window=300):
        return jsonify(error="Large-file analysis is limited to 5 files every 5 minutes."), 429
    s3 = _large_upload_s3()
    if not s3: return jsonify(error="File upload service is temporarily unavailable."), 503
    try:
        head = s3.head_object(Bucket=_large_upload_bucket(), Key=key)
        size = int(head.get("ContentLength", 0))
        mime = head.get("ContentType", "application/octet-stream")
        if size > CYBERLORD_LARGE_FILE_MAX_BYTES: return jsonify(error="This file exceeds the configured limit."), 400
        extension = os.path.splitext(key)[1].lower()
        office_or_text = {".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv"}
        if extension in office_or_text:
            if size > 50 * 1024 * 1024:
                return jsonify(error="Office and text documents are limited to 50 MB for safe text extraction. Video, audio, images and PDF can use the provider-supported 2 GB route."), 400
            raw_document = s3.get_object(Bucket=_large_upload_bucket(), Key=key)["Body"].read(50 * 1024 * 1024 + 1)
            from super_mode import extract_document
            parsed = extract_document(key.rsplit("-", 1)[-1], raw_document)
            analysis, analysis_error = _super_mode_gemini(question, "Filename: " + parsed["filename"] + "\n" + parsed["text"], timeout=90)
            if not analysis:
                return jsonify(error=analysis_error or "The document could not be analysed."), 503
            return jsonify(ok=True, filename=parsed["filename"], analysis=analysis, size=size,
                           truncated=parsed["truncated"], note="Your file was processed securely. Temporary upload data is removed after processing.")
        info, error = _gemini_upload_b2_file(key, current_user.id)
        if error: return jsonify(error=error), 503
        analysis = _analyse_gemini_file(question, info)
        # Delete the temporary Gemini file after the response has been generated.
        try:
            if info.get("name"):
                requests.delete(f"https://generativelanguage.googleapis.com/v1beta/{info['name']}",
                                params={"key": os.getenv("GEMINI_API_KEY", "").strip()}, timeout=20)
        except Exception:
            app.logger.info("Gemini temporary file cleanup will rely on provider retention.")
        return jsonify(ok=True, filename=key.rsplit("-", 1)[-1][:120], analysis=analysis or "The model returned no analysis.",
                       size=size, note="The temporary CyberLord storage object is deleted after processing. Gemini temporary files are deleted when supported; otherwise Google's retention policy applies.")
    except Exception as exc:
        app.logger.warning("Large-file analysis failed: %s", str(exc)[:180])
        return jsonify(error="The file was uploaded, but analysis failed. Check Gemini support for this file type and provider quota."), 503
    finally:
        try: s3.delete_object(Bucket=_large_upload_bucket(), Key=key)
        except Exception: pass


@app.route("/api/super-mode/analyse-document", methods=["POST"])
@login_required
def super_mode_analyse_document():
    if rate_limited(key="superdoc:" + client_ip() + ":" + str(current_user.id), limit=8, window=300):
        return jsonify(error="Document analysis is limited to 8 requests every 5 minutes. Please wait and try again."), 429
    uploaded = request.files.get("document")
    if not uploaded:
        return jsonify(error="Choose a document first."), 400
    raw = uploaded.read(8 * 1024 * 1024 + 1)
    try:
        from super_mode import extract_document
        parsed = extract_document(uploaded.filename, raw)
    except ValueError as exc:
        if uploaded.filename.lower().endswith(".pdf") and "no extractable text" in str(exc).lower():
            question = str(request.form.get("question") or "Read this scanned PDF using OCR. Transcribe important text and explain the document.")[:1200]
            analysis, error = _super_mode_gemini_media(question, raw, "application/pdf")
            if not analysis: return jsonify(error=error or str(exc)), 503
            return jsonify(ok=True, filename=uploaded.filename[:120], analysis=analysis, ocr=True,
                           note="OCR was performed by the multimodal AI. Verify critical numbers and names against the original scan.")
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        app.logger.warning("Super Mode document parse failed: %s", str(exc)[:160])
        return jsonify(error="This document could not be read. Check that it is a valid, unencrypted file."), 400
    question = str(request.form.get("question") or "Summarise this document, explain its important points, and identify anything that needs attention.")[:1200]
    analysis, error = _super_mode_gemini(question, "Filename: " + parsed["filename"] + "\n" + parsed["text"])
    if not analysis:
        return jsonify(error=error, filename=parsed["filename"], extracted_text=parsed["text"][:8000], truncated=parsed["truncated"]), 503
    return jsonify(ok=True, filename=parsed["filename"], analysis=analysis, truncated=parsed["truncated"],
                   note="Document text was processed for this request and was not saved as a public file.")


@app.route("/api/super-mode/youtube", methods=["POST"])
@login_required
def super_mode_youtube():
    body = request.get_json(silent=True) or {}
    query = str(body.get("query") or "").strip()[:180]
    if not query:
        return jsonify(error="Enter a YouTube search or video URL."), 400
    try:
        from super_mode import youtube_video_id, youtube_search, youtube_transcript
        if youtube_video_id(query):
            transcript = youtube_transcript(query)
            summary, error = _super_mode_gemini("Summarise this YouTube transcript. Give the main ideas, useful timestamps only if present, and important limitations.", transcript["transcript"])
            if not summary:
                return jsonify(error=error, transcript=transcript["transcript"][:9000], url=transcript["url"]), 503
            return jsonify(ok=True, url=transcript["url"], summary=summary, transcript_truncated=transcript["truncated"])
        result = youtube_search(query)
        if not result.get("configured"):
            return jsonify(error=result.get("message"), setup_required=True), 503
        return jsonify(ok=True, **result)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except requests.RequestException as exc:
        app.logger.warning("YouTube API request failed: %s", str(exc)[:160])
        return jsonify(error="YouTube search is temporarily unavailable. Check the API key, quota and Google Cloud API settings."), 503
    except Exception as exc:
        app.logger.warning("Super Mode YouTube failed: %s", str(exc)[:160])
        return jsonify(error="YouTube research could not be completed."), 503


@app.route("/api/super-mode/transcribe-audio", methods=["POST"])
@login_required
def super_mode_transcribe_audio():
    audio = request.files.get("audio")
    if not audio:
        return jsonify(error="Record or choose an audio note first."), 400
    raw = audio.read(15 * 1024 * 1024 + 1)
    if not raw or len(raw) > 15 * 1024 * 1024:
        return jsonify(error="Audio notes must be under 15 MB."), 400
    mime = (audio.mimetype or "audio/webm").split(";")[0].lower()
    allowed = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/mp4", "audio/aac", "audio/flac"}
    if mime not in allowed:
        return jsonify(error="Use a WEBM, OGG, MP3, WAV, MP4-audio, AAC or FLAC recording."), 400
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return jsonify(error="Voice-note transcription needs GEMINI_API_KEY configured in Render."), 503
    try:
        model = os.getenv("GEMINI_AUDIO_MODEL", _gemini_model()).strip()
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {"contents": [{"role": "user", "parts": [
            {"text": "Transcribe this audio accurately in its original language. Return only the words spoken. If speech is unclear, mark the unclear section rather than guessing."},
            {"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode("ascii")}}
        ]}], "generationConfig": {"temperature": 0.1}}
        response = requests.post(endpoint, params={"key": key}, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        transcript = "".join(part.get("text", "") for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []) if isinstance(part, dict)).strip()
        if not transcript:
            return jsonify(error="The audio provider returned no transcript."), 503
        return jsonify(ok=True, transcript=transcript[:12000])
    except Exception as exc:
        app.logger.warning("Super Mode audio transcription failed: %s", str(exc)[:180])
        return jsonify(error="The voice note could not be transcribed. Check the audio format, Gemini model access and quota."), 503


@app.route("/api/super-mode/analyse-video", methods=["POST"])
@login_required
def super_mode_analyse_video():
    uploaded = request.files.get("video")
    if not uploaded: return jsonify(error="Choose an MP4, MOV or WEBM video first."), 400
    raw = uploaded.read(20 * 1024 * 1024 + 1)
    if not raw or len(raw) > 20 * 1024 * 1024: return jsonify(error="For files larger than 20 MB, use the resumable large-file uploader in Super Mode."), 400
    mime = (uploaded.mimetype or "").split(";")[0].lower()
    allowed = {"video/mp4", "video/quicktime", "video/webm", "video/mpeg"}
    if mime not in allowed: return jsonify(error="Use MP4, MOV or WEBM video."), 400
    question = str(request.form.get("question") or "Describe the video in sequence, identify key events, visible text and important details. Do not invent timestamps.")[:1200]
    answer, error = _super_mode_gemini_media(question, raw, mime, timeout=120)
    if not answer: return jsonify(error=error), 503
    return jsonify(ok=True, analysis=answer, filename=uploaded.filename[:120], note="Video was analysed inline. Long videos may exceed provider limits; use a shorter clip if needed.")


@app.route("/api/super-mode/speak", methods=["POST"])
@login_required
def super_mode_speak():
    body = request.get_json(silent=True) or {}
    audio = _gemini_speech_bytes(str(body.get("text") or "")[:3500])
    if not audio: return jsonify(error="Speech generation is unavailable. Configure a Gemini TTS model with audio output access."), 503
    return jsonify(ok=True, audio=audio["data"], mime_type=audio["mime_type"])


@app.route("/api/super-mode/agent-plan", methods=["POST"])
@login_required
def super_mode_agent_plan():
    body = request.get_json(silent=True) or {}
    try:
        from super_mode import build_agent_plan
        return jsonify(ok=True, plan=build_agent_plan(body.get("goal")))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@app.route("/api/super-mode/readiness")
@login_required
def super_mode_readiness():
    return jsonify(ok=True, capabilities={
        "large_resumable_uploads": bool(_large_upload_s3() and os.getenv("GEMINI_API_KEY")),
        "large_upload_max_bytes": CYBERLORD_LARGE_FILE_MAX_BYTES,
        "large_upload_storage": "Available" if _large_upload_s3() else "Unavailable",
        "gemini_reasoning_and_document_analysis": bool(os.getenv("GEMINI_API_KEY")),
        "groq_fallback": bool(os.getenv("GROQ_API_KEY")),
        "youtube_search": bool(os.getenv("YOUTUBE_API_KEY")),
        "video_generation": bool(os.getenv("GOOGLE_CLOUD_PROJECT") and os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")),
        "cloudflare_image_fallback": bool(os.getenv("CLOUDFLARE_ACCOUNT_ID") and os.getenv("CLOUDFLARE_API_TOKEN")),
        "browser_voice_input": True,
        "browser_voice_playback": True,
        "scanned_pdf_ocr": bool(os.getenv("GEMINI_API_KEY")),
        "uploaded_video_analysis": bool(os.getenv("GEMINI_API_KEY")),
        "generated_audio_replies": bool(os.getenv("GEMINI_API_KEY")),
        "telegram_voice_note_input": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("GEMINI_API_KEY")),
        "whatsapp_voice_note_input": bool(os.getenv("WHATSAPP_ACCESS_TOKEN") and os.getenv("GEMINI_API_KEY")),
        "persistent_user_memory": True,
        "artificial_brain_orchestration": True,
        "private_user_approved_knowledge": True,
        "resumable_multipart_uploads": True,
        "large_office_document_uploads": True,
        "academy_training": True,
        "shared_messaging_engine": True,
        "monitoring_worker": True
    }, note="Readiness indicates configuration or existing code paths only. It does not guarantee provider quota, successful delivery or live service availability.")


@app.route("/health")
def health(): return jsonify(status="ok",service="CyberLord Domain Intelligence")

with app.app_context():
    db.create_all()
    # Lightweight additive migration for existing installations (safe to run repeatedly).
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    user_cols = {c["name"] for c in inspector.get_columns("user")}
    payment_cols = {c["name"] for c in inspector.get_columns("payment")}
    with db.engine.begin() as conn:
        if "plan_expires_at" not in user_cols:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN plan_expires_at TIMESTAMP NULL'))
        if "tutor_pro_expires_at" not in user_cols:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN tutor_pro_expires_at TIMESTAMP NULL'))
        for name, definition in [("currency", "VARCHAR(10) NOT NULL DEFAULT 'NGN'"), ("network", "VARCHAR(20) NULL"), ("tx_hash", "VARCHAR(140) NULL"), ("expires_at", "TIMESTAMP NULL")]:
            if name not in payment_cols:
                conn.execute(text(f"ALTER TABLE payment ADD COLUMN {name} {definition}"))
        # Unique index prevents one on-chain transaction from paying for multiple accounts.
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_tx_hash ON payment (tx_hash)"))
    # Existing paid accounts without an expiry are backfilled from their latest verified payment.
    for legacy_user in User.query.filter(User.plan != "free", User.plan_expires_at.is_(None)).all():
        last_payment = Payment.query.filter_by(user_id=legacy_user.id, status="success").order_by(Payment.verified_at.desc()).first()
        start = (last_payment.verified_at if last_payment and last_payment.verified_at else legacy_user.created_at) or datetime.utcnow()
        legacy_user.plan_expires_at = start + timedelta(days=30)
        if legacy_user.plan_expires_at <= datetime.utcnow():
            legacy_user.plan = "free"
            legacy_user.plan_expires_at = None
    db.session.commit()

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=os.getenv("FLASK_DEBUG")=="1")

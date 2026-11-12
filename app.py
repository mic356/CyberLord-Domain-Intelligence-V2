import os, re, json, hmac, hashlib, secrets, socket, ssl, ipaddress, subprocess, shutil, time
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse
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
from html.parser import HTMLParser
from difflib import SequenceMatcher
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle, KeepTogether

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "CHANGE-ME-TO-A-LONG-RANDOM-SECRET")
db_url = os.getenv("DATABASE_URL", "sqlite:///cyberlord.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True} if db_url.startswith("postgresql") else {}
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# Fixed prices agreed for launch. NGN prices are fixed rather than live FX conversions.
PLANS = {
    "free": {"name": "FREE", "price": 0, "ngn": 0, "usdt": "0.00", "rank": 0},
    "pro": {"name": "PRO", "price": 6300, "ngn": 6300, "usdt": "4.50", "rank": 1},
    "pro_plus": {"name": "PRO PLUS", "price": 12600, "ngn": 12600, "usdt": "9.00", "rank": 2},
}
USDT_WALLETS = {
    "trc20": "TSLdKMFJB3pqWMkkZoUfdo5j2GVh2ANHSw",
    "bep20": "0xab22fd86fbf75f7082436b25c0f851d4d7484e32",
}
USDT_CONTRACTS = {
    "trc20": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
    "bep20": "0x55d398326f99059fF775485246999027B3197955",
}
PRO_TOOLS = {"phone", "email_review", "breach"}
PLUS_TOOLS = {"attack_surface", "cve", "compare", "port"}
TOOL_NAMES = {
    "domain": "Domain Security Scan", "subdomains": "Subdomain Intelligence",
    "email": "Email Security", "dns": "DNS Intelligence", "technology": "Technology Fingerprint",
    "ip": "IP Intelligence", "phone": "Phone Intelligence", "email_review": "Individual Email Review",
    "breach": "Breach Exposure", "attack_surface": "Attack Surface Map",
    "cve": "CVE Intelligence", "compare": "Compare Domains", "port": "Limited Port Scanner"
}

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    plan = db.Column(db.String(20), default="free", nullable=False)
    plan_expires_at = db.Column(db.DateTime)
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


class BoardReply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("board_post.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def normalize_domain(value):
    value = (value or "").strip().lower()
    if "://" in value:
        value = urlparse(value).hostname or ""
    value = value.split("/")[0].split(":")[0].strip(".")
    if not value or len(value) > 253 or not re.fullmatch(r"(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", value):
        raise ValueError("Enter a valid public domain name, e.g. example.com.")
    return value

def refresh_subscription(user):
    """Downgrade expired paid plans before checking access or showing the dashboard."""
    if user and user.plan != "free" and user.plan_expires_at:
        expiry = user.plan_expires_at
        if expiry <= datetime.utcnow():
            user.plan = "free"
            user.plan_expires_at = None
            db.session.commit()

def activate_subscription(user, payment):
    """Start a fresh 30-day term only after server-side payment verification."""
    now = datetime.utcnow()
    user.plan = payment.plan
    user.plan_expires_at = now + timedelta(days=30)
    payment.status = "success"
    payment.verified_at = now
    payment.expires_at = user.plan_expires_at
    db.session.commit()

def allowed_tool(tool):
    refresh_subscription(current_user)
    rank = PLANS.get(current_user.plan, PLANS["free"])["rank"]
    if tool in PRO_TOOLS and rank < 1: return False
    if tool in PLUS_TOOLS and rank < 2: return False
    return True

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
    try: ptr=socket.gethostbyaddr(str(ip))[0]
    except Exception: ptr=None
    return {"ip":str(ip),"version":ip.version,"is_global":ip.is_global,"reverse_dns":ptr,
        "reverse_dns_names":socket.gethostbyaddr(str(ip))[2][:10] if ptr else [],
        "rdap_url":"https://rdap.org/ip/"+str(ip),"note":"RDAP link points to registration data; allocation data does not identify a device owner or prove malicious activity."}

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
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(password) < 10:
            flash("Enter a valid email and a password of at least 10 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            user = User(email=email); user.set_password(password)
            db.session.add(user); db.session.commit()
            login_user(user); return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
        if user and user.check_password(request.form.get("password","")):
            login_user(user); return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout")
@login_required
def logout():
    logout_user(); return redirect(url_for("index"))

@app.route("/forgot-password", methods=["GET","POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
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
        password = request.form.get("password","")
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
    return render_template("dashboard.html", plans=PLANS, tool_names=TOOL_NAMES, pro_tools=PRO_TOOLS, plus_tools=PLUS_TOOLS, history=history, usdt_wallets=USDT_WALLETS)

ACADEMY_LESSONS = [
    {"slug":"networking-essentials", "level":"FOUNDATION", "title":"Networking essentials", "time":"12 min", "desc":"Understand IP addresses, ports, TCP, UDP and DNS.", "content":["An IP address identifies a device or network interface. A port identifies a service or application endpoint on that device.","TCP is connection-oriented and provides ordered, reliable delivery. UDP is connectionless and has lower overhead, but does not guarantee delivery.","DNS translates domain names into records such as A/AAAA addresses and MX mail servers. A port being open means a service is listening; it does not automatically mean the service is vulnerable."], "question":"What does a port number help identify?", "choices":["A service or application endpoint", "A device's physical location", "The owner's password"], "answer":0, "explain":"A port helps direct network traffic to the correct service on a device."},
    {"slug":"kali-linux-basics", "level":"LINUX & TOOLS", "title":"Getting comfortable with Kali Linux", "time":"15 min", "desc":"Learn terminal navigation, files and safe lab habits.", "content":["The terminal lets you run commands and inspect system information. Start with pwd to show your current directory, ls to list files and cd to change directory.","Use whoami to see the current account and ip addr to inspect network interfaces. Read command help before running unfamiliar tools.","Keep practice inside your own virtual lab or systems where you have explicit permission. Avoid running commands copied from unknown sources with administrator privileges."], "question":"Which command shows your current directory?", "choices":["pwd", "whoami", "ip addr"], "answer":0, "explain":"pwd prints the current working directory."},
    {"slug":"nmap-fundamentals", "level":"RECONNAISSANCE", "title":"Nmap fundamentals", "time":"18 min", "desc":"Learn port states, service detection and scan interpretation.", "content":["Nmap is used for network discovery and security auditing. Only scan systems you own or have permission to assess.","A basic lab command is nmap 127.0.0.1. The -sV option asks Nmap to identify service versions. Use -p 80,443 to specify ports or -p- to scan all TCP ports.","Open means a service accepted the connection attempt. Closed means the host responded but no service is listening. Filtered means a firewall or network control prevents Nmap from determining the state."], "question":"What does Nmap -sV attempt to identify?", "choices":["Service versions", "Wi-Fi passwords", "User account passwords"], "answer":0, "explain":"-sV enables service/version detection."},
    {"slug":"http-tls-headers", "level":"WEB SECURITY", "title":"HTTP, TLS and security headers", "time":"16 min", "desc":"Understand requests, responses, HTTPS and browser security headers.", "content":["An HTTP request contains a method, path, headers and sometimes a body. The server responds with a status code, headers and optional content.","Common status codes include 200 (success), 301/302 (redirect), 400 (bad request), 401 (authentication required), 403 (forbidden) and 404 (not found).", "TLS protects data in transit and helps authenticate the server. Headers such as Strict-Transport-Security, Content-Security-Policy and X-Content-Type-Options add browser-side protections."], "question":"What does HTTP status 403 generally mean?", "choices":["Forbidden", "Successful response", "Page permanently moved"], "answer":0, "explain":"403 means the server understood the request but refuses access."},
    {"slug":"cve-triage", "level":"VULNERABILITY", "title":"CVE and vulnerability triage", "time":"14 min", "desc":"Validate versions, severity, exposure and remediation.", "content":["A CVE is a public identifier for a disclosed cybersecurity vulnerability. A CVE record is a starting point for research, not proof that a particular system is affected.","Check the exact product, version, configuration and vendor advisory. Compare the affected version range with reliable evidence from the target environment.","Severity scores help prioritise work, but real risk also depends on exposure, exploitability, business impact and available mitigations. Document uncertainty instead of overstating a finding."], "question":"Does a CVE number alone prove a system is vulnerable?", "choices":["No; verify product, version and configuration", "Yes, always", "Only if the port is open"], "answer":0, "explain":"A CVE must be matched to the actual product and affected version/configuration."},
    {"slug":"security-reporting", "level":"REPORTING", "title":"Writing a professional security report", "time":"10 min", "desc":"Turn evidence into clear impact and practical recommendations.", "content":["A useful report explains what was tested, when it was tested, the scope and the limitations. Readers should understand exactly what was and was not assessed.","For each finding, include a concise title, severity rationale, affected asset, reproducible evidence, impact and a practical remediation recommendation.","Do not include secrets or unnecessary personal data. Separate confirmed observations from assumptions, and retest after remediation when authorised."], "question":"What should a finding include?", "choices":["Evidence, impact and remediation", "Only a scary title", "Unverified assumptions"], "answer":0, "explain":"A finding should be supported by evidence and explain its impact and remediation."},
]

@app.route("/academy")
@login_required
def academy():
    progress = {p.lesson_slug: p for p in AcademyProgress.query.filter_by(user_id=current_user.id).all()}
    lessons = []
    for item in ACADEMY_LESSONS:
        row = dict(item)
        row["progress"] = progress.get(item["slug"])
        lessons.append(row)
    completed = sum(1 for item in lessons if item["progress"] and item["progress"].completed_at)
    return render_template("academy.html", lessons=lessons, completed=completed, total=len(lessons))

@app.route("/academy/<slug>", methods=["GET", "POST"])
@login_required
def academy_lesson(slug):
    lesson = next((x for x in ACADEMY_LESSONS if x["slug"] == slug), None)
    if not lesson:
        abort(404)
    progress = AcademyProgress.query.filter_by(user_id=current_user.id, lesson_slug=slug).first()
    result = None
    if request.method == "POST":
        try:
            selected = int(request.form.get("answer", "-1"))
        except (TypeError, ValueError):
            selected = -1
        if selected not in range(len(lesson["choices"])):
            flash("Choose one answer before submitting.", "warning")
        else:
            correct = selected == lesson["answer"]
            score = 100 if correct else 0
            if not progress:
                progress = AcademyProgress(user_id=current_user.id, lesson_slug=slug)
                db.session.add(progress)
            progress.best_score = max(progress.best_score or 0, score)
            if correct:
                progress.completed_at = datetime.utcnow()
            db.session.commit()
            result = {"correct": correct, "explain": lesson["explain"]}
    return render_template("academy_lesson.html", lesson=lesson, progress=progress, result=result)

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
    target=request.form.get("target","").strip()
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
        elif tool in {"domain","dns","subdomains","technology","email","attack_surface","cve","port","breach","email_review"}:
            if tool == "email_review":
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",target): raise ValueError("Enter a valid email address.")
                domain=normalize_domain(target.split("@",1)[1]); posture=email_posture(domain)
                result={"email":target,"domain":domain,"syntax_valid":True,"domain_email_posture":posture,"mailbox_exists":None,"note":"No mailbox login or delivery test is performed; this does not verify that the individual mailbox exists."}
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
                elif tool=="breach":
                    result={"target":domain,"provider_status":"not_connected","message":"No licensed breach-intelligence provider is connected. This is not a clean-breach result; no breach conclusion can be made."}
        save_scan(tool,target,result)
        return jsonify(result=result)
    except ValueError as e: return jsonify(error=str(e)),400
    except requests.RequestException as e:
        app.logger.warning("External scan provider unavailable: %s",e)
        return jsonify(error="A scan provider could not be reached. Check the target and provider connection."),502
    except Exception:
        app.logger.exception("Tool execution failed")
        return jsonify(error="The check could not be completed. Verify the target and try again."),500

def verify_tron_usdt(tx_hash, expected_amount):
    """Verify a confirmed TRC20 USDT transfer using TronGrid's confirmed account history."""
    wallet = USDT_WALLETS["trc20"]
    params = {"limit": 200, "only_confirmed": "true", "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"}
    headers = {}
    api_key = os.getenv("TRONGRID_API_KEY")
    if api_key:
        headers["TRON-PRO-API-KEY"] = api_key
    response = requests.get(f"https://api.trongrid.io/v1/accounts/{wallet}/transactions/trc20", params=params, headers=headers, timeout=20)
    response.raise_for_status()
    for transfer in response.json().get("data", []):
        info = transfer.get("token_info", {})
        if transfer.get("transaction_id", "").lower() != tx_hash.lower():
            continue
        if info.get("address") != "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t":
            continue
        if transfer.get("to", "").lower() != wallet.lower():
            continue
        decimals = int(info.get("decimals", 6))
        received = Decimal(str(transfer.get("value", "0"))) / (Decimal(10) ** decimals)
        if received != expected_amount:
            return False, "The transaction amount does not match the selected plan."
        return True, "Confirmed TRC20 USDT transfer verified."
    return False, "No confirmed incoming USDT transfer matching this transaction hash was found yet. Check the network and try again later."

def verify_bep20_usdt(tx_hash, expected_amount):
    """Verify a BEP20 USDT transfer from a successful, sufficiently confirmed BSC receipt."""
    rpc = os.getenv("BSC_RPC_URL") or "https://bsc-dataseed.binance.org/"
    token = USDT_CONTRACTS["bep20"].lower()
    recipient = USDT_WALLETS["bep20"].lower()
    transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    def rpc_call(method, params):
        r = requests.post(rpc, json={"jsonrpc":"2.0","id":1,"method":method,"params":params}, timeout=20)
        r.raise_for_status()
        payload = r.json()
        if payload.get("error"):
            raise RuntimeError("BSC RPC returned an error")
        return payload.get("result")
    chain_id = rpc_call("eth_chainId", [])
    if int(chain_id, 16) != 56:
        raise RuntimeError("Configured RPC endpoint is not BNB Smart Chain mainnet")
    receipt = rpc_call("eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        return False, "Transaction not found on BNB Smart Chain yet."
    if int(receipt.get("status", "0x0"), 16) != 1:
        return False, "The blockchain transaction failed."
    latest = rpc_call("eth_blockNumber", [])
    confirmations = int(latest, 16) - int(receipt.get("blockNumber", "0x0"), 16) + 1
    if confirmations < 12:
        return False, f"Transaction has {confirmations} confirmations; at least 12 are required."
    for log in receipt.get("logs", []):
        topics = log.get("topics", [])
        if log.get("address", "").lower() != token or len(topics) < 3 or topics[0].lower() != transfer_topic:
            continue
        to_address = "0x" + topics[2][-40:].lower()
        if to_address != recipient:
            continue
        received = Decimal(int(log.get("data", "0x0"), 16)) / (Decimal(10) ** 18)
        if received != expected_amount:
            return False, "The transaction amount does not match the selected plan."
        return True, "Confirmed BEP20 USDT transfer verified."
    return False, "This transaction does not contain an incoming transfer of the supported USDT token to the CyberLord wallet."

def verify_usdt(network, tx_hash, plan):
    if network == "trc20":
        return verify_tron_usdt(tx_hash, Decimal(PLANS[plan]["usdt"]))
    if network == "bep20":
        return verify_bep20_usdt(tx_hash, Decimal(PLANS[plan]["usdt"]))
    return False, "Unsupported payment network."

@app.route("/payment/usdt/submit", methods=["POST"])
@login_required
def payment_usdt_submit():
    plan = request.form.get("plan", "")
    network = request.form.get("network", "").lower()
    tx_hash = request.form.get("tx_hash", "").strip()
    if plan not in ("pro", "pro_plus") or network not in USDT_WALLETS:
        flash("Select a valid plan and USDT network.", "error")
        return redirect(url_for("dashboard") + "#plans")
    valid_hash = (re.fullmatch(r"[0-9a-fA-F]{64}", tx_hash) if network == "bep20" else re.fullmatch(r"[0-9a-fA-F]{64}", tx_hash))
    if not valid_hash:
        flash("Enter the 64-character transaction hash from the selected blockchain.", "error")
        return redirect(url_for("dashboard") + "#plans")
    existing = Payment.query.filter_by(tx_hash=tx_hash).first()
    if existing and (existing.status == "success" or existing.user_id != current_user.id or existing.plan != plan or existing.network != network):
        flash("This transaction hash has already been submitted and cannot be reused.", "error")
        return redirect(url_for("dashboard") + "#plans")
    payment = existing or Payment(user_id=current_user.id, reference="USDT-" + secrets.token_urlsafe(16), plan=plan,
        amount=int(Decimal(PLANS[plan]["usdt"]) * 100), status="pending", currency="USDT", network=network, tx_hash=tx_hash)
    if not existing:
        db.session.add(payment)
        db.session.commit()
    try:
        verified, message = verify_usdt(network, tx_hash, plan)
    except Exception:
        app.logger.exception("USDT transaction verification provider failed")
        verified, message = False, "The blockchain verification service is temporarily unavailable. Your payment remains pending; retry later."
    if verified:
        user = db.session.get(User, payment.user_id)
        if payment.status != "success" and user:
            activate_subscription(user, payment)
        flash("Payment verified. " + PLANS[plan]["name"] + " is active for 30 days.", "success")
    else:
        payment.status = "pending"
        db.session.commit()
        flash(message + " Your submission is pending and no subscription has been activated.", "warning")
    return redirect(url_for("dashboard") + "#plans")

@app.route("/payment/bank/submit", methods=["POST"])
@login_required
def payment_bank_submit():
    plan = request.form.get("plan", "")
    bank_reference = request.form.get("bank_reference", "").strip()
    if plan not in ("pro", "pro_plus") or not bank_reference or len(bank_reference) > 115:
        flash("Select a plan and enter your bank transfer reference.", "error")
        return redirect(url_for("dashboard") + "#plans")
    reference = "BANK-" + bank_reference
    if Payment.query.filter_by(reference=reference).first():
        flash("That bank transfer reference has already been submitted.", "error")
        return redirect(url_for("dashboard") + "#plans")
    payment_method = request.form.get("payment_method", "opay").strip().lower()
    if payment_method not in ("opay", "union_bank"):
        flash("Select a valid bank payment method.", "error")
        return redirect(url_for("dashboard") + "#plans")
    db.session.add(Payment(user_id=current_user.id, reference=reference, plan=plan, amount=PLANS[plan]["ngn"] * 100,
        status="pending", currency="NGN", network=payment_method))
    db.session.commit()
    flash("Payment request submitted successfully. Your subscription will activate after the payment is confirmed.", "success")
    return redirect(url_for("dashboard") + "#plans")

# Paystack integration is retained for future reactivation, but disabled unless explicitly enabled.
@app.route("/payment/initialize", methods=["POST"])
@login_required
def payment_initialize():
    if os.getenv("PAYSTACK_ENABLED", "false").lower() != "true":
        flash("Paystack is temporarily disabled while the account is awaiting approval.", "warning")
        return redirect(url_for("dashboard") + "#plans")
    plan=request.form.get("plan") or (request.get_json(silent=True) or {}).get("plan")
    if plan not in ("pro","pro_plus"): return jsonify(error="Invalid plan"), 400
    secret=os.getenv("PAYSTACK_SECRET_KEY")
    if not secret: return jsonify(error="Paystack is not configured on the server."), 503
    reference="CLD-"+secrets.token_urlsafe(18)
    amount=PLANS[plan]["ngn"]*100
    payment=Payment(user_id=current_user.id,reference=reference,plan=plan,amount=amount,currency="NGN")
    db.session.add(payment); db.session.commit()
    try:
        response=requests.post("https://api.paystack.co/transaction/initialize",
            headers={"Authorization":"Bearer "+secret,"Content-Type":"application/json"},
            json={"email":current_user.email,"amount":amount,"currency":"NGN","reference":reference,
                  "callback_url":url_for("payment_callback",_external=True),"metadata":{"user_id":current_user.id,"plan":plan}},timeout=15)
        data=response.json()
        if not response.ok or not data.get("status"): raise RuntimeError(data.get("message","Paystack initialization failed"))
        return redirect(data["data"]["authorization_url"],code=303)
    except Exception:
        payment.status="failed"; db.session.commit()
        app.logger.exception("Paystack initialization failed")
        flash("Could not start Paystack checkout. Please try again later.", "error")
        return redirect(url_for("dashboard"))

def verify_paystack(reference):
    secret=os.getenv("PAYSTACK_SECRET_KEY")
    if not secret: return None
    r=requests.get("https://api.paystack.co/transaction/verify/"+reference,headers={"Authorization":"Bearer "+secret},timeout=15)
    data=r.json()
    if r.ok and data.get("status") and data.get("data",{}).get("status")=="success": return data["data"]
    return None

@app.route("/payment/callback")
@login_required
def payment_callback():
    if os.getenv("PAYSTACK_ENABLED", "false").lower() != "true":
        flash("Paystack is currently disabled.", "warning")
        return redirect(url_for("dashboard"))
    reference=request.args.get("reference", "")
    payment=Payment.query.filter_by(reference=reference,user_id=current_user.id).first()
    if not payment: flash("Payment reference was not found.", "error"); return redirect(url_for("dashboard"))
    try: data=verify_paystack(reference)
    except Exception: data=None
    if data and data.get("amount")==payment.amount and data.get("currency")=="NGN" and payment.status != "success":
        activate_subscription(current_user, payment)
        flash("Payment verified. Your plan is active for 30 days.", "success")
    else:
        flash("Payment is not yet verified. If you paid, wait briefly and refresh your dashboard.", "warning")
    return redirect(url_for("dashboard"))

@app.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    if os.getenv("PAYSTACK_ENABLED", "false").lower() != "true": return "Paystack disabled", 404
    secret=os.getenv("PAYSTACK_SECRET_KEY", "")
    signature=request.headers.get("x-paystack-signature", "")
    expected=hmac.new(secret.encode(),request.get_data(),hashlib.sha512).hexdigest()
    if not secret or not hmac.compare_digest(signature,expected): return "invalid signature", 401
    event=request.get_json(silent=True) or {}
    if event.get("event")=="charge.success":
        data=event.get("data",{}); ref=data.get("reference")
        payment=Payment.query.filter_by(reference=ref).first()
        if payment and payment.status != "success" and data.get("status")=="success" and data.get("amount")==payment.amount and data.get("currency")=="NGN":
            user=db.session.get(User,payment.user_id)
            if user: activate_subscription(user, payment)
    return jsonify(received=True)

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
    return render_template("admin_payments.html", payments=payments, counts=counts, status_filter=status_filter, csrf_token=_admin_csrf_token())

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    _require_admin()
    session.clear()
    flash("You have signed out of the administrator area.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/payments/<int:payment_id>/approve", methods=["POST"])
def admin_approve_bank_payment(payment_id):
    _require_admin()
    payment = db.session.get(Payment, payment_id)
    eligible_methods = {"bank_transfer", "opay", "union_bank"}
    if not payment or payment.currency != "NGN" or payment.network not in eligible_methods or payment.status != "pending":
        flash("This payment is not an eligible pending bank transfer.", "error")
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



@app.route("/api/ai-assistant", methods=["POST"])
@login_required
def ai_assistant():
    """Gemini-backed CyberLord assistant with a local knowledge fallback."""
    now = time.time()
    window = session.get("ai_rate_window", [])
    window = [stamp for stamp in window if now - stamp < 60]
    if len(window) >= 20:
        return jsonify(error="You're sending messages quickly. Please wait a moment and try again."), 429
    window.append(now)
    session["ai_rate_window"] = window

    body = request.get_json(silent=True) or {}
    messages = body.get("messages", [])
    if not isinstance(messages, list):
        return jsonify(error="Invalid conversation format."), 400

    # Keep a short, bounded history and accept only plain-text user/assistant turns.
    contents = []
    for item in messages[-12:]:
        if not isinstance(item, dict) or not isinstance(item.get("content"), str):
            continue
        content = item["content"].strip()[:1800]
        if not content:
            continue
        role = item.get("role")
        if role == "user":
            gemini_role = "user"
        elif role in ("assistant", "model"):
            gemini_role = "model"
        else:
            continue
        # Gemini expects alternating user/model turns. Drop duplicate consecutive roles.
        if contents and contents[-1]["role"] == gemini_role:
            contents[-1]["parts"][0]["text"] += "\n\n" + content
        else:
            contents.append({"role": gemini_role, "parts": [{"text": content}]})
    if not contents or contents[-1]["role"] != "user":
        return jsonify(error="Please enter a question."), 400

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash"
    if api_key:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "systemInstruction": {"parts": [{"text": (
                    "You are CyberLord AI, the cybersecurity learning and platform assistant. "
                    "Give clear, accurate, beginner-friendly explanations. Prefer practical, "
                    "step-by-step defensive guidance. Support authorised security testing only; "
                    "do not help compromise systems, steal credentials, evade detection, deploy "
                    "malware, or access data without permission. For dual-use questions, keep "
                    "the answer bounded to a legal lab or defensive validation. Never claim "
                    "you performed a scan or verified a live target unless a tool result is supplied. "
                    "Do not invent CyberLord account, payment, scan or subscription status. "
                    "Do not request passwords, OTPs, API keys, wallet seed phrases or private keys. "
                    "If uncertain, say so and recommend checking primary documentation."
                )}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.55, "maxOutputTokens": 1200, "candidateCount": 1},
            }
            response = requests.post(endpoint,
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json=payload, timeout=25)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates") or []
            parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
            reply = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
            if not reply:
                raise ValueError("Gemini returned an empty response.")
            return jsonify(reply=reply, mode="gemini", model=model,
                           live_sources="Gemini response; verify important security findings against primary sources")
        except Exception as exc:
            app.logger.warning("Gemini API unavailable; using local CyberLord knowledge fallback: %s", str(exc)[:240])

    # Keep the service useful if no key is configured or Gemini temporarily fails.
    try:
        from cyberlord_ai import answer
        latest = next(item["parts"][0]["text"] for item in reversed(contents) if item["role"] == "user")
        fallback_history = []
        for item in contents:
            fallback_history.append({"role": "assistant" if item["role"] == "model" else "user",
                                     "content": item["parts"][0]["text"]})
        reply = answer(latest, fallback_history)
        return jsonify(reply=reply, mode="built-in-fallback",
                       live_sources="NIST NVD and CISA KEV when reachable")
    except Exception:
        app.logger.exception("CyberLord assistant error")
        return jsonify(error="CyberLord AI is temporarily unavailable. Please try again shortly."), 500



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
    if request.form.get("authorized")!="yes":
        return jsonify(ok=False,error="Confirm that you own this domain or have permission to investigate it."),400
    try:
        domain=normalize_domain(request.form.get("domain"))
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

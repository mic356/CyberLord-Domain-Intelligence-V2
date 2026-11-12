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
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from io import BytesIO
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
    db.session.add(Payment(user_id=current_user.id, reference=reference, plan=plan, amount=PLANS[plan]["ngn"] * 100,
        status="pending", currency="NGN", network="bank_transfer"))
    db.session.commit()
    flash("Bank transfer submitted for manual verification. A receipt or reference alone will not activate your plan.", "warning")
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

@app.route("/admin/payments/<int:payment_id>/approve", methods=["POST"])
def admin_approve_bank_payment(payment_id):
    """Manual bank confirmation endpoint; protect with a long random server-only token."""
    admin_token = os.getenv("PAYMENT_ADMIN_TOKEN", "")
    supplied = request.headers.get("Authorization", "")
    if not admin_token or not hmac.compare_digest(supplied, "Bearer " + admin_token):
        abort(401)
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.currency != "NGN" or payment.network != "bank_transfer" or payment.status != "pending":
        return jsonify(error="No eligible pending bank transfer was found."), 404
    user = db.session.get(User, payment.user_id)
    if not user:
        return jsonify(error="Payment account was not found."), 404
    activate_subscription(user, payment)
    return jsonify(status="approved", payment_id=payment.id, plan=payment.plan, expires_at=payment.expires_at.isoformat())



@app.route("/api/ai-assistant", methods=["POST"])
@login_required
def ai_assistant():
    """Free built-in CyberLord knowledge assistant with optional public CVE intelligence lookups."""
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
    user_turns = [item.get("content", "").strip()[:900] for item in messages[-12:]
                  if isinstance(item, dict) and item.get("role") == "user"
                  and isinstance(item.get("content"), str) and item.get("content", "").strip()]
    if not user_turns:
        return jsonify(error="Please enter a question."), 400
    latest = user_turns[-1]
    # Carry a little conversational context for follow-up prompts such as "explain that more".
    context_query = " ".join(user_turns[-3:])

    try:
        from cyberlord_ai import answer
        reply = answer(context_query, messages[-12:])
        return jsonify(reply=reply, mode="built-in-knowledge", live_sources="NIST NVD and CISA KEV when reachable")
    except Exception:
        app.logger.exception("CyberLord built-in assistant error")
        return jsonify(error="CyberLord Assistant hit an unexpected problem. Please try again shortly."), 500

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

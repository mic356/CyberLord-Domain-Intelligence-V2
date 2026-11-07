import os, re, json, hmac, hashlib, secrets, socket, ssl, ipaddress
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlparse
import requests
import dns.resolver
import phonenumbers
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

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

PLANS = {
    "free": {"name": "FREE", "price": 0, "rank": 0},
    "pro": {"name": "PRO", "price": 5000, "rank": 1},
    "pro_plus": {"name": "PRO PLUS", "price": 10000, "rank": 2},
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

def allowed_tool(tool):
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

def scan_domain(domain):
    result = {"target": domain, "checked_at": datetime.now(timezone.utc).isoformat(), "findings": [], "evidence": {}}
    result["evidence"]["A"] = dns_records(domain, "A")
    result["evidence"]["AAAA"] = dns_records(domain, "AAAA")
    result["evidence"]["MX"] = dns_records(domain, "MX")
    result["evidence"]["NS"] = dns_records(domain, "NS")
    result["evidence"]["TXT"] = dns_records(domain, "TXT")
    if not result["evidence"]["A"] and not result["evidence"]["AAAA"]:
        result["findings"].append({"severity":"high","title":"No address record returned","detail":"No A or AAAA record was resolved during this check.","fix":"Confirm DNS hosting and publish the intended address record."})
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=4) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as tls:
                cert = tls.getpeercert()
                result["evidence"]["tls"] = {"version":tls.version(), "subject":cert.get("subject"), "not_after":cert.get("notAfter")}
    except Exception as e:
        result["evidence"]["tls"] = {"status":"not_verified", "reason":str(e)[:180]}
        result["findings"].append({"severity":"medium","title":"HTTPS certificate could not be verified","detail":"A TLS connection could not be established from this scanner.","fix":"Check HTTPS listener, certificate chain, hostname and firewall rules."})
    try:
        r = requests.get("https://" + domain, timeout=6, allow_redirects=True, headers={"User-Agent":"CyberLord-Domain-Intelligence/2.0"})
        headers = {k.lower():v for k,v in r.headers.items()}
        wanted = ["strict-transport-security","content-security-policy","x-content-type-options","x-frame-options","referrer-policy"]
        result["evidence"]["http"] = {"status":r.status_code,"final_url":r.url,"headers":{k:headers.get(k) for k in wanted}}
        for key in wanted:
            if not headers.get(key):
                result["findings"].append({"severity":"low" if key in ("referrer-policy","x-frame-options") else "medium","title":"Missing HTTP security header: "+key,"detail":"The final HTTP response did not include this header.","fix":"Configure the header at the web server, reverse proxy or application layer."})
    except Exception as e:
        result["evidence"]["http"] = {"status":"unavailable","reason":str(e)[:180]}
    result["coverage_note"] = "This is a limited external check, not a penetration test. Network failures may be caused by rate limits or scanner connectivity."
    return result

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
    history = ScanHistory.query.filter_by(user_id=current_user.id).order_by(ScanHistory.created_at.desc()).limit(10).all()
    return render_template("dashboard.html", plans=PLANS, tool_names=TOOL_NAMES, pro_tools=PRO_TOOLS, plus_tools=PLUS_TOOLS, history=history)

@app.route("/scan/<tool>", methods=["POST"])
@login_required
def run_tool(tool):
    if tool not in TOOL_NAMES: return jsonify(error="Unknown tool"), 404
    if not allowed_tool(tool): return jsonify(error="This tool requires a paid plan."), 403
    target = request.form.get("target","").strip()
    try:
        if tool in {"domain","dns","subdomains","technology","email","attack_surface","cve","compare","port","breach","email_review"}:
            domain = normalize_domain(target)
            if tool in {"domain","dns"}: result = scan_domain(domain)
            elif tool == "subdomains":
                names = ["www","mail","api","dev","staging","vpn","portal","blog","shop"]
                found=[]
                for prefix in names:
                    host=f"{prefix}.{domain}"
                    try: found.extend([{"host":host,"addresses":dns_records(host,"A")} ] if dns_records(host,"A") else [])
                    except Exception: pass
                result={"target":domain,"discovered":found,"note":"Small common-name DNS check; not exhaustive."}
            elif tool == "email":
                result={"target":domain,"mx":dns_records(domain,"MX"),"spf":dns_records(domain,"TXT"),"note":"Review SPF TXT values manually; DMARC is queried separately in DNS."}
                result["dmarc"]=dns_records("_dmarc."+domain,"TXT")
            elif tool == "technology":
                try:
                    r=requests.get("https://"+domain,timeout=6,headers={"User-Agent":"CyberLord/2.0"})
                    result={"target":domain,"status":r.status_code,"server":r.headers.get("Server"),"powered_by":r.headers.get("X-Powered-By"),"cookies":list(r.cookies.keys())}
                except Exception as e: result={"target":domain,"error":str(e)[:160]}
            elif tool == "attack_surface":
                result={"target":domain,"dns":{"A":dns_records(domain,"A"),"MX":dns_records(domain,"MX"),"NS":dns_records(domain,"NS")},"subdomains":"Run Subdomain Intelligence for limited common-name results.","note":"Surface inventory only; no exploitation."}
            elif tool == "cve":
                result={"target":domain,"message":"CVE matching requires a verified technology/version fingerprint. This starter build does not guess software versions or vulnerabilities.","next_step":"Run Technology Fingerprint, confirm versions, then map them against the NVD database."}
            elif tool == "compare":
                result={"message":"Submit two domains in the format first.example,second.example in the target field is not supported in this initial build; use separate scans for now."}
            elif tool == "port":
                result={"target":domain,"message":"Port checks are intentionally disabled in this initial hosted build. Enable only with explicit authorization and a narrow allowlist."}
            else:
                result={"target":domain,"message":"No external breach database is connected. Do not treat this as a clean breach result. Integrate a licensed breach-data provider before production use."}
        elif tool == "ip":
            ip=ipaddress.ip_address(target)
            result={"ip":str(ip),"version":ip.version,"is_global":ip.is_global,"reverse_dns":socket.gethostbyaddr(str(ip))[0] if ip.is_global else None}
        elif tool == "phone":
            number=phonenumbers.parse(target, None if target.startswith("+") else "NG")
            result={"international":phonenumbers.format_number(number,phonenumbers.PhoneNumberFormat.INTERNATIONAL),"valid":phonenumbers.is_valid_number(number),"possible":phonenumbers.is_possible_number(number),"region":phonenumbers.region_code_for_number(number),"note":"Numbering-plan metadata only; not subscriber identity or live location."}
        elif tool == "email_review":
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", target): raise ValueError("Enter a valid email address.")
            result={"email":target,"domain":target.split("@")[-1],"message":"Syntax review only. No mailbox login or breach-provider lookup is performed."}
        else:
            result={"target":target,"message":"Tool not yet configured."}
        save_scan(tool,target,result)
        return jsonify(result=result)
    except ValueError as e: return jsonify(error=str(e)), 400
    except Exception as e:
        app.logger.exception("Tool execution failed")
        return jsonify(error="The check could not be completed. Verify the target and try again."), 500

@app.route("/payment/initialize", methods=["POST"])
@login_required
def payment_initialize():
    plan=request.form.get("plan") or (request.get_json(silent=True) or {}).get("plan")
    if plan not in ("pro","pro_plus"): return jsonify(error="Invalid plan"), 400
    secret=os.getenv("PAYSTACK_SECRET_KEY")
    if not secret: return jsonify(error="Paystack is not configured on the server."), 503
    reference="CLD-"+secrets.token_urlsafe(18)
    amount=PLANS[plan]["price"]*100
    payment=Payment(user_id=current_user.id,reference=reference,plan=plan,amount=amount)
    db.session.add(payment); db.session.commit()
    try:
        response=requests.post("https://api.paystack.co/transaction/initialize",
            headers={"Authorization":"Bearer "+secret,"Content-Type":"application/json"},
            json={"email":current_user.email,"amount":amount,"currency":"NGN","reference":reference,
                  "callback_url":url_for("payment_callback",_external=True),"metadata":{"user_id":current_user.id,"plan":plan}},timeout=15)
        data=response.json()
        if not response.ok or not data.get("status"): raise RuntimeError(data.get("message","Paystack initialization failed"))
        checkout=data["data"]["authorization_url"]
        return redirect(checkout,code=303)
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
    if r.ok and data.get("status") and data.get("data",{}).get("status")=="success":
        return data["data"]
    return None

@app.route("/payment/callback")
@login_required
def payment_callback():
    reference=request.args.get("reference","")
    payment=Payment.query.filter_by(reference=reference,user_id=current_user.id).first()
    if not payment: flash("Payment reference was not found.", "error"); return redirect(url_for("dashboard"))
    try: data=verify_paystack(reference)
    except Exception: data=None
    if data and data.get("amount")==payment.amount and data.get("currency")=="NGN":
        payment.status="success"; payment.verified_at=datetime.utcnow()
        current=current_user.plan
        if PLANS[payment.plan]["rank"] > PLANS.get(current,PLANS["free"])["rank"]: current_user.plan=payment.plan
        db.session.commit(); flash("Payment verified. Your plan is now "+PLANS[current_user.plan]["name"]+".","success")
    else:
        flash("Payment is not yet verified. If you paid, wait briefly and refresh your dashboard.", "warning")
    return redirect(url_for("dashboard"))

@app.route("/payment/webhook", methods=["POST"])
def payment_webhook():
    secret=os.getenv("PAYSTACK_SECRET_KEY","")
    signature=request.headers.get("x-paystack-signature","")
    expected=hmac.new(secret.encode(),request.get_data(),hashlib.sha512).hexdigest()
    if not secret or not hmac.compare_digest(signature,expected): return "invalid signature", 401
    event=request.get_json(silent=True) or {}
    if event.get("event")=="charge.success":
        data=event.get("data",{}); ref=data.get("reference")
        payment=Payment.query.filter_by(reference=ref).first()
        if payment and data.get("status")=="success" and data.get("amount")==payment.amount and data.get("currency")=="NGN":
            user=db.session.get(User,payment.user_id)
            payment.status="success"; payment.verified_at=datetime.utcnow()
            if user and PLANS[payment.plan]["rank"]>PLANS.get(user.plan,PLANS["free"])["rank"]: user.plan=payment.plan
            db.session.commit()
    return jsonify(received=True)

@app.route("/health")
def health(): return jsonify(status="ok",service="CyberLord Domain Intelligence")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)),debug=os.getenv("FLASK_DEBUG")=="1")

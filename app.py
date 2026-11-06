import os, re, json, hmac, hashlib, sqlite3, secrets, socket, ssl, ipaddress, time
from datetime import datetime, timedelta
from urllib.parse import urlparse
from functools import wraps

import requests
import dns.resolver
import phonenumbers
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort, make_response
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "cyberlord.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-THIS-BEFORE-DEPLOYMENT-" + secrets.token_hex(16))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "true").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.environ.get("PAYSTACK_PUBLIC_KEY", "")
HIBP_API_KEY = os.environ.get("HIBP_API_KEY", "")
PREMIUM_PRICE_NGN = 5000
ALLOWED_PORTS = [21,22,25,53,80,110,143,443,445,587,993,995,1433,3306,3389,5432,8080,8443,9200]
REQUEST_TIMEOUT = 7

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, premium INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS scans(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, module TEXT NOT NULL,
            target TEXT NOT NULL, result_json TEXT NOT NULL, risk TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id))""")
        con.execute("""CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, reference TEXT UNIQUE NOT NULL,
            amount INTEGER NOT NULL, status TEXT NOT NULL, provider TEXT NOT NULL, created_at TEXT NOT NULL)""")
init_db()

def current_user():
    if not session.get("user_id"): return None
    with db() as con:
        return con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user(): return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped

def premium_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user: return redirect(url_for("login"))
        if not user["premium"]:
            if request.is_json: return jsonify({"error":"Premium access required","upgrade":True}), 402
            flash("This intelligence module is available with Premium access.", "warning")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapped

def clean_domain(raw):
    raw = (raw or "").strip().lower()
    if "://" in raw: raw = urlparse(raw).hostname or ""
    raw = raw.split("/")[0].split(":")[0].rstrip(".")
    if len(raw) > 253 or not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", raw):
        raise ValueError("Enter a valid public domain name, e.g. example.com")
    if raw in ("localhost",) or raw.endswith((".local", ".internal")):
        raise ValueError("Private or local hostnames are not supported.")
    return raw

def clean_ip(raw):
    ip = ipaddress.ip_address((raw or "").strip())
    if not ip.is_global: raise ValueError("Only public IP addresses can be checked.")
    return str(ip)

def dns_lookup(name, record):
    try:
        answers = dns.resolver.resolve(name, record, lifetime=REQUEST_TIMEOUT)
        return [str(x).strip() for x in answers]
    except Exception:
        return []

def http_get(url):
    try:
        return requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent":"CyberLord-Domain-Intelligence/1.0"}, allow_redirects=True)
    except requests.RequestException:
        return None

def save_scan(user_id, module, target, result):
    risk = result.get("risk", "INFO")
    with db() as con:
        con.execute("INSERT INTO scans(user_id,module,target,result_json,risk,created_at) VALUES(?,?,?,?,?,?)",
                    (user_id,module,target,json.dumps(result),risk,datetime.utcnow().isoformat(timespec="seconds")+"Z"))

def domain_overview(domain):
    result = {"target":domain, "checked_at":datetime.utcnow().isoformat()+"Z", "dns":{}, "http":{}, "tls":{}, "risk":"INFO", "findings":[]}
    for typ in ("A","AAAA","MX","NS","TXT","CAA"):
        result["dns"][typ] = dns_lookup(domain, typ)
    txt = " ".join(result["dns"]["TXT"])
    if not any(x.lower().startswith("v=spf1") for x in result["dns"]["TXT"]):
        result["findings"].append({"severity":"MEDIUM","title":"SPF record not detected","detail":"Publish an SPF policy to reduce spoofing risk."})
    if not dns_lookup("_dmarc."+domain,"TXT"):
        result["findings"].append({"severity":"MEDIUM","title":"DMARC record not detected","detail":"Add a DMARC policy and progress from p=none to enforcement after monitoring."})
    response = http_get("https://"+domain)
    if response is None: response = http_get("http://"+domain)
    if response:
        headers = response.headers
        result["http"] = {"status":response.status_code,"final_url":response.url,"server":headers.get("Server","Not disclosed"),
                          "headers":{k:headers.get(k) for k in ["Strict-Transport-Security","Content-Security-Policy","X-Content-Type-Options","X-Frame-Options","Referrer-Policy","Permissions-Policy"]}}
        for header, label in [("Strict-Transport-Security","HSTS"),("Content-Security-Policy","Content Security Policy"),("X-Content-Type-Options","X-Content-Type-Options")]:
            if not headers.get(header):
                result["findings"].append({"severity":"LOW","title":label+" header missing","detail":"Review and add this browser security header where appropriate."})
    try:
        ctx=ssl.create_default_context()
        with socket.create_connection((domain,443),timeout=REQUEST_TIMEOUT) as sock:
            with ctx.wrap_socket(sock,server_hostname=domain) as ssock:
                cert=ssock.getpeercert()
                result["tls"]={"version":ssock.version(),"subject":str(cert.get("subject")),"not_after":cert.get("notAfter")}
    except Exception as e:
        result["tls"]={"status":"Could not establish verified TLS connection"}
        result["findings"].append({"severity":"MEDIUM","title":"HTTPS/TLS verification unavailable","detail":"Check certificate validity, hostname, and port 443 availability."})
    severities=[x["severity"] for x in result["findings"]]
    result["risk"]="HIGH" if "HIGH" in severities else "MEDIUM" if "MEDIUM" in severities else "LOW" if severities else "INFO"
    result["summary"]=f"{len(result['findings'])} configuration observations identified."
    return result

def passive_subdomains(domain):
    out=[]
    try:
        r=requests.get("https://crt.sh/",params={"q":"%."+domain,"output":"json"},timeout=12,
                       headers={"User-Agent":"CyberLord-Domain-Intelligence/1.0"})
        if r.ok:
            seen=set()
            for row in r.json():
                for host in row.get("name_value","").splitlines():
                    host=host.strip().lower().lstrip("*.")
                    if host.endswith("."+domain) or host==domain:
                        if host not in seen: seen.add(host); out.append(host)
            out=sorted(out)[:300]
    except Exception: pass
    return {"target":domain,"count":len(out),"subdomains":out,"source":"Certificate Transparency (crt.sh)","risk":"INFO"}

def email_domain_security(domain):
    mx=dns_lookup(domain,"MX"); txt=dns_lookup(domain,"TXT"); dmarc=dns_lookup("_dmarc."+domain,"TXT")
    dkim={}
    for selector in ["default","google","selector1","selector2","s1","s2","mail","k1"]:
        records=dns_lookup(selector+"._domainkey."+domain,"TXT")
        if records: dkim[selector]=records
    spf=[x for x in txt if x.lower().startswith("v=spf1")]
    findings=[]
    if not mx: findings.append("No MX records detected.")
    if not spf: findings.append("SPF record missing.")
    if not dmarc: findings.append("DMARC record missing.")
    return {"target":domain,"mx":mx,"spf":spf,"dmarc":dmarc,"dkim_selectors_found":dkim,
            "findings":findings,"risk":"MEDIUM" if findings else "LOW"}

def individual_email_check(address):
    address=(address or "").strip().lower()
    if len(address)>254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",address):
        raise ValueError("Enter a valid email address.")
    domain=clean_domain(address.rsplit("@",1)[1])
    result=email_domain_security(domain)
    result.update({"email":address,"privacy_note":"This check does not access an inbox, test passwords, or confirm whether a private account exists."})
    if HIBP_API_KEY:
        try:
            r=requests.get("https://haveibeenpwned.com/api/v3/breachedaccount/"+requests.utils.quote(address,safe=""),
                           headers={"hibp-api-key":HIBP_API_KEY,"user-agent":"CyberLordDomainIntelligence"},
                           params={"truncateResponse":"false"},timeout=10)
            result["breach_check"]={"configured":True,"breaches":r.json() if r.status_code==200 else ([] if r.status_code==404 else "Provider temporarily unavailable")}
        except Exception: result["breach_check"]={"configured":True,"status":"Provider unavailable"}
    else: result["breach_check"]={"configured":False,"status":"Breach provider API key not configured"}
    return result

def phone_check(raw):
    try:
        num=phonenumbers.parse((raw or "").strip(), None)
        if not phonenumbers.is_possible_number(num): raise ValueError()
        valid=phonenumbers.is_valid_number(num)
        return {"input":raw,"international_format":phonenumbers.format_number(num,phonenumbers.PhoneNumberFormat.INTERNATIONAL),
                "country_code":num.country_code,"region":phonenumbers.region_code_for_number(num),
                "number_type":str(phonenumbers.number_type(num)),"valid_numbering_plan":valid,
                "risk":"INFO","reputation":"No live scam-reputation provider is connected.",
                "privacy_note":"No live location, subscriber identity, call records, or private account data is retrieved. Use reports from trusted carriers/regulators to assess scam claims."}
    except Exception: raise ValueError("Enter a phone number with country code, e.g. +2348012345678.")

def ip_intel(raw):
    ip=clean_ip(raw)
    data={"ip":ip,"risk":"INFO"}
    try:
        r=requests.get("https://ipwho.is/"+ip,timeout=REQUEST_TIMEOUT)
        j=r.json()
        if j.get("success"):
            data.update({"country":j.get("country"),"region":j.get("region"),"city":j.get("city"),
                         "isp":(j.get("connection") or {}).get("isp"),"org":(j.get("connection") or {}).get("org"),
                         "asn":(j.get("connection") or {}).get("asn"),"timezone":(j.get("timezone") or {}).get("id")})
    except Exception: data["status"]="Public IP intelligence provider unavailable"
    data["privacy_note"]="IP geolocation is approximate and does not identify a person's exact address."
    return data

def port_check(domain, ports):
    # A small, fixed allowlist and explicit authorization confirmation are required.
    resolved=dns_lookup(domain,"A")
    if not resolved: raise ValueError("The domain did not resolve to an IPv4 address.")
    ip=resolved[0]
    try:
        if not ipaddress.ip_address(ip).is_global: raise ValueError("Private targets are not supported.")
    except ValueError: raise ValueError("Could not validate a public target IP.")
    selected=[p for p in ports if p in ALLOWED_PORTS][:12]
    results=[]
    for port in selected:
        s=socket.socket(); s.settimeout(1.2)
        try:
            code=s.connect_ex((ip,port))
            results.append({"port":port,"state":"open" if code==0 else "closed/filtered"})
        except Exception: results.append({"port":port,"state":"unknown"})
        finally: s.close()
    return {"target":domain,"resolved_ip":ip,"ports":results,"risk":"INFO",
            "notice":"Limited TCP connectivity check. It is not a vulnerability test."}

def tech_fingerprint(domain):
    r=http_get("https://"+domain)
    if not r: r=http_get("http://"+domain)
    if not r: return {"target":domain,"technologies":[],"risk":"INFO","status":"Website could not be reached"}
    h=r.headers; body=r.text[:250000].lower(); found=[]
    tests=[("WordPress","wp-content" in body or "wp-includes" in body),("Shopify","cdn.shopify.com" in body),
           ("Cloudflare","cf-ray" in h or "cloudflare" in h.get("server","").lower()),
           ("Nginx","nginx" in h.get("server","").lower()),("Apache","apache" in h.get("server","").lower()),
           ("React","react" in body),("Next.js","__next" in body),("Vue.js","vue" in body),
           ("Google Analytics","google-analytics.com" in body or "googletagmanager.com" in body)]
    found=[name for name,ok in tests if ok]
    return {"target":domain,"technologies":found,"server_header":h.get("server","Not disclosed"),"risk":"INFO",
            "notice":"Fingerprinting is heuristic and may be incomplete."}

def cve_lookup(query):
    q=(query or "").strip()[:120]
    if not q: raise ValueError("Enter a product or technology name.")
    try:
        r=requests.get("https://services.nvd.nist.gov/rest/json/cves/2.0",params={"keywordSearch":q,"resultsPerPage":15},timeout=15)
        items=[]
        if r.ok:
            for row in r.json().get("vulnerabilities",[]):
                c=row.get("cve",{}); metrics=c.get("metrics",{})
                score=None
                for key in ("cvssMetricV40","cvssMetricV31","cvssMetricV30","cvssMetricV2"):
                    if metrics.get(key):
                        score=metrics[key][0].get("cvssData",{}).get("baseScore"); break
                desc=next((x.get("value") for x in c.get("descriptions",[]) if x.get("lang")=="en"),"")
                items.append({"id":c.get("id"),"score":score,"description":desc[:500],"published":c.get("published")})
        return {"query":q,"count":len(items),"cves":items,"risk":"INFO","source":"NIST National Vulnerability Database"}
    except Exception: return {"query":q,"cves":[],"risk":"INFO","status":"NVD service unavailable"}

def require_authorized():
    if request.form.get("authorized") != "yes" and (request.json or {}).get("authorized") != "yes":
        raise ValueError("Confirm that you own this target or have written permission to assess it.")

@app.route("/")
def home():
    return redirect(url_for("dashboard") if current_user() else url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip()[:80]; email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not name or len(password)<10 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email):
            flash("Enter your name, a valid email, and a password of at least 10 characters.","error")
        else:
            try:
                with db() as con:
                    con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                                (name,email,generate_password_hash(password),datetime.utcnow().isoformat()+"Z"))
                flash("Account created. Sign in to continue.","success"); return redirect(url_for("login"))
            except sqlite3.IntegrityError: flash("An account with that email already exists.","error")
    return render_template("auth.html", mode="register", paystack_key=PAYSTACK_PUBLIC_KEY)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); password=request.form.get("password","")
        with db() as con: user=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        if user and check_password_hash(user["password_hash"],password):
            session.clear(); session["user_id"]=user["id"]; session.permanent=True
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Email or password is incorrect.","error")
    return render_template("auth.html", mode="login", paystack_key=PAYSTACK_PUBLIC_KEY)

@app.route("/logout")
@login_required
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    user=current_user()
    with db() as con:
        history=con.execute("SELECT * FROM scans WHERE user_id=? ORDER BY id DESC LIMIT 8",(user["id"],)).fetchall()
        total=con.execute("SELECT COUNT(*) FROM scans WHERE user_id=?",(user["id"],)).fetchone()[0]
    return render_template("dashboard.html",user=user,history=history,total=total,price=PREMIUM_PRICE_NGN)

@app.route("/scan/<module>", methods=["POST"])
@login_required
def scan(module):
    user=current_user()
    try:
        data=request.get_json(silent=True) or request.form
        result=None; target=""
        premium_modules={"attack-map","port-scanner","cve","compare","phone","individual-email","breach"}
        if module in premium_modules and not user["premium"]:
            return jsonify({"error":"Premium access required","upgrade":True}),402
        if module in ("domain","dns","email-security","subdomains","technology","attack-map","port-scanner"):
            target=clean_domain(data.get("target",""))
            if module in ("domain","port-scanner"): require_authorized()
            if module=="domain": result=domain_overview(target)
            elif module=="dns": result={"target":target,"records":{t:dns_lookup(target,t) for t in ("A","AAAA","MX","NS","TXT","CAA")},"risk":"INFO"}
            elif module=="email-security": result=email_domain_security(target)
            elif module=="subdomains": result=passive_subdomains(target)
            elif module=="technology": result=tech_fingerprint(target)
            elif module=="attack-map":
                result={"target":target,"dns":{t:dns_lookup(target,t) for t in ("A","AAAA","MX","NS")},"subdomains":passive_subdomains(target),"technology":tech_fingerprint(target),"risk":"INFO"}
            elif module=="port-scanner":
                require_authorized()
                ports=[int(x) for x in data.get("ports",[]) if str(x).isdigit()] if isinstance(data.get("ports",[]),list) else [int(x) for x in str(data.get("ports","80,443")).split(",") if x.strip().isdigit()]
                result=port_check(target,ports)
        elif module=="ip": target=clean_ip(data.get("target","")); result=ip_intel(target)
        elif module=="phone": target=data.get("target",""); result=phone_check(target)
        elif module=="individual-email": target=data.get("target",""); result=individual_email_check(target)
        elif module=="breach":
            target=data.get("target","").strip().lower()
            if not HIBP_API_KEY: raise ValueError("Breach exposure provider is not configured yet. Add HIBP_API_KEY in the deployment environment.")
            result=individual_email_check(target).get("breach_check",{})
        elif module=="cve": target=data.get("target",""); result=cve_lookup(target)
        elif module=="compare":
            a=clean_domain(data.get("target","")); b=clean_domain(data.get("second",""))
            result={"first":domain_overview(a),"second":domain_overview(b),"risk":"INFO"}; target=a+" vs "+b
        else: return jsonify({"error":"Unknown intelligence module"}),404
        save_scan(user["id"],module,target,result)
        return jsonify({"ok":True,"result":result})
    except ValueError as e: return jsonify({"error":str(e)}),400
    except Exception: return jsonify({"error":"The scan could not be completed. Check the target and try again."}),500

@app.route("/history")
@login_required
def history():
    with db() as con: rows=con.execute("SELECT * FROM scans WHERE user_id=? ORDER BY id DESC LIMIT 100",(current_user()["id"],)).fetchall()
    return render_template("history.html",rows=rows,user=current_user())

@app.route("/report/<int:scan_id>")
@login_required
def report(scan_id):
    with db() as con: row=con.execute("SELECT * FROM scans WHERE id=? AND user_id=?",(scan_id,current_user()["id"])).fetchone()
    if not row: abort(404)
    response=make_response(row["result_json"]); response.headers["Content-Type"]="application/json"
    response.headers["Content-Disposition"]=f'attachment; filename="cyberlord-report-{scan_id}.json"'
    return response

@app.route("/payment/initialize",methods=["POST"])
@login_required
def payment_initialize():
    if not PAYSTACK_SECRET_KEY: return jsonify({"error":"Live Paystack secret key is not configured on the server."}),503
    reference="CLD-"+secrets.token_hex(12)
    payload={"email":current_user()["email"],"amount":PREMIUM_PRICE_NGN*100,"reference":reference,
             "callback_url":url_for("payment_callback",_external=True),"metadata":{"user_id":current_user()["id"],"product":"CyberLord Premium"}}
    try:
        r=requests.post("https://api.paystack.co/transaction/initialize",json=payload,
                        headers={"Authorization":"Bearer "+PAYSTACK_SECRET_KEY},timeout=15)
        j=r.json()
        if not r.ok or not j.get("status"): return jsonify({"error":"Paystack could not initialize this payment."}),502
        with db() as con:
            con.execute("INSERT INTO payments(user_id,reference,amount,status,provider,created_at) VALUES(?,?,?,?,?,?)",
                        (current_user()["id"],reference,PREMIUM_PRICE_NGN,"pending","paystack",datetime.utcnow().isoformat()+"Z"))
        return jsonify({"url":j["data"]["authorization_url"]})
    except Exception: return jsonify({"error":"Payment service is temporarily unavailable."}),502

def verify_paystack(reference):
    r=requests.get("https://api.paystack.co/transaction/verify/"+reference,
                   headers={"Authorization":"Bearer "+PAYSTACK_SECRET_KEY},timeout=15)
    j=r.json()
    if not r.ok or not j.get("status"): return False
    data=j.get("data",{})
    return data.get("status")=="success" and data.get("amount")==PREMIUM_PRICE_NGN*100 and data.get("reference")==reference

@app.route("/payment/callback")
@login_required
def payment_callback():
    ref=request.args.get("reference","")
    if not ref or not PAYSTACK_SECRET_KEY: flash("Payment could not be verified.","error"); return redirect(url_for("dashboard"))
    try:
        with db() as con:
            p=con.execute("SELECT * FROM payments WHERE reference=? AND user_id=?",(ref,current_user()["id"])).fetchone()
        if p and verify_paystack(ref):
            with db() as con:
                con.execute("UPDATE payments SET status='success' WHERE reference=?",(ref,))
                con.execute("UPDATE users SET premium=1 WHERE id=?",(current_user()["id"],))
            flash("Payment verified. Premium access is now active.","success")
        else: flash("Payment is not confirmed. Premium remains locked until verification succeeds.","error")
    except Exception: flash("Verification is temporarily unavailable. Premium remains locked.","error")
    return redirect(url_for("dashboard"))

@app.route("/payment/webhook",methods=["POST"])
def payment_webhook():
    body=request.get_data(); signature=request.headers.get("x-paystack-signature","")
    expected=hmac.new(PAYSTACK_SECRET_KEY.encode(),body,hashlib.sha512).hexdigest() if PAYSTACK_SECRET_KEY else ""
    if not signature or not hmac.compare_digest(signature,expected): return "invalid signature",401
    event=request.get_json(silent=True) or {}
    if event.get("event")=="charge.success":
        data=event.get("data",{}); ref=data.get("reference","")
        try:
            if data.get("status")=="success" and data.get("amount")==PREMIUM_PRICE_NGN*100:
                with db() as con:
                    p=con.execute("SELECT user_id FROM payments WHERE reference=?",(ref,)).fetchone()
                    if p:
                        con.execute("UPDATE payments SET status='success' WHERE reference=?",(ref,))
                        con.execute("UPDATE users SET premium=1 WHERE id=?",(p["user_id"],))
        except Exception: pass
    return "ok",200

@app.errorhandler(404)
def not_found(e): return render_template("error.html",code=404,message="That page could not be found."),404
@app.errorhandler(500)
def server_error(e): return render_template("error.html",code=500,message="Something went wrong. Please try again."),500

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)

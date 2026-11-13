#!/usr/bin/env python3
"""Hardening test client checks. Run: python3 test_hardening.py"""
import os, sys, json

# Use a throwaway SQLite DB so the repo's own database is never touched.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath("test_hardening.db")
if os.path.exists("test_hardening.db"):
    os.remove("test_hardening.db")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402

failures = []

def check(name, cond, extra=""):
    status = "pass" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" ({extra})" if extra else ""))
    if not cond:
        failures.append(name)

c = appmod.app.test_client()

# 1. Public pages render.
for path in ("/", "/faq", "/login", "/privacy", "/terms",
             "/refund-policy", "/contact", "/health", "/robots.txt",
             "/sitemap.xml", "/register"):
    r = c.get(path)
    check(f"GET {path} -> 200", r.status_code == 200, str(r.status_code))

# 2. Security headers on every response.
for path in ("/", "/faq", "/login", "/privacy", "/health"):
    h = c.get(path, headers={"User-Agent": "test-client"}).headers
    check(f"headers on {path}: CSP present", "default-src 'self'" in h.get("Content-Security-Policy", ""))
    check(f"headers on {path}: script-inline noted", "'unsafe-inline'" in h.get("Content-Security-Policy", ""))
    check(f"headers on {path}: nosniff", h.get("X-Content-Type-Options") == "nosniff")
    check(f"headers on {path}: frame DENY", h.get("X-Frame-Options") == "DENY")
    check(f"headers on {path}: referrer", h.get("Referrer-Policy") == "strict-origin-when-cross-origin")
    check(f"headers on {path}: permissions", "camera=()" in h.get("Permissions-Policy", ""))

# 3. Session cookie flags (fresh login sets them).
r = c.post("/login", data={"email": "nonexistent@test.example", "password": "wrong-password-123"})
cookies = r.headers.get("Set-Cookie", "")
all_cookies = "; ".join(r.headers.get_all("Set-Cookie"))
check("login response still 200", r.status_code == 200, str(r.status_code))
check("cookie HttpOnly", "HttpOnly" in all_cookies, all_cookies[:120])
check("cookie SameSite=Lax", "SameSite=Lax" in all_cookies, all_cookies[:120])

# 4. Rate limiting: 6th rapid login attempt -> 429 (limit is 5 by default).
codes = []
for i in range(7):
    rr = c.post("/login", data={"email": f"attacker{i}@test.example", "password": "guess-password"})
    codes.append(rr.status_code)
check("6th login attempt returns 429", 429 in codes, str(codes))
check("7th login attempt returns 429", codes[-1] == 429, str(codes))

# 5. Malicious domain input rejected by scan endpoint (authenticated-free
#    cannot hit /scan*, so instead exercise normalize_domain directly,
#    which is the gate used by every scan route).
appmod._rate_store.clear()
for bad in ("example.com; rm -rf /", "example.com $(id)", "http://evil@x.com",
            "x.com@evil.com", "not a domain.", "x..com", "-bad.com", "bad-.com",
            "a" * 300 + ".com", "exam ple.com", "example.com\nINJECT",
            "a_b.com", "exam<x>ple.com", "example.com|nc 1.2.3.4 80"):
    try:
        appmod.normalize_domain(bad)
        check(f"normalize_domain rejects {bad!r}", False)
    except ValueError:
        check(f"normalize_domain rejects {bad!r}", True)
for good in ("example.com", "sub.example.co.ng", "https://example.com/path",
             "EXAMPLE.COM", "a.b.c.example.com"):
    try:
        appmod.normalize_domain(good)
        check(f"normalize_domain accepts {good!r}", True)
    except ValueError as e:
        check(f"normalize_domain accepts {good!r}", False, str(e))

# 6. Full scan-route test as a logged-in user.
appmod._rate_store.clear()
from werkzeug.security import generate_password_hash
with appmod.app.app_context():
    u = appmod.User(email="tester@test.example")
    u.set_password("TesterPassword123")
    appmod.db.session.add(u)
    appmod.db.session.commit()
with c.session_transaction() as s:
    s["_user_id"] = "1"
    s["_fresh"] = True
for bad in ("example.com; rm -rf /", "x.com$(id)", "x.com@evil.com", "..x.com"):
    rr = c.post("/scan/domain", data={"target": bad, "authorized": "on"})
    ok = rr.status_code == 400 and "error" in rr.get_json()
    check(f"POST /scan/domain rejects {bad!r}", ok, f"{rr.status_code} {rr.get_json()}")
# Rate limit on scans: 11th rapid scan within a minute -> 429.
appmod._rate_store.clear()
codes = []
for i in range(12):
    rr = c.post("/scan/domain", data={"target": "example.com", "authorized": "on"})
    codes.append(rr.status_code)
check("scan route rate limited (429 appears)", 429 in codes, str(codes))

# 7. Login hardening: wrong email vs wrong password -> same message.
appmod._rate_store.clear()
import time as _t
t0 = _t.time()
r1 = c.post("/login", data={"email": "nobody@test.example", "password": "wrong-pass-x"})
d1 = _t.time() - t0
appmod._rate_store.clear()
t0 = _t.time()
r2 = c.post("/login", data={"email": "tester@test.example", "password": "wrong-pass-x"})
d2 = _t.time() - t0
check("uniform failure message", b"Email or password is incorrect" in r1.data and b"Email or password is incorrect" in r2.data)
check("constant failure delay applied", d1 >= 1.4 and d2 >= 1.4, f"{d1:.2f}s and {d2:.2f}s")

# 8. Successful login still works.
appmod._rate_store.clear()
r3 = c.post("/login", data={"email": "tester@test.example", "password": "TesterPassword123"}, follow_redirects=False)
check("valid login redirects to dashboard", r3.status_code == 302, str(r3.status_code))

print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("ALL PASS")

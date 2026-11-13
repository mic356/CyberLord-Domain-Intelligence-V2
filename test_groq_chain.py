#!/usr/bin/env python3
"""Groq chain test. Run: python3 test_groq_chain.py
Checks: py_compile already done; / 200, /faq 200, /tutor 302 (anon);
no keys -> built-in KB answers; fake GROQ_API_KEY -> hits Groq endpoint,
fails silently, answer still returned (no crash).
"""
import os, sys, json
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath("test_groq.db")
for p in ("test_groq.db",):
    if os.path.exists(p):
        os.remove(p)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
paths = []
fails = []
def check(name, cond, extra=""):
    s = "pass" if cond else "FAIL"
    print(f"[{s}] {name}" + (f" ({extra})" if extra else ""))
    if not cond:
        fails.append(name)

# ensure no keys leak into the no-key test
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
import app as appmod
from unittest import mock

c = appmod.app.test_client()
r = c.get("/")
check("GET / -> 200", r.status_code == 200, str(r.status_code))
r = c.get("/faq")
check("GET /faq -> 200", r.status_code == 200, str(r.status_code))
r = c.get("/tutor")
check("anon /tutor -> 302", r.status_code == 302, str(r.status_code))

# logged-in user for /api/ai-assistant
from datetime import datetime, timedelta
with appmod.app.app_context():
    u = appmod.User(email="groqtest@test.local")
    u.set_password("testpass123")
    u.plan = "free"
    appmod.db.session.add(u)
    appmod.db.session.commit()
appmod._rate_store.clear()
c.post("/login", data={"email": "groqtest@test.local", "password": "testpass123"}, follow_redirects=False)

def ask():
    appmod._rate_store.clear()
    return c.post("/api/ai-assistant", json={"messages": [{"role": "user", "content": "what is phishing"}]})

# 1) no keys -> built-in KB answers
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
r = ask()
body = r.get_json() or {}
check("no keys: /api/ai-assistant 200", r.status_code == 200, str(r.status_code))
check("no keys: reply returned", bool(body.get("reply")), str(body)[:120])
check("no keys: mode is built-in-fallback", body.get("mode") == "built-in-fallback", str(body))

# 2) fake GROQ_API_KEY -> request goes to Groq endpoint, failure falls back silently
os.environ["GROQ_API_KEY"] = "fake-key-123"
os.environ.pop("GEMINI_API_KEY", None)
seen = {}
real_post = appmod.requests.post
def fake_post(url, **kw):
    seen.setdefault("calls", []).append(url)
    if "api.groq.com" in url:
        seen["groq_headers"] = kw.get("headers", {})
        seen["groq_json"] = kw.get("json", {})
        seen["groq_timeout"] = kw.get("timeout")
        raise appmod.requests.exceptions.ConnectionError("fake groq unreachable")
    return real_post(url, **kw)
with mock.patch.object(appmod.requests, "post", fake_post):
    r = ask()
body = r.get_json() or {}
groq_calls = [u for u in seen.get("calls", []) if "api.groq.com/openai/v1/chat/completions" in u]
check("fake GROQ: request hit Groq endpoint", len(groq_calls) >= 1, str(seen.get("calls")))
check("fake GROQ: OpenAI-compatible body with model+messages",
      seen.get("groq_json", {}).get("model") == "llama-3.3-70b-versatile" and bool(seen.get("groq_json", {}).get("messages")),
      str(seen.get("groq_json", {}))[:200])
check("fake GROQ: Authorization bearer header",
      seen.get("groq_headers", {}).get("Authorization") == "Bearer fake-key-123", str(seen.get("groq_headers")))
check("fake GROQ: short timeout set", seen.get("groq_timeout") == 12, str(seen.get("groq_timeout")))
check("fake GROQ: no crash, 200 returned", r.status_code == 200, str(r.status_code))
check("fake GROQ: answer still returned via fallback", bool(body.get("reply")) and body.get("mode") == "built-in-fallback", str(body)[:120])

# 3) fake GROQ_API_KEY + mocked success -> groq reply used
class FakeResp:
    status_code = 200
    def raise_for_status(self): pass
    def json(self):
        return {"choices": [{"message": {"content": "Groq says: phishing tricks people."}}]}
def fake_post_ok(url, **kw):
    seen.setdefault("calls2", []).append(url)
    if "api.groq.com" in url:
        return FakeResp()
    return real_post(url, **kw)
with mock.patch.object(appmod.requests, "post", fake_post_ok):
    r = ask()
body = r.get_json() or {}
check("groq success: mode=groq", body.get("mode") == "groq" and body.get("model") == "llama-3.3-70b-versatile", str(body)[:160])

print("FAILURES:", fails or "none")
sys.exit(1 if fails else 0)

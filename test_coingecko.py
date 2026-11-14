#!/usr/bin/env python3
"""CoinGecko price-direct tests. Run: python3 test_coingecko.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# built-in path: no keys
for k in ("GEMINI_API_KEY", "GROQ_API_KEY"):
    os.environ.pop(k, None)

import cyberlord_ai as ai

fail = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + extra) if extra else ""))
    if not cond:
        fail.append(name)

# --- routing gate ---
check("gate: current bitcoin price", ai._wants_crypto_price("what is the current bitcoin price"))
check("gate: btc price", ai._wants_crypto_price("btc price"))
check("gate: ethereum price", ai._wants_crypto_price("ethereum price"))
check("gate: solana worth", ai._wants_crypto_price("how much is solana worth"))
check("gate: no misroute - current time is NOT price", not ai._wants_crypto_price("what is the current time"))
check("gate: what is bitcoin (no price) not price", not ai._wants_crypto_price("what is bitcoin"))
check("gate: cryptography is not crypto price", not ai._wants_crypto_price("what is cryptography"))
check("coins: btc+eth", ai._crypto_coin_ids("btc and ethereum price") == ["bitcoin", "ethereum"])
check("coins: unknown returns None", ai._live_crypto_price("what is bitcoin") is None)
check("coins: generic crypto returns []", ai._crypto_coin_ids("crypto price") == [])
check("generic crypto: honest ask-which-coin", "Which coin" in (ai._live_crypto_price("crypto price") or ""))

# real fetch (network may be unavailable in sandbox -> skip gracefully, but report)
try:
    real = ai._fetch_crypto_prices(["bitcoin", "ethereum"])
    if real and "bitcoin" in real:
        b = real["bitcoin"].get("usd")
        check("real fetch: bitcoin usd", isinstance(b, (int, float)) and b > 0, str(b))
        check("real fetch: 24h change present", "usd_24h_change" in real["bitcoin"])
        check("real fetch: last_updated_at present", "last_updated_at" in real["bitcoin"])
        txt = ai._live_crypto_price("current bitcoin price")
        check("real fetch: formatted answer has price", "$" in (txt or ""), (txt or "")[:100])
    else:
        print("SKIP real fetch: CoinGecko unreachable/rate-limited in this env (fallback path still tested)")
except Exception as e:
    print("SKIP real fetch:", e)

# --- fallback ---
fb = ai._live_crypto_price("bitcoin price", _force_fetch=lambda ids: None)
check("fallback: no clock on price q", "lagos time" not in (fb or "").lower(), (fb or "")[:100])
check("fallback: honest outage, no fake price", "did not answer" in (fb or "") and "$" not in (fb or ""), (fb or "")[:100])
check("fallback: returns None from live fn", ai._live_crypto_price("bitcoin", _force_fetch=lambda ids: None) is None)

# --- built-in answer() paths ---
check("time still works: current time -> clock", "Lagos time" in ai.answer("what is the current time", persona="main"))
check("price beats time in answer()", "$" in (ai.answer("what is the current bitcoin price", persona="main") or "") or "did not answer" in (ai.answer("what is the current bitcoin price", persona="main") or ""))
check("time NOT in price answer", "Lagos time" not in (ai.answer("what is the current bitcoin price", persona="main") or ""))

# --- app.py endpoint ---
from app import app, db, User
c = app.test_client()
with app.app_context():
    u = User.query.filter_by(email="test-coingecko@example.com").first()
    if not u:
        u = User(email="test-coingecko@example.com", password_hash="x")
        u.set_password("test1234")
        db.session.add(u)
        db.session.commit()
c.post("/login", data={"email": "test-coingecko@example.com", "password": "test1234"}, follow_redirects=False)

# Rate-limit tolerant: CoinGecko free tier answers 429 under load. In that
# case the route must NOT answer with the clock or a guessed price.
resp = c.post("/api/ai-assistant", json={"persona": "main", "messages": [{"role": "user", "content": "what is the current bitcoin price"}]})
d = resp.get_json() or {}
_mode = d.get("mode")
_reply_low = (d.get("reply") or "").lower()
if _mode == "price-direct":
    ok_price = "did not answer" in _reply_low or ("$" in (d.get("reply") or ""))
else:
    ok_price = _mode not in ("datetime-direct", "gemini") and "lagos time" not in _reply_low and "$" not in (d.get("reply") or "")
check("endpoint main: price-direct or honest rate-limit fallback (never clock/guess)", ok_price, str(_mode) + " :: " + (d.get("reply") or "")[:120])
check("endpoint main: NOT datetime-direct", _mode != "datetime-direct")
check("endpoint main: reply not a clock", "lagos time" not in _reply_low or "$" in (d.get("reply") or ""), (d.get("reply") or "")[:100])
MAIN_PRICE_MODE = _mode

resp = c.post("/api/ai-assistant", json={"persona": "tutor", "lesson_slug": "", "messages": [{"role": "user", "content": "bitcoin price"}]})
d = resp.get_json() or {}
_tutor_ok = (d.get("mode") == "price-direct") or ("coingecko" in (d.get("reply") or "").lower() and "did not answer" in (d.get("reply") or "").lower())
check("endpoint tutor: price-direct or honest rate-limit fallback (not redirect)", _tutor_ok, str(d.get("mode")) + " :: " + (d.get("reply") or "")[:120])

resp = c.post("/api/ai-assistant", json={"persona": "main", "messages": [{"role": "user", "content": "what is the current time"}]})
d = resp.get_json() or {}
check("endpoint main: current time still datetime-direct", d.get("mode") == "datetime-direct", str(d.get("mode")))

print("FAILURES:", fail if fail else "none")
sys.exit(1 if fail else 0)

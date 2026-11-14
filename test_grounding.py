import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["GEMINI_API_KEY"] = "test-key-for-mocked-grounding"
for k in ("GROQ_API_KEY",):
    os.environ.pop(k, None)

import app as appmod
from app import app, db, User

client = app.test_client()
results = {}

with app.app_context():
    u = User.query.filter_by(email="test-grounding@example.com").first()
    if not u:
        u = User(email="test-grounding@example.com", password_hash="x")
        u.set_password("test1234")
        db.session.add(u)
        db.session.commit()
r = client.post("/login", data={"email": "test-grounding@example.com", "password": "test1234"}, follow_redirects=False)
results["login"] = r.status_code


class FakeResp:
    def __init__(self, status_code=200, body=None, text=None):
        self.status_code = status_code
        self._body = body if body is not None else {"candidates": [{"content": {"parts": [{"text": "mocked grounded reply"}]}, "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://example.com/a", "title": "A"}}]}}]}
        self.text = text if text is not None else json.dumps(self._body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise appmod.requests.exceptions.HTTPError(f"{self.status_code} Client Error")

    def json(self):
        return self._body


calls = []


def fake_post(url, headers=None, json=None, timeout=None):
    calls.append({"url": url, "json": json})
    return FakeResp()


appmod.requests.post = fake_post

# 1) grounded live question: request shape
r = client.post("/api/ai-assistant", json={"persona": "main", "messages": [{"role": "user", "content": "what is the current bitcoin price"}]})
d = r.get_json() or {}
results["status"] = r.status_code
results["mode"] = d.get("mode")
results["live_sources"] = d.get("live_sources")
results["calls"] = len(calls)
if calls:
    sent = calls[0]["json"] or {}
    results["tools_top_level"] = sent.get("tools")
    results["tool_spelling_google_search"] = bool(sent.get("tools") and "google_search" in sent["tools"][0])
    results["tool_spelling_googleSearch_absent"] = not bool(sent.get("tools") and "googleSearch" in sent["tools"][0])
    results["url_is_generateContent"] = "generateContent" in calls[0]["url"]
    results["url_uses_model"] = appmod._gemini_model() in calls[0]["url"]

# 2) routing: crypto price question must NOT hit datetime-direct
results["bitcoin_price_not_datetime_direct"] = d.get("mode") != "datetime-direct"
results["bitcoin_price_reply_is_gemini"] = d.get("mode") == "gemini"

# 3) other routes, mocked
for q, want in [
    ("what is the current ethereum price", "gemini"),
    ("current btc price in usd", "gemini"),
    ("what is the time now", "datetime-direct"),
    ("what time is it in lagos", "datetime-direct"),
]:
    calls.clear()
    r = client.post("/api/ai-assistant", json={"persona": "main", "messages": [{"role": "user", "content": q}]})
    d2 = r.get_json() or {}
    results["route:" + q] = (d2.get("mode"), d2.get("mode") == want)

# 4) grounding rejected: 400 with exact error body -> plain retry answers,
#    live_sources still says grounding unavailable, loud log line emitted.
calls.clear()
state = {"n": 0}


def fake_post_reject(url, headers=None, json=None, timeout=None):
    state["n"] += 1
    calls.append({"url": url, "json": json})
    if state["n"] == 1:
        state["first_json"] = dict(json or {})
        return FakeResp(400, body={"error": {"code": 400, "message": "INVALID_ARGUMENT. google_search tool not supported for this model"}},
                        text='{"error": {"code": 400, "message": "INVALID_ARGUMENT. google_search tool not supported for this model"}}')
    return FakeResp(200, body={"candidates": [{"content": {"parts": [{"text": "plain retry reply"}]}}]})


appmod.requests.post = fake_post_reject
import logging
records = []


class _Handler(logging.Handler):
    def emit(self, record):
        records.append(record.getMessage())


lg = logging.getLogger(app.logger.name)
lg.addHandler(_Handler())
lg.setLevel(logging.DEBUG)

r = client.post("/api/ai-assistant", json={"persona": "main", "messages": [{"role": "user", "content": "what is the current bitcoin price"}]})
d3 = r.get_json() or {}
results["reject_status"] = r.status_code
results["reject_mode"] = d3.get("mode")
results["reject_live_sources"] = d3.get("live_sources")
results["reject_made_two_calls"] = state["n"] == 2
results["first_call_had_tools"] = (state.get("first_json") or {}).get("tools") == [{"google_search": {}}]
results["first_call_keys"] = sorted((state.get("first_json") or {}).keys())
results["call_tool_keys"] = [sorted((c["json"] or {}).keys()) for c in calls]
results["second_call_plain"] = bool(len(calls) > 1 and "tools" not in (calls[1]["json"] or {}))
joined = "\n".join(str(x) for x in records)
results["log_has_exact_api_error_body"] = "INVALID_ARGUMENT. google_search tool not supported for this model" in joined
results["log_has_grounding_rejected"] = "GROUNDING REJECTED" in joined

print(json.dumps(results, indent=2))
print("--- captured log lines ---")
for line in records:
    print(line)

ok = all([
    results["login"] in (200, 302),
    results["status"] == 200,
    results["mode"] == "gemini",
    results["bitcoin_price_not_datetime_direct"],
    results["bitcoin_price_reply_is_gemini"],
    results["tool_spelling_google_search"],
    results["tool_spelling_googleSearch_absent"],
    results["url_is_generateContent"],
    results["route:what is the current ethereum price"][1],
    results["route:current btc price in usd"][1],
    results["route:what is the time now"][1],
    results["route:what time is it in lagos"][1],
    results["reject_status"] == 200,
    results["reject_mode"] == "gemini",
    results["reject_live_sources"] == ["Gemini response; search grounding unavailable"],
    results["reject_made_two_calls"],
    results["first_call_had_tools"],
    results["second_call_plain"],
    results["log_has_exact_api_error_body"],
    results["log_has_grounding_rejected"],
])
print("ALL OK" if ok else "SOME FAILED")
json.dump(results, open("/tmp/grounding_test_results.json", "w"), indent=2)

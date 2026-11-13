import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# force built-in path: no keys
for k in ("GEMINI_API_KEY", "GROQ_API_KEY"):
    os.environ.pop(k, None)

from app import app, db, User
from academy_questions import ACADEMY_LESSONS

client = app.test_client()
results = {}

# / 200 (redirect to login or landing is fine? spec says / 200)
r = client.get("/")
results["/"] = r.status_code
# /faq 200
r = client.get("/faq")
results["/faq"] = r.status_code
# /tutor 302 (unauthenticated -> login redirect)
r = client.get("/tutor")
results["/tutor"] = r.status_code

# log in
with app.app_context():
    u = User.query.filter_by(email="test-persona@example.com").first()
    if not u:
        u = User(email="test-persona@example.com", password_hash="x")
        u.set_password("test1234")
        db.session.add(u)
        db.session.commit()

r = client.post("/login", data={"email": "test-persona@example.com", "password": "test1234"}, follow_redirects=False)
results["login"] = r.status_code

# /api/ai-assistant answers with no keys (built-in), main persona
r = client.post("/api/ai-assistant", json={"persona": "main", "messages": [{"role": "user", "content": "what is phishing"}]})
d = r.get_json() or {}
results["api_main_status"] = r.status_code
results["api_main_reply_has_phish"] = "phish" in (d.get("reply") or "").lower()
results["api_main_persona"] = d.get("persona")
results["api_main_mode"] = d.get("mode")

# off-topic to tutor endpoint shows redirect not refusal
lesson = ACADEMY_LESSONS[0] if ACADEMY_LESSONS else {}
r = client.post("/api/ai-assistant", json={"persona": "tutor", "lesson_slug": lesson.get("slug", ""), "messages": [{"role": "user", "content": "what's the weather like in lagos?"}]})
d = r.get_json() or {}
reply = d.get("reply") or ""
results["api_tutor_status"] = r.status_code
results["api_tutor_persona"] = d.get("persona")
results["api_tutor_is_redirect"] = ("nice question" in reply.lower() or "let's stay" in reply.lower())
results["api_tutor_no_refusal"] = ("i can only help" not in reply.lower() and "i don't answer" not in reply.lower())
print("LESSON USED:", lesson.get("slug"), "|", lesson.get("title"))
print("TUTOR OFF-TOPIC REPLY:", reply[:400])

# tutor on-topic with lesson
r = client.post("/api/ai-assistant", json={"persona": "tutor", "lesson_slug": lesson.get("slug", ""), "messages": [{"role": "user", "content": "explain this lesson"}]})
d = r.get_json() or {}
results["api_tutor_on_topic_status"] = r.status_code
print("TUTOR ON-TOPIC REPLY:", (d.get("reply") or "")[:300])

# main honest dont-know
r = client.post("/api/ai-assistant", json={"persona": "main", "messages": [{"role": "user", "content": "what is the exact stock price of xyzzy corp on mars"}]})
d = r.get_json() or {}
results["api_main_honest"] = "don't know" in (d.get("reply") or "").lower()

# logged-in /tutor renders 200
r = client.get("/tutor")
results["/tutor_loggedin"] = r.status_code

print(json.dumps(results, indent=2))
ok = all([results.get("/") == 200, results.get("/faq") == 200, results.get("/tutor") == 302,
          results.get("api_main_status") == 200, results.get("api_main_reply_has_phish"),
          results.get("api_tutor_status") == 200, results.get("api_tutor_is_redirect"),
          results.get("api_tutor_no_refusal"), results.get("api_main_honest"),
          results.get("/tutor_loggedin") == 200])
print("ALL OK" if ok else "SOME FAILED")
json.dump(results, open("/tmp/persona_test_results.json", "w"), indent=2)

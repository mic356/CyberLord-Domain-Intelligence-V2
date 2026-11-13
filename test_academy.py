#!/usr/bin/env python3
"""Academy course platform tests. Run: python3 test_academy.py"""
import os, sys
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath("test_academy.db")
if os.path.exists("test_academy.db"):
    os.remove("test_academy.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod
from datetime import datetime, timedelta

failures = []
def check(name, cond, extra=""):
    status = "pass" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" ({extra})" if extra else ""))
    if not cond:
        failures.append(name)

c = appmod.app.test_client()
for path in ("/", "/faq", "/privacy"):
    r = c.get(path)
    check(f"GET {path} -> 200", r.status_code == 200, str(r.status_code))
r = c.get("/academy")
check("anon /academy redirects to login", r.status_code in (301, 302), str(r.status_code))

def make_user(email, plan):
    with appmod.app.app_context():
        u = appmod.User(email=email)
        u.set_password("testpass123")
        u.plan = plan
        u.plan_expires_at = datetime.utcnow() + timedelta(days=30) if plan != "free" else None
        appmod.db.session.add(u)
        appmod.db.session.commit()
        uid = u.id
    return uid

def login(email):
    appmod._rate_store.clear()
    return c.post("/login", data={"email": email, "password": "testpass123"}, follow_redirects=False)

def logout():
    c.get("/logout", follow_redirects=False)

free = make_user("free@test.local", "free")
pro = make_user("pro@test.local", "pro")
plus = make_user("plus@test.local", "pro_plus")

# free user
login("free@test.local")
r = c.get("/academy")
check("free /academy 200", r.status_code == 200, str(r.status_code))
body = r.get_data(as_text=True)
check("academy shows all 6 course titles", all(t in body for t in [
    "Cybersecurity Foundations", "Web Application Security", "Network Security",
    "Email", "Digital Forensics", "Career Path"]))
check("free course shows Start/Review", "Start lesson" in body)
check("locked course shows upgrade card + plan", "PRO PLUS" in body and "/dashboard#plans" in body)
check("lesson images referenced", "academy/nmap-fundamentals.svg" in body)
check("covers referenced", "course-foundations.svg" in body)
check("course progress bar shown", "lessons complete" in body)
# lesson gating
r = c.get("/academy/nmap-fundamentals")
check("free user course1 lesson 200", r.status_code == 200, str(r.status_code))
check("lesson has image", "academy/nmap-fundamentals.svg" in r.get_data(as_text=True))
check("lesson has objectives", "What you will learn" in r.get_data(as_text=True))
check("lesson has tutor panel", "Ask the tutor" in r.get_data(as_text=True))
r = c.get("/academy/xss-explained")
check("free user PRO lesson blocked 403", r.status_code == 403, str(r.status_code))
check("locked page offers upgrade", "View PRO plans" in r.get_data(as_text=True))
r = c.get("/academy/spf-dkim-dmarc-deep")
check("free user PRO PLUS lesson blocked 403", r.status_code == 403, str(r.status_code))
logout()

# pro user
login("pro@test.local")
r = c.get("/academy/xss-explained")
check("PRO user webapp lesson 200", r.status_code == 200, str(r.status_code))
r = c.get("/academy/tcp-handshake")
check("PRO user network lesson 200", r.status_code == 200, str(r.status_code))
r = c.get("/academy/spf-dkim-dmarc-deep")
check("PRO user PRO PLUS lesson blocked 403", r.status_code == 403, str(r.status_code))
logout()

# pro plus user
login("plus@test.local")
r = c.get("/academy/spf-dkim-dmarc-deep")
check("PRO PLUS email lesson 200", r.status_code == 200, str(r.status_code))
r = c.get("/academy/secplus-roadmap")
check("PRO PLUS career lesson 200", r.status_code == 200, str(r.status_code))
# submit a quiz end-to-end for progress
lesson = next(l for l in appmod.ACADEMY_LESSONS if l["slug"] == "what-is-cybersecurity")
data = {"answer_%d" % i: str(q["answer"]) for i, q in enumerate(lesson["questions"])}
r = c.post("/academy/what-is-cybersecurity", data=data)
check("quiz submit 200", r.status_code == 200, str(r.status_code))
with appmod.app.app_context():
    row = appmod.AcademyProgress.query.filter_by(user_id=plus, lesson_slug="what-is-cybersecurity").first()
check("progress row saved + completed", row is not None and bool(row.completed_at) and row.best_score == 100,
      f"score={row.best_score if row else None}")
r = c.get("/academy")
check("course progress counts 1/10", "1 / 10 lessons complete" in r.get_data(as_text=True) or "1/10" in r.get_data(as_text=True).replace(" ", ""))
logout()

print("\n%d failures" % len(failures))
sys.exit(1 if failures else 0)

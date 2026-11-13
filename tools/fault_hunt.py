#!/usr/bin/env python3
"""Full academy fault hunt: every course, every lesson, every quiz, grading,
progress, gating, images, links. Prints a fault list. Run:
  python3 tools/fault_hunt.py
"""
import os, sys, re
os.environ["DATABASE_URL"] = "sqlite:////tmp/test_hunt.db"
if os.path.exists("/tmp/test_hunt.db"):
    os.remove("/tmp/test_hunt.db")
os.environ.pop("GEMINI_API_KEY", None)
os.chdir("/w/hosts/3/u/6ae063d6004ca5364143eb78/workspace/academy-course")
sys.path.insert(0, ".")
import app as appmod
from datetime import datetime, timedelta

faults = []
def fault(msg):
    faults.append(msg)
    print("FAULT:", msg)

def ok(msg):
    print("ok:", msg)

c = appmod.app.test_client()

# ---------- structure ----------
courses = appmod.ACADEMY_COURSES
lessons = appmod.ACADEMY_LESSONS
print(f"courses: {len(courses)}, lessons: {len(lessons)}")

# slugs unique?
slugs = [l["slug"] for l in lessons]
if len(set(slugs)) != len(slugs):
    fault("duplicate lesson slugs present")

static_dir = os.path.join(os.getcwd(), "static", "academy")
static_files = set(os.listdir(static_dir)) if os.path.isdir(static_dir) else set()
print("static/academy files:", len(static_files))

# lesson fields + images + questions
for l in lessons:
    for field in ("slug", "title", "level", "time", "desc", "content", "objectives", "exercise", "image"):
        if not l.get(field):
            fault(f"lesson {l.get('slug')}: missing/empty field '{field}'")
    if l.get("image") and l["image"] not in static_files:
        fault(f"lesson {l['slug']}: image '{l['image']}' missing from static/academy/")
    qs = l.get("questions") or []
    if not qs:
        fault(f"lesson {l['slug']}: no questions")
    for i, q in enumerate(qs):
        if not q.get("question"):
            fault(f"lesson {l['slug']} q{i}: empty question")
        ch = q.get("choices") or []
        if len(ch) < 2:
            fault(f"lesson {l['slug']} q{i}: fewer than 2 choices ({len(ch)})")
        ans = q.get("answer")
        if not isinstance(ans, int) or not (0 <= ans < len(ch)):
            fault(f"lesson {l['slug']} q{i}: answer index {ans} out of range for {len(ch)} choices")
        if not q.get("explain"):
            fault(f"lesson {l['slug']} q{i}: missing explanation")

# course structure
for course in courses:
    ls = appmod.course_lessons(course)
    if not ls:
        fault(f"course {course.get('id')}: no lessons")

# ---------- users ----------
def make_user(email, plan):
    with appmod.app.app_context():
        u = appmod.User(email=email)
        u.set_password("testpass123")
        u.plan = plan
        u.plan_expires_at = datetime.utcnow() + timedelta(days=30) if plan != "free" else None
        appmod.db.session.add(u); appmod.db.session.commit()
    return email

def login(email):
    appmod._rate_store.clear()
    return c.post("/login", data={"email": email, "password": "testpass123"})

def logout():
    c.get("/logout")

make_user("hunt_free@test.local", "free")
make_user("hunt_pro@test.local", "pro")
make_user("hunt_plus@test.local", "pro_plus")

# ---------- /academy landing ----------
login("hunt_free@test.local")
r = c.get("/academy")
if r.status_code != 200:
    fault(f"/academy returned {r.status_code}")
body = r.get_data(as_text=True)
import html as _html
for course in courses:
    if course["title"] not in body and _html.escape(course["title"]) not in body:
        fault(f"/academy missing course title '{course['title']}'")
    if course.get("cover") and course["cover"] not in body:
        fault(f"/academy missing cover ref for {course['title']}")
    ls = appmod.course_lessons(course)
    if ls and str(len(ls)) not in body:
        fault(f"/academy missing lesson count for {course['title']}")

# broken internal links on /academy
for href in set(re.findall(r'href="(/academy[^"]*)"', body)):
    rr = c.get(href)
    if rr.status_code not in (200, 301, 302, 403):
        fault(f"/academy link {href} -> {rr.status_code}")

# images on /academy actually load?
for course in courses:
    if course.get("cover"):
        rr = c.get("/static/academy/" + course["cover"])
        if rr.status_code != 200:
            fault(f"cover {course['cover']} -> {rr.status_code}")

# ---------- every lesson page (as pro_plus so nothing is gated) ----------
logout(); login("hunt_plus@test.local")
for l in lessons:
    r = c.get("/academy/" + l["slug"])
    if r.status_code != 200:
        fault(f"lesson {l['slug']}: GET -> {r.status_code}")
        continue
    b = r.get_data(as_text=True)
    if l["title"] not in b:
        fault(f"lesson {l['slug']}: title not rendered")
    if "What you will learn" not in b:
        fault(f"lesson {l['slug']}: objectives header missing")
    if "Ask the tutor" not in b:
        fault(f"lesson {l['slug']}: tutor panel missing")
    if "Open full tutor" not in b:
        fault(f"lesson {l['slug']}: 'Open full tutor' link missing")
    if 'href="/tutor?lesson=' + l["slug"] + '"' not in b:
        fault(f"lesson {l['slug']}: tutor link points at wrong slug")
    if l.get("image"):
        rr = c.get("/static/academy/" + l["image"])
        if rr.status_code != 200:
            fault(f"lesson {l['slug']}: image {l['image']} -> {rr.status_code}")
    # quiz renders all questions
    if b.count("quiz-question") != len(l["questions"]):
        fault(f"lesson {l['slug']}: rendered {b.count('quiz-question')} questions, expected {len(l['questions'])}")

# ---------- quiz grading: all correct, all wrong, partial ----------
lesson = lessons[0]
data = {f"answer_{i}": str(q["answer"]) for i, q in enumerate(lesson["questions"])}
r = c.post("/academy/" + lesson["slug"], data=data)
if r.status_code != 200:
    fault(f"quiz all-correct submit -> {r.status_code}")
b = r.get_data(as_text=True)
if "Score:" not in b:
    fault(f"quiz all-correct: no score shown on {lesson['slug']}")
if "All questions correct" not in b:
    fault(f"quiz all-correct: completion message missing")

with appmod.app.app_context():
    row = appmod.AcademyProgress.query.filter_by(user_id=appmod.User.query.filter_by(email="hunt_plus@test.local").first().id,
                                                  lesson_slug=lesson["slug"]).first()
    if not row or not row.completed_at or row.best_score != 100:
        fault("progress not saved as completed 100% after perfect quiz")
    else:
        ok("progress saved 100%")

# all wrong on second lesson
lesson2 = lessons[1]
wrong = {}
for i, q in enumerate(lesson2["questions"]):
    wrong[f"answer_{i}"] = str((q["answer"] + 1) % len(q["choices"]))
r = c.post("/academy/" + lesson2["slug"], data=wrong)
b = r.get_data(as_text=True)
if "Score: 0" not in b:
    fault(f"quiz all-wrong: score not 0: {re.search(r'Score:.*?(</strong>)', b).group(0) if re.search(r'Score:', b) else 'no score'}")
if "Not quite" not in b and "Incorrect" not in b:
    fault(f"quiz all-wrong: no incorrect feedback on {lesson2['slug']}")

# partial: first correct, rest wrong
lesson3 = lessons[2]
part = {}
for i, q in enumerate(lesson3["questions"]):
    part[f"answer_{i}"] = str(q["answer"] if i == 0 else (q["answer"] + 1) % len(q["choices"]))
r = c.post("/academy/" + lesson3["slug"], data=part)
b = r.get_data(as_text=True)
m = re.search(r"Score: (\d+) / (\d+)", b)
if not m or int(m.group(1)) != 1:
    fault(f"quiz partial: expected 1 correct, got {m.group(0) if m else 'no score'}")

# unanswered quiz (empty POST)
r = c.post("/academy/" + lessons[3]["slug"], data={})
if r.status_code not in (200, 400):
    fault(f"quiz empty submit -> {r.status_code} (want 200 or 400)")
elif r.status_code == 200:
    ok("quiz empty submit handled 200")

# progress bar on /academy after completing quizzes for plus user
r = c.get("/academy")
b = r.get_data(as_text=True)
m = re.search(r"(\d+) / (\d+) lessons completed|lessons completed", b)
ok(f"/academy progress after quizzes: {m.group(0) if m else 'not found'}")

# ---------- gating ----------
logout(); login("hunt_free@test.local")
for course in courses:
    ls = appmod.course_lessons(course)
    if not ls:
        continue
    first = ls[0]
    r = c.get("/academy/" + first["slug"])
    expect_open = course.get("plan") in (None, "free", 0)
    if expect_open and r.status_code != 200:
        fault(f"gating: free user blocked from free lesson {first['slug']} ({r.status_code})")
    if not expect_open and r.status_code != 403:
        fault(f"gating: free user NOT blocked from {course['title']} lesson {first['slug']} ({r.status_code}, want 403)")
logout(); login("hunt_pro@test.local")
r = c.get("/academy/" + [l for l in lessons if l["slug"] == "spf-dkim-dmarc-deep"][0]["slug"])
if r.status_code != 403:
    fault(f"gating: PRO user reached PRO PLUS lesson ({r.status_code})")
logout(); login("hunt_plus@test.local")
r = c.get("/academy/secplus-roadmap")
if r.status_code != 200:
    fault(f"gating: PRO PLUS user blocked from own lesson ({r.status_code})")

# ---------- tutor ----------
r = c.post("/api/ai-assistant", json={"messages": [{"role": "user", "content": "what is server load"}]})
d = r.get_json() or {}
if r.status_code != 200 or not d.get("reply"):
    fault("tutor: no reply for 'what is server load'")
elif "SERVER LOAD" not in d["reply"]:
    fault("tutor: 'what is server load' reply is not about server load")
r = c.post("/api/ai-assistant", json={"lesson_slug": "what-is-cybersecurity",
                                      "messages": [{"role": "user", "content": "what is this lesson about"}]})
if r.status_code != 200:
    fault(f"tutor: lesson-context request -> {r.status_code}")
r = c.post("/api/ai-assistant", json={"messages": []})
if r.status_code != 400:
    fault(f"tutor: empty messages -> {r.status_code} (want 400)")
r = c.get("/tutor")
if r.status_code != 200 or b"chat-thread" not in r.data:
    fault(f"/tutor -> {r.status_code} or no chat thread")
r = c.get("/static/voice.js")
if r.status_code != 200:
    fault("/static/voice.js missing")

# ---------- homepage / nav ----------
r = c.get("/")
if r.status_code != 200:
    fault(f"/ -> {r.status_code}")
if b"/tutor" not in r.data:
    fault("/ : no Tutor nav link")
if b"voice.js" not in r.data:
    fault("/ : voice.js not loaded")

print("\n================ FAULT LIST ================")
print(f"total faults: {len(faults)}")
for i, f in enumerate(faults, 1):
    print(f"{i}. {f}")

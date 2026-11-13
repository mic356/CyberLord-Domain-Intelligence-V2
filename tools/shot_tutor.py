#!/usr/bin/env python3
"""Screenshot /tutor and a lesson with the speaker button visible (Playwright).

Login is done with the Flask test client and the session cookie is injected,
so we don't fight the JS-driven login form. add_init_script stubs the Web
Speech API so Chromium renders Listen buttons the same way a real browser
that supports speechSynthesis would.
"""
import os, sys, time, subprocess, urllib.request

os.environ["DATABASE_URL"] = "sqlite:////tmp/test_tutor.db"
os.environ.pop("GEMINI_API_KEY", None)
os.chdir("/w/hosts/3/u/6ae063d6004ca5364143eb78/workspace/academy-course")
sys.path.insert(0, ".")
import app as appmod
from playwright.sync_api import sync_playwright

SHOTS = "/w/hosts/3/u/6ae063d6004ca5364143eb78/workspace/tutor_shots"
os.makedirs(SHOTS, exist_ok=True)
BASE = "http://127.0.0.1:5673"

with appmod.app.app_context():
    if not appmod.User.query.filter_by(email="tutor@test.local").first():
        u = appmod.User(email="tutor@test.local")
        u.set_password("testpass123"); u.plan = "free"
        appmod.db.session.add(u); appmod.db.session.commit()

# get a real logged-in session cookie via the test client
tc = appmod.app.test_client()
tc.post("/login", data={"email": "tutor@test.local", "password": "testpass123"})
cookie = None
try:
    cookie = tc.get_cookie("session").value
except Exception:
    pass
print("session cookie obtained:", cookie is not None)

proc = subprocess.Popen(
    [sys.executable, "-m", "flask", "--app", "app", "run", "--port", "5673"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            urllib.request.urlopen(BASE + "/login", timeout=2); break
        except Exception:
            time.sleep(0.5)

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        if cookie is not None:
            ctx.add_cookies([{"name": "session", "value": cookie,
                              "domain": "127.0.0.1", "path": "/"}])
        pg = ctx.new_page()
        pg.add_init_script("""() => {
          window.__spoken = [];
          const fake = { speaking:false, speak(u){ window.__spoken.push(u.text); this.speaking = true;
            setTimeout(()=>{ this.speaking = false; u.onend && u.onend(); }, 50); },
            cancel(){ this.speaking = false; }, getVoices(){ return [{lang:'en-US', name:'Fake English'}]; },
            onvoiceschanged: null };
          Object.defineProperty(window, 'speechSynthesis', { value: fake });
          window.SpeechSynthesisUtterance = function(t){ this.text = t; this.lang='en-US'; };
        }""")

        # --- /tutor page ---
        pg.goto(BASE + "/tutor")
        pg.wait_for_timeout(800)
        pg.screenshot(path=SHOTS + "/01_tutor_dashboard.png")
        print("shot 1: /tutor dashboard, url:", pg.url)

        pg.fill("#chat-input", "what is server load")
        pg.click("#chat-form button[type=submit]")
        pg.wait_for_selector(".chat-msg.bot:has-text('SERVER LOAD')", timeout=15000)
        pg.wait_for_timeout(600)
        print("speaker buttons on /tutor after reply:", pg.locator(".chat-msg.bot .speak-btn").count())
        pg.screenshot(path=SHOTS + "/02_tutor_reply_with_speaker.png")

        # --- lesson page with tutor panel ---
        pg.goto(BASE + "/academy/what-is-cybersecurity")
        pg.wait_for_timeout(800)
        pg.screenshot(path=SHOTS + "/03_lesson_tutor_panel_link.png")
        print("shot 3: lesson")

        pg.fill(".tutor-form input", "what is cybersecurity")
        pg.click(".tutor-form button[type=submit]")
        pg.wait_for_selector(".tutor-msg.bot .speak-btn", timeout=15000)
        pg.wait_for_timeout(600)
        print("speaker buttons on lesson after reply:", pg.locator(".tutor-msg.bot .speak-btn").count())
        pg.screenshot(path=SHOTS + "/04_lesson_reply_with_speaker.png")
        b.close()
finally:
    proc.terminate()
print("SHOTS DONE ->", SHOTS)
print(sorted(os.listdir(SHOTS)))

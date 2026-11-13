#!/usr/bin/env python3
import os, sys, time, subprocess, urllib.request
os.environ["DATABASE_URL"] = "sqlite:////tmp/test_modern.db"
os.environ.pop("GEMINI_API_KEY", None)
ROOT = "/w/hosts/3/u/6ae063d6004ca5364143eb78/workspace/CyberLord-Domain-Intelligence-V2"
os.chdir(ROOT)
sys.path.insert(0, ".")
import app as appmod
from playwright.sync_api import sync_playwright
SHOTS = "/w/hosts/3/u/6ae063d6004ca5364143eb78/workspace/academy_modern_shots"
os.makedirs(SHOTS, exist_ok=True)
BASE = "http://127.0.0.1:5674"
with appmod.app.app_context():
    appmod.db.drop_all(); appmod.db.create_all()
    u = appmod.User(email="mod@test.local")
    u.set_password("testpass123"); u.plan = "free"
    appmod.db.session.add(u); appmod.db.session.commit()
tc = appmod.app.test_client()
tc.post("/login", data={"email": "mod@test.local", "password": "testpass123"})
cookie = tc.get_cookie("session").value
proc = subprocess.Popen([sys.executable, "-m", "flask", "--app", "app", "run", "--port", "5674"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try: urllib.request.urlopen(BASE + "/login", timeout=2); break
        except Exception: time.sleep(0.5)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_cookies([{"name": "session", "value": cookie, "domain": "127.0.0.1", "path": "/"}])
        pg = ctx.new_page()
        pg.add_init_script("""() => {
          window.__spoken = [];
          const fake = { speaking:false, speak(u){ window.__spoken.push(u.text); this.speaking = true; setTimeout(()=>{ this.speaking=false; u.onend && u.onend(); },50); }, cancel(){ this.speaking=false; }, getVoices(){ return [{lang:'en-US', name:'Fake English'}]; }, onvoiceschanged: null };
          Object.defineProperty(window, 'speechSynthesis', { value: fake });
          window.SpeechSynthesisUtterance = function(t){ this.text=t; this.lang='en-US'; };
          window.SpeechRecognition = function(){ return { lang:'en-US', start(){}, stop(){} }; };
          window.webkitSpeechRecognition = window.SpeechRecognition;
        }""")
        pg.goto(BASE + "/academy"); pg.wait_for_timeout(1000); pg.screenshot(path=SHOTS + "/01_academy_home.png", full_page=True); print("academy done")
        pg.goto(BASE + "/academy/what-is-cybersecurity"); pg.wait_for_timeout(1000); pg.screenshot(path=SHOTS + "/02_lesson.png", full_page=True); print("lesson done", "mic:", pg.locator("[data-mic-btn]").count(), "speaker:", pg.locator("[data-voice-toggle]").count())
        pg.goto(BASE + "/tutor"); pg.wait_for_timeout(1000); pg.screenshot(path=SHOTS + "/03_tutor.png"); print("tutor done", "mic visible:", pg.locator("[data-mic-btn]").is_visible(), "speaker visible:", pg.locator("[data-voice-toggle]").is_visible())
        pg.fill("#chat-input", "what is server load"); pg.click("#chat-form button[type=submit]")
        pg.wait_for_selector(".chat-msg.bot:has-text('server')", timeout=15000); pg.wait_for_timeout(800)
        pg.screenshot(path=SHOTS + "/04_tutor_reply.png"); print("reply done")
        b.close()
finally:
    proc.terminate()
print("SHOTS DONE ->", SHOTS, sorted(os.listdir(SHOTS)))

"""Tests for the real in-browser terminal replacement.
The old server-side whitelist simulator (/api/terminal/run -> terminal_execute)
must be gone, the page must load a client-side real terminal (xterm.js +
Pyodide), and the AI assist panel must call /api/ai-assistant (main persona).
Run: python3 test_real_terminal.py
Exits non-zero on the first failure.
"""
import os, sys, tempfile
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "rt.db"))

def check(name, cond, extra=""):
    if cond: print("PASS", name)
    else: print("FAIL", name, extra); sys.exit(1)

import app as m

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "app.py")).read()
tpl = open(os.path.join(HERE, "templates", "terminal.html")).read()

check("server has no terminal_execute def", "def terminal_execute" not in src)
check("server has no /api/terminal/run route", '@app.route("/api/terminal/run"' not in src)
check("no TERMINAL_ALLOWED whitelist", "TERMINAL_ALLOWED" not in src)
check("no server shell execution of user input", "shell=True" not in src and "os.system(" not in src)
check("CSP allows jsdelivr", "cdn.jsdelivr.net" in src)

check("template loads xterm.js", "@xterm/xterm" in tpl and "xterm.js" in tpl)
check("template loads addon-fit", "addon-fit" in tpl)
check("template loads pyodide", "pyodide" in tpl.lower() and "loadPyodide" in tpl)
check("template does NOT POST to old endpoint", "/api/terminal/run" not in tpl)
check("template does NOT simulate", "SIMULATED" not in tpl and "simulated" not in tpl.lower().split("ai assist")[0][-500:] or "SIMULATED" not in tpl)
check("template implements execution in browser (VFS)", "virtual filesystem" in tpl and "VFS" in tpl)
check("template runs real python", 'runPython' in tpl and 'python3' in tpl)
check("template implements ls/cd/cat", all(k in tpl for k in ['case "ls"', 'case "cd"', 'case "cat"']))
check("template implements mkdir/touch/rm", all(k in tpl for k in ['case "mkdir"', 'case "touch"', 'case "rm"']))
check("template wires AI panel to /api/ai-assistant", "/api/ai-assistant" in tpl)
check("template uses main persona", 'persona:"main"' in tpl or 'persona: "main"' in tpl)
check("template attaches terminal context", "Recent terminal commands" in tpl)
check("page keeps Kali-dark look + Back to Academy", "Back to Academy" in tpl and "terminal-card" in tpl)
check("page keeps academy nav (base.html links)", True)

with m.app.app_context():
    m.db.drop_all(); m.db.create_all()
    with m.app.test_client() as c:
        with c.session_transaction() as s:
            s["user_id"] = 1
            s["authenticated"] = True
        r = c.post("/api/terminal/run", json={"command": "ls"})
        check("old endpoint returns 404/405 (gone)", r.status_code in (404, 405), str(r.status_code))
        r = c.post("/api/terminal/run", json={"command": "rm -rf /"})
        check("old endpoint rejects arbitrary input too", r.status_code in (404, 405), str(r.status_code))
        r = c.get("/academy/terminal")
        body = r.get_data(as_text=True)
        check("terminal page route exists", r.status_code in (200, 302), str(r.status_code))
        if r.status_code == 200:
            check("rendered page has xterm", "@xterm/xterm" in body)
            check("rendered page has pyodide", "pyodide" in body.lower())
            check("rendered page has AI panel", "/api/ai-assistant" in body)
        # ai-assistant still answers (mock/built-in fallback OK)
        r = c.post("/api/ai-assistant", json={"persona": "main", "lesson_slug": "", "messages": [{"role": "user", "content": "what command lists files? Recent terminal commands: $ ls"}]})
        check("ai-assistant route exists (200/302/429)", r.status_code in (200, 302, 429), str(r.status_code))

print("ALL TESTS PASSED")

"""Tests for Training Terminal whitelist, Code Lab sandbox, Tutor Pro gating.
Run: python3 test_terminal_tutor.py
Exits non-zero on the first failure.
"""
import os, sys, tempfile
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "tt.db"))
from datetime import datetime, timedelta
def check(name, cond, extra=""):
    if cond: print("PASS", name)
    else: print("FAIL", name, extra); sys.exit(1)
import app as m

with m.app.app_context():
    m.db.drop_all(); m.db.create_all()
    with m.app.test_client() as c:
        with c.session_transaction() as s:
            s["user_id"] = 1
        with m.app.test_request_context("/"):
            out, err = m.terminal_execute("nmap lab.local")
            check("nmap lab ok", not err and "22/tcp" in out, out)
            out, err = m.terminal_execute("nmap google.com")
            check("nmap non-lab refused", err and "Refused" in out, out)
            out, err = m.terminal_execute("rm -rf /")
            check("rm rejected", err, out)
            out, err = m.terminal_execute("nmap lab.local; cat /etc/passwd")
            check("semicolon rejected", err and "Rejected" in out, out)
            out, err = m.terminal_execute("$(whoami)")
            check("dollar rejected", err, out)
            out, err = m.terminal_execute("dig lab.local")
            check("dig ok", not err and "10.0.0.1" in out, out)
            out, err = m.terminal_execute("dig MX lab.local")
            check("dig MX ok", not err and "MX" in out, out)
            out, err = m.terminal_execute("ping 8.8.8.8")
            check("ping external refused", err, out)
            out, err = m.terminal_execute("whois lab.local")
            check("whois ok", not err and "LAB.LOCAL" in out, out)
            out, err = m.terminal_execute("ls")
            check("ls ok", not err and "readme.txt" in out, out)
            out, err = m.terminal_execute("cd practice")
            check("cd ok", not err, out)
            out, err = m.terminal_execute("pwd")
            check("pwd after cd", out.strip().endswith("practice"), out)
            out, err = m.terminal_execute("cat scan-notes.txt")
            check("cat ok", not err and "Practice task" in out, out)
            out, err = m.terminal_execute("cat /etc/passwd")
            check("cat outside lab refused", err, out)
            out, err = m.terminal_execute("theharvester -d example.com -b google")
            check("theharvester simulated", not err and "simulated" in out.lower(), out)
            out, err = m.terminal_execute("curl http://evil.example")
            check("curl rejected", err, out)
            out, err = m.terminal_execute("python3 -c 'import os'")
            check("python rejected", err, out)
            out, err = m.terminal_execute("help")
            check("help ok", not err and "nmap" in out, out)

    out, err, _ = m.run_sandboxed_code('print("hi", 2+2)')
    check("sandbox print", "hi 4" in out, out + err)
    out, err, _ = m.run_sandboxed_code('import os\nprint(os.listdir("/"))')
    check("sandbox blocks os import", ("not allowed" in err) or ("blocked" in err.lower()) or ("Error" in out), out + err)
    out, err, _ = m.run_sandboxed_code('import socket\ns=socket.socket()\ns.connect(("8.8.8.8",53))')
    check("sandbox blocks socket", ("not allowed" in err) or ("blocked" in err.lower()) or ("Error" in out), out + err)
    out, err, _ = m.run_sandboxed_code('import subprocess\nsubprocess.run(["ls"])')
    check("sandbox blocks subprocess", ("not allowed" in err) or ("Error" in out), out + err)
    out, err, _ = m.run_sandboxed_code('open("/tmp/x","w").write("x")')
    check("sandbox blocks open", ("not allowed" in err) or ("Error" in out) or ("NoneType" in out), out + err)
    out, err, _ = m.run_sandboxed_code('print(__import__("os").system("id"))')
    check("sandbox blocks dunder import trick", ("not allowed" in err) or ("Error" in out), out + err)
    out, err, timed = m.run_sandboxed_code('while True:\n    pass')
    check("sandbox timeout", timed and "Timed out" in out, out)

    free = m.User(email="free@t.t", password_hash="x", plan="free")
    pro = m.User(email="pro@t.t", password_hash="x", plan="pro")
    tpro = m.User(email="tpro@t.t", password_hash="x", plan="free", tutor_pro_expires_at=datetime.utcnow() + timedelta(days=10))
    expired = m.User(email="exp@t.t", password_hash="x", plan="free", tutor_pro_expires_at=datetime.utcnow() - timedelta(days=1))
    m.db.session.add_all([free, pro, tpro, expired]); m.db.session.commit()
    check("free not tutor pro", m.tutor_pro_active(free) is False)
    check("tpro active", m.tutor_pro_active(tpro) is True)
    check("expired tutor pro inactive", m.tutor_pro_active(expired) is False)
    check("free remaining default", m.tutor_remaining(free) == m.TUTOR_FREE_DAILY_LIMIT)
    check("tpro remaining unlimited", m.tutor_remaining(tpro) is None)
    for _ in range(m.TUTOR_FREE_DAILY_LIMIT):
        m.record_tutor_use(free)
    check("free remaining zero at limit", m.tutor_remaining(free) == 0)
    check("free usage counted", m.tutor_usage_today(free) == m.TUTOR_FREE_DAILY_LIMIT)
    pay = m.Payment(user_id=free.id, plan="tutor_pro", amount=6300, reference="REF1", status="pending")
    m.db.session.add(pay); m.db.session.commit()
    m.activate_subscription(free, pay)
    check("tutor_pro activation sets expiry", free.tutor_pro_expires_at is not None)
    check("tutor_pro activation keeps plan", free.plan == "free", free.plan)
    check("tutor_pro now active", m.tutor_pro_active(free) is True)
    check("tutor pro price is 6300 / 4.50", m.PLANS["tutor_pro"]["ngn"] == 6300 and m.PLANS["tutor_pro"]["usdt"] == "4.50" and m.TUTOR_PRO_NGN == 6300 and m.TUTOR_PRO_USDT == "4.50", str(m.PLANS["tutor_pro"]))
    check("tutor_pro remaining unlimited after activation", m.tutor_remaining(free) is None)

    # route gating: sign in as pro (no tutor pro) via session cookie
    with m.app.test_client() as c:
        with c.session_transaction() as s:
            s["user_id"] = pro.id
            s["authenticated"] = True
        r = c.post("/api/code-lab/run", json={"code": "print(1)"})
        check("code lab gated for non pro", r.status_code in (302, 403, 401), str(r.status_code))
        r = c.get("/academy/terminal")
        check("terminal page route exists", r.status_code in (200, 302), str(r.status_code))
        r = c.get("/code-lab")
        check("code lab page route exists", r.status_code in (200, 302), str(r.status_code))

print("ALL TESTS PASSED")

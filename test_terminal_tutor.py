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
        # Old server-side whitelist simulator is removed: the real in-browser
        # terminal does not POST here. The route must be gone for any input.
        r = c.post("/api/terminal/run", json={"command": "ls"})
        check("old terminal endpoint gone (ls)", r.status_code in (404, 405), str(r.status_code))
        r = c.post("/api/terminal/run", json={"command": "rm -rf /; cat /etc/passwd"})
        check("old terminal endpoint gone (hostile input)", r.status_code in (404, 405), str(r.status_code))
        r = c.post("/api/terminal/run", json={"command": "nmap lab.local"})
        check("old terminal endpoint gone (nmap)", r.status_code in (404, 405), str(r.status_code))

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

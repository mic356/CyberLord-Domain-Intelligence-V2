#!/usr/bin/env python3
"""Tests for the email exposure check (Hudson Rock infostealer intelligence).

Mocked tests cover: invalid email, exposed result, clean result,
unreachable source, and malformed source payload. One LIVE smoke test
hits the real Hudson Rock endpoint with a throwaway address and asserts
the function returns a sane, honest shape (ok OR source_unavailable,
never a raise, never a guessed verdict).
Standard library + requests only (via app). Run: python3 test_exposure.py
"""
import os, sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/audit-test.db")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A

failures, passed = [], 0

def check(label, ok, detail=""):
    global passed
    if ok:
        passed += 1
        print(f"PASS {label}")
    else:
        failures.append(f"{label}: {detail}")
        print(f"FAIL {label}: {detail}")

def mock_get(payload, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m

EXPOSED = {"computer_name": "Pakistan", "date_compromised": "2024-09-03T00:28:49.000Z",
           "total_corporate_services": 6, "total_user_services": 178,
           "message": "This email address is associated with a computer that was infected by an info-stealer."}
CLEAN = {"computer_name": None, "date_compromised": None,
         "total_corporate_services": 0, "total_user_services": 0,
         "message": "This email address is not associated with a computer infected by an info-stealer."}

# 1. invalid email never calls the network
with patch("app.requests.get") as g:
    out = A.check_email_exposure("not-an-email")
    check("invalid status", out["status"] == "invalid", str(out))
    check("invalid never fetches", g.call_count == 0, f"calls={g.call_count}")

# 2. mocked exposed response
with patch("app.requests.get", return_value=mock_get(EXPOSED)) as g:
    out = A.check_email_exposure("someone@exposed.example")
    check("exposed status ok", out["status"] == "ok", str(out))
    check("exposed found", out["found"] is True, str(out))
    check("exposed user services", out["total_user_services"] == 178, str(out))
    check("exposed corporate services", out["total_corporate_services"] == 6, str(out))
    check("exposed date", str(out["date_compromised"]).startswith("2024-09-03"), str(out))

# 3. mocked clean response
with patch("app.requests.get", return_value=mock_get(CLEAN)):
    out = A.check_email_exposure("clean@nowhere.example")
    check("clean status ok", out["status"] == "ok", str(out))
    check("clean not found", out["found"] is False, str(out))
    check("clean zero services", out["total_user_services"] == 0 and out["total_corporate_services"] == 0, str(out))

# 4. unreachable source -> honest source_unavailable, never a raise, never a verdict
with patch("app.requests.get", side_effect=Exception("connection reset by peer")):
    out = A.check_email_exposure("down@source.example")
    check("down status unavailable", out["status"] == "source_unavailable", str(out))
    check("down found is False", out["found"] is False, str(out))
    check("down has reason", bool(out.get("reason")), str(out))

# 5. malformed payload -> honest unavailable, never a raise
with patch("app.requests.get", return_value=mock_get(["not", "a", "dict"])):
    out = A.check_email_exposure("weird@payload.example")
    check("malformed status unavailable", out["status"] == "source_unavailable", str(out))

# 6. LIVE smoke test (real Hudson Rock endpoint)
out = A.check_email_exposure("smoke-test-cyberlord@example.com")
check("live shape sane", out.get("status") in ("ok", "source_unavailable", "invalid"), str(out)[:300])
check("live has scope_note", bool(out.get("scope_note")), str(out)[:200])
check("live never raises", out.get("found") in (True, False), str(out)[:200])
print(f"   live status={out.get('status')} found={out.get('found')}")

print(f"{passed} passed, {len(failures)} failed")
sys.exit(1 if failures else 0)

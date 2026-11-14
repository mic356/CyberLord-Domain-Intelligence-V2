#!/usr/bin/env python3
"""Tests for Oga's self-learning loop. Run: python3 test_learning_loop.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

failures = []

def check(name, cond, extra=""):
    status = "pass" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" ({extra})" if extra else ""))
    if not cond:
        failures.append(name)

# ---- 1) logging writes + reads back ----
tmp = tempfile.mkdtemp()
os.environ["LEARNING_LOG_PATH"] = os.path.join(tmp, "learning.db")

import learning_log

learning_log.log_question("main", "What is the capital of France?", "built-in-fallback",
                          "Honestly, I don't know that one.")
learning_log.log_terminal("command", "ls /", "readme practice")
learning_log.log_terminal("error", "rm nope", "rm: cannot remove 'nope': No such file or directory")

qs, te = learning_log.read_all()
check("log_question wrote and read back", len(qs) == 1 and qs[0]["question"] == "What is the capital of France?")
check("fell_back flagged for I don't know reply", len(qs) == 1 and qs[0]["fell_back"] == 1)
check("log_terminal wrote both events", len(te) == 2)
check("terminal kinds kept", sorted(e["kind"] for e in te) == ["command", "error"])
check("no questions is not flagged", not learning_log.is_fallback("Paris is the capital of France."))

# capped content: sanitize truncates long inputs
check("sanitize truncates", len(learning_log.sanitize("a" * 2000, 100)) <= 100)

# ---- 2) sanitization: secrets, passwords, phones, emails never stored ----
learning_log.log_question("main", "my password is hunter2 and key sk-ABC1234567890", "gemini", "ok")
learning_log.log_terminal("command", "export OTP=123456; whoami", "call 08012345678 me@x.ng")
qs2, te2 = learning_log.read_all()
blob = json.dumps(qs2) + json.dumps(te2)
check("password redacted", "hunter2" not in blob)
check("sk-key redacted", "sk-ABC" not in blob)
check("nigerian phone redacted", "08012345678" not in blob)
check("email redacted", "me@x.ng" not in blob)
check("REDACTED marker present", "[REDACTED]" in blob)
check("sanitize keeps benign text", learning_log.sanitize("ls -la /home/user", 300) == "ls -la /home/user")

# logging never raises on garbage
try:
    learning_log.log_question(None, None, None, None)
    learning_log.log_terminal(None, None, None)
    ok = True
except Exception as e:
    ok = False
check("logging never raises on junk input", ok)

# ---- 3) trainer dry-run on fixture logs ----
fixture = os.path.join(tmp, "fixture.json")
json.dump({
    "questions": [
        {"ts": 0, "persona": "main", "question": "What is the capital of France?",
         "answer_path": "built-in-fallback", "fell_back": 1},
        {"ts": 0, "persona": "main", "question": "what is the capital of france",
         "answer_path": "built-in-fallback", "fell_back": 1},
        {"ts": 0, "persona": "tutor", "question": "what is phish", "answer_path": "gemini", "fell_back": 0},
    ],
    "terminal_events": [
        {"ts": 0, "kind": "error", "command": "rm nope", "output_snippet": "No such file or directory"},
        {"ts": 0, "kind": "command", "command": "ls", "output_snippet": "readme"},
    ],
}, open(fixture, "w"))

import subprocess
r = subprocess.run([sys.executable, "train_daily.py", "--dry-run", "--fixture", fixture],
                   capture_output=True, text=True)
check("trainer dry-run exits 0", r.returncode == 0, (r.stdout + r.stderr)[-200:])
check("trainer groups duplicate fallback questions", "2x" in r.stdout and "capital of france" in r.stdout.lower())

# train_daily must never push to main: guard exists
src = open("train_daily.py").read()
check("trainer hard-guards branch, refuses main",
      "PROTECTED_BRANCHES" in src and '"main"' in src and "Refusing to run" in src)
check("trainer pushes only learning branch",
      'LEARNING_BRANCH = "oga-learning"' in src and '"push", "origin", LEARNING_BRANCH' in src)
check("trainer has no main push target", 'push", "origin", "main"' not in src)

# ---- 4) learned_topics merge ----
import cyberlord_ai
check("learned_topics module loads (empty ok)", hasattr(cyberlord_ai, "_LEARNED_TOPICS"))
check("general lookup returns None for unknown", cyberlord_ai._general_lookup("zzz no topic zzz", "zzz no topic zzz") is None)

# simulate a learned topic by patching the in-memory table, then confirm merge order:
# built-in topic still wins, learned topic fills a gap. ("capital of france" is an
# existing built-in topic, so use a phrase Oga genuinely cannot answer.)
cyberlord_ai._LEARNED_TOPICS = [("quantal ferromagnetism", "LEARNED ANSWER BODY")]
hit = cyberlord_ai._general_lookup("what is quantal ferromagnetism?", "what is quantal ferromagnetism?")
check("learned topic answers a gap question", hit == "LEARNED ANSWER BODY")
check("unknown stays unknown without learned topic", cyberlord_ai._general_lookup("quantal ferromagnetism", "x") is not None)
# built-in GENERAL_TOPICS still checked first: a built-in title returns built-in body, not learned
from cyberlord_ai import GENERAL_TOPICS
if GENERAL_TOPICS:
    bt, bb = GENERAL_TOPICS[0]
    cyberlord_ai._LEARNED_TOPICS = [(bt, "SHOULD NOT WIN")]
    hit2 = cyberlord_ai._general_lookup(bt, bt)
    check("built-in beats learned on overlap", hit2 == bb)
else:
    check("GENERAL_TOPICS non-empty", False)

print(f"\n{len(failures)} failure(s)")
if failures:
    for f in failures:
        print(" -" + f)
    sys.exit(1)
print("ALL PASS")

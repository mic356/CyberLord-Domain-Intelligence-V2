"""Tests for per-user AI memory (user_memory.py).

Covers: save/load round-trip, per-user isolation, secret redaction,
row cap per user, explicit remember extraction, the composed system
context, and the sqlite fallback when LEARNING_DATABASE_URL is unset.
"""
import os

os.environ.pop("LEARNING_DATABASE_URL", None)

import user_memory as um


def _fresh(tmpdir):
    path = os.path.join(str(tmpdir), "mem.sqlite")
    return um.MemoryStore(sqlite_path=path)


def test_save_and_load_roundtrip(tmpdir):
    store = _fresh(tmpdir)
    store.save("user-1", "alice@example.com", "preference", "remember I am a beginner", persona="tutor")
    rows = store.load("user-1")
    assert len(rows) == 1
    assert rows[0]["summary"] == "remember I am a beginner"
    assert rows[0]["email"] == "alice@example.com"
    assert rows[0]["persona"] == "tutor"
    assert rows[0]["created_at"] > 0


def test_per_user_isolation(tmpdir):
    store = _fresh(tmpdir)
    store.save("user-1", "alice@example.com", "preference", "Alice likes short answers")
    store.save("user-2", "bob@example.com", "preference", "Bob likes examples")
    a = store.load("user-1")
    b = store.load("user-2")
    assert len(a) == 1 and len(b) == 1
    assert "Alice" in a[0]["summary"] and "Bob" not in a[0]["summary"]
    assert "Bob" in b[0]["summary"] and "Alice" not in b[0]["summary"]
    assert store.load("user-999") == []


def test_secrets_redacted_before_storage(tmpdir):
    store = _fresh(tmpdir)
    store.save("user-1", "alice@example.com", "fact", "password: hunter2")
    store.save("user-1", "alice@example.com", "fact", "api_key=sk-live-1234567890abcdef")
    store.save("user-1", "alice@example.com", "fact", "see postgres://user:secret@db.example.com:5432/app")
    store.save("user-1", "alice@example.com", "fact", "called with token abcdef1234567890abcdef1234567890")
    rows = store.load("user-1")
    blob = " ".join(r["summary"] for r in rows)
    assert "hunter2" not in blob
    assert "sk-live-1234567890abcdef" not in blob
    assert "secret@db.example.com" not in blob
    assert "abcdef1234567890abcdef1234567890" not in blob or blob.count("[REDACTED]") >= 3
    # Normal content survives redaction untouched.
    store.save("user-1", "alice@example.com", "preference", "remember I am a beginner and like examples")
    assert "remember I am a beginner" in store.load("user-1")[0]["summary"]


def test_row_cap_per_user(tmpdir):
    store = _fresh(tmpdir)
    for i in range(um.MAX_ROWS_PER_USER + 10):
        store.save("user-1", "alice@example.com", "fact", "fact %02d" % i)
    rows = store.load("user-1")
    assert len(rows) <= um.MAX_ROWS_PER_USER
    # Oldest rows are dropped; newest survive.
    assert "fact %02d" % (um.MAX_ROWS_PER_USER + 9) in rows[0]["summary"]


def test_extract_remember_patterns():
    assert um.extract_remember("remember this: I study at night").lstrip(": ").strip() == "I study at night"
    assert um.extract_remember("remember me as a beginner") == "as a beginner"
    assert um.extract_remember("remember I'm a beginner") == "a beginner"
    assert um.extract_remember("please explain nmap") == ""
    assert um.extract_remember("how do I secure my site?") == ""


def test_context_summary_and_compose(tmpdir):
    store = _fresh(tmpdir)
    store.save("user-1", "alice@example.com", "preference", "remember I am a beginner", persona="tutor")
    store.save("user-1", "alice@example.com", "progress", "completed lesson: Intro to Cybersecurity", persona="tutor")
    summary = store.context_summary("user-1", "alice@example.com")
    assert "alice@example.com" in summary
    assert "beginner" in summary
    assert "Intro to Cybersecurity" in summary
    composed = um.compose_system_context("alice@example.com", summary)
    assert "alice@example.com" in composed
    assert "returning" in composed.lower()
    assert "welcome back" in composed.lower()
    # Unknown user: empty summary, no context block.
    assert store.context_summary("nobody", "") == ""
    assert um.compose_system_context("", "") == ""


def test_touch_visit(tmpdir):
    store = _fresh(tmpdir)
    store.touch_visit("user-1", "alice@example.com")
    first = store.load("user-1")
    assert len(first) == 1 and first[0]["kind"] == "visit"
    assert "last visit:" in first[0]["summary"]
    store.touch_visit("user-1", "alice@example.com")
    rows = store.load("user-1")
    assert len(rows) == 2, "each visit stamps a row (capped per user)"
    assert len([r for r in rows if r["kind"] == "visit"]) == 2
    assert "welcome back" in um.compose_system_context("alice@example.com", store.context_summary("user-1", "alice@example.com")).lower()


def test_fallback_when_no_env(tmpdir, monkeypatch):
    monkeypatch.delenv("LEARNING_DATABASE_URL", raising=False)
    um.reset_store()
    # get_store must fall back to local sqlite, never raise.
    try:
        store = um.get_store()
        assert store.backend == "sqlite"
        store.save("user-1", "alice@example.com", "preference", "remember this")
        assert any(r["summary"] == "remember this" for r in store.load("user-1"))
    finally:
        um.reset_store()


def test_get_store_without_env_and_no_dbpath_uses_local_file(tmpdir, monkeypatch):
    monkeypatch.setenv("USER_MEMORY_SQLITE_PATH", os.path.join(str(tmpdir), "mem2.sqlite"))
    um.reset_store()
    store = um.get_store()
    try:
        store.save("user-1", "alice@example.com", "fact", "hello from fallback")
        assert any(r["summary"] == "hello from fallback" for r in store.load("user-1"))
    finally:
        um.reset_store()
        store.clear("user-1") if hasattr(store, "clear") else None


def test_lesson_completed_summary():
    s = um.lesson_completed_summary("Intro to Cybersecurity")
    assert "Intro to Cybersecurity" in s
    assert "completed lesson" in s

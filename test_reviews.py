"""Tests for public site reviews (reviews.py + /api/reviews wiring).

Covers: submit + validation, pending-by-default, list/average, rate
limit, spam guards, sqlite fallback, and the Flask API endpoints.
Run: python3 -m pytest test_reviews.py -q   (or python3 test_reviews.py)
"""
import os
import sys

# Never touch a real database during tests: force the sqlite fallback.
os.environ.pop("LEARNING_DATABASE_URL", None)
os.environ["REVIEWS_SQLITE_PATH"] = os.path.abspath("test_reviews.db")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reviews as reviews_mod  # noqa: E402
from reviews import ReviewStore, validate_review  # noqa: E402

failures = []


def check(name, cond, extra=""):
    status = "pass" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" ({extra})" if extra else ""))
    if not cond:
        failures.append(name)


def _fresh(tmpdir=None):
    path = os.path.join(str(tmpdir), "reviews.sqlite") if tmpdir else os.path.abspath("test_reviews_fresh.db")
    if os.path.exists(path):
        os.remove(path)
    return ReviewStore(sqlite_path=path), path


def main():
    # -- validation (pure functions) --
    check("valid review passes", validate_review("ada", 5, "great site")[0])
    check("empty name defaults ok", validate_review("", 5, "great site")[0])
    check("rating 0 rejected", not validate_review("ada", 0, "great site")[0])
    check("rating 6 rejected", not validate_review("ada", 6, "great site")[0])
    check("rating text rejected", not validate_review("ada", "x", "great site")[0])
    check("rating bool rejected", not validate_review("ada", True, "great site")[0])
    check("rating 2.5 rejected", not validate_review("ada", 2.5, "great site")[0])
    check("empty text rejected", not validate_review("ada", 5, "")[0])
    check("too-long text rejected", not validate_review("ada", 5, "x" * 501)[0])
    check("500-char text ok", validate_review("ada", 5, "word " * 100)[0])
    check("profanity blocked", not validate_review("ada", 5, "this is shit")[0])
    check("link spam blocked", not validate_review("ada", 5, "visit https://spam.example.com now")[0])
    check("normal words pass (skills)", validate_review("ada", 4, "I learned real skills here")[0])

    # -- store: submit / pending / approve / list / average --
    store, path = _fresh()
    ok, err, row = store.submit("ada", 5, "great site")
    check("submit ok", ok and row["status"] == "pending", err)
    check("pending not public", store.public_summary()["review_count"] == 0)
    ok6, err6, _ = store.submit("x", 6, "bad rating")
    check("rating 6 rejected", not ok6)
    store.submit("bob", 4, "very good tools")
    check("approve 1", store.set_status(1, "approved"))
    summ = store.public_summary()
    check("one approved, avg 5.0", summ["review_count"] == 1 and summ["average_rating"] == 5.0)
    store.set_status(2, "approved")
    summ = store.public_summary()
    check("two approved, avg 4.5", summ["review_count"] == 2 and summ["average_rating"] == 4.5)
    check("latest first", summ["reviews"][0]["name"] == "bob")
    check("pending list empty after approvals", store.list_by_status("pending") == [])
    check("reject keeps out of public", store.set_status(2, "rejected") and store.public_summary()["review_count"] == 1)

    # -- sqlite fallback path (no LEARNING_DATABASE_URL) --
    check("sqlite backend chosen", store.backend == "sqlite")
    os.remove(path)

    # -- Flask API wiring (rate limit, validation, list) --
    os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath("test_reviews_app.db")
    for f in ("test_reviews_app.db", "test_reviews.db"):
        if os.path.exists(f):
            os.remove(f)
    reviews_mod.reset_store()
    import importlib
    import app as appmod  # noqa: E402
    importlib.reload(appmod)
    appmod.reviews_get_store = None
    # Point the app at a fresh store file.
    os.environ["REVIEWS_SQLITE_PATH"] = os.path.abspath("test_reviews_api.db")
    if os.path.exists("test_reviews_api.db"):
        os.remove("test_reviews_api.db")
    reviews_mod.reset_store()

    c = appmod.app.test_client()

    r = c.get("/api/reviews")
    check("GET /api/reviews 200 empty", r.status_code == 200 and r.json["review_count"] == 0)

    r = c.post("/api/reviews", json={"name": "ada", "rating": 6, "text": "bad"})
    check("POST rating 6 -> 400", r.status_code == 400, str(r.status_code))

    r = c.post("/api/reviews", json={"name": "ada", "rating": 5, "text": "great site, very helpful tools"})
    check("POST valid -> 201 pending", r.status_code == 201 and r.json.get("status") == "pending", str(r.status_code))

    # Pending must not show publicly.
    r = c.get("/api/reviews")
    check("pending review hidden", r.json["review_count"] == 0)

    # Approve directly in the store, then it must show with average.
    rid = r.json.get("id")
    # (id from the 201; re-fetch via store for safety)
    st = reviews_mod.get_store()
    all_pending = st.list_by_status("pending")
    check("one pending stored", len(all_pending) == 1)
    st.set_status(all_pending[0]["id"], "approved")
    r = c.get("/api/reviews")
    check("approved review public, avg 5.0", r.json["review_count"] == 1 and r.json["average_rating"] == 5.0)

    # Rate limit: default 5 per hour per IP. Earlier posts in this run
    # already used 2 slots, so the last posts must hit the limit.
    codes = []
    for i in range(5):
        rr = c.post("/api/reviews", json={"name": f"r{i}", "rating": 4, "text": f"another review {i}"})
        codes.append(rr.status_code)
    check("rate limit kicks in", 429 in codes and codes.count(201) == 3, str(codes))
    r = c.post("/api/reviews", json={"name": "last", "rating": 4, "text": "one too many"})
    check("over-limit post returns 429", r.status_code == 429, str(r.status_code))

    # Homepage renders with the reviews section.
    r = c.get("/")
    check("homepage 200 with reviews section", r.status_code == 200 and b"Leave a review" in r.data)

    print()
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

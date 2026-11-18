"""Tests for Squad payment gateway integration (flag-gated).
Run: python3 test_squad_payments.py
Exits non-zero on the first failure.
Network calls to Squad are mocked; no real keys or network needed.
"""
import os, sys, tempfile, json, hmac, hashlib
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.gettempdir(), "squad_test.db"))
os.environ.setdefault("SQUAD_ENABLED", "true")
os.environ.setdefault("SQUAD_SECRET_KEY", "test-secret-key")
os.environ.setdefault("SQUAD_ENV", "sandbox")

def check(name, cond, extra=""):
    if cond:
        print("PASS", name)
    else:
        print("FAIL", name, extra)
        sys.exit(1)

import app as m

with m.app.app_context():
    m.db.drop_all(); m.db.create_all()

    # feature flag / config
    check("squad enabled when flag+key set", m.squad_enabled() is True)
    check("squad base url sandbox", m.squad_base_url() == "https://sandbox-api-d.squadco.com")
    old_env = os.environ.get("SQUAD_ENV")
    os.environ["SQUAD_ENV"] = "live"
    check("squad base url live", m.squad_base_url() == "https://api-d.squadco.com")
    os.environ["SQUAD_ENV"] = old_env or "sandbox"
    check("squad amount kobo pro", m._squad_amount_kobo("pro") == 630000)
    check("squad amount kobo pro_plus", m._squad_amount_kobo("pro_plus") == 1260000)
    check("squad amount kobo tutor_pro", m._squad_amount_kobo("tutor_pro") == 630000)

    # webhook signature
    secret = "test-secret-key"
    body = json.dumps({"data": {"transaction_ref": "CLD-SQD-1-x", "status": "success"}}).encode()
    good = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest().upper()
    check("webhook signature valid", m.squad_webhook_signature_valid(secret, body, good) is True)
    check("webhook signature lowercase accepted", m.squad_webhook_signature_valid(secret, body, good.lower()) is True)
    check("webhook signature tampered rejected", m.squad_webhook_signature_valid(secret, body, "00" * 32) is False)
    check("webhook signature wrong secret rejected", m.squad_webhook_signature_valid("other", body, good) is False)
    check("webhook signature empty rejected", m.squad_webhook_signature_valid("", body, good) is False)

    # test user + payment
    user = m.User(email="squad@t.t", password_hash="x", plan="free")
    m.db.session.add(user); m.db.session.commit()
    pay = m.Payment(user_id=user.id, plan="pro", amount=m._squad_amount_kobo("pro"),
                    reference="CLD-SQD-TEST-1", status="pending", currency="NGN", network="squad")
    m.db.session.add(pay); m.db.session.commit()

    # settle: success path
    verified = {"amount": pay.amount, "currency": "NGN", "status": "success"}
    check("settle success activates", m._settle_squad_payment(pay, verified) is True)
    check("settle sets status success", pay.status == "success")
    check("settle sets user plan", user.plan == "pro")
    check("settle idempotent - second call no-op", m._settle_squad_payment(pay, verified) is False)

    # settle: wrong amount rejected
    pay2 = m.Payment(user_id=user.id, plan="pro_plus", amount=m._squad_amount_kobo("pro_plus"),
                     reference="CLD-SQD-TEST-2", status="pending", currency="NGN", network="squad")
    m.db.session.add(pay2); m.db.session.commit()
    check("settle wrong amount rejected",
          m._settle_squad_payment(pay2, {"amount": 1, "currency": "NGN"}) is False)
    check("wrong amount stays pending", pay2.status == "pending")

    # settle: non-squad payment rejected
    pay3 = m.Payment(user_id=user.id, plan="pro", amount=pay.amount,
                     reference="BANK-xyz", status="pending", currency="NGN", network="opay")
    m.db.session.add(pay3); m.db.session.commit()
    check("settle non-squad rejected", m._settle_squad_payment(pay3, verified) is False)

    # webhook route: bad signature
    with m.app.test_client() as c:
        r = c.post("/payment/squad/webhook", data=body, headers={"x-squad-encrypted-body": "bad"})
        check("webhook bad signature 401", r.status_code == 401, str(r.status_code))

    # webhook route: good signature but squad verify mocked to return verified data
    orig_verify = m.squad_verify_transaction
    m.squad_verify_transaction = lambda ref: {"amount": m._squad_amount_kobo("pro_plus"), "currency": "NGN", "status": "success"}
    try:
        payload = json.dumps({"data": {"transaction_ref": "CLD-SQD-TEST-2", "status": "success"}}).encode()
        sig = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest().upper()
        with m.app.test_client() as c:
            r = c.post("/payment/squad/webhook", data=payload,
                       headers={"x-squad-encrypted-body": sig, "Content-Type": "application/json"})
            check("webhook valid signature 200", r.status_code == 200, str(r.status_code))
    finally:
        m.squad_verify_transaction = orig_verify
    check("webhook activates subscription", pay2.status == "success")

    # flag off: webhook 404 and initiate blocked
    os.environ["SQUAD_ENABLED"] = "false"
    check("flag off disables squad", m.squad_enabled() is False)
    with m.app.test_client() as c:
        r = c.post("/payment/squad/webhook", data=b"{}")
        check("flag off webhook 404", r.status_code == 404, str(r.status_code))
    os.environ["SQUAD_ENABLED"] = "true"

    # legacy code untouched: usdt/bank/paystack routes still present
    rules = {r.endpoint for r in m.app.url_map.iter_rules()}
    check("legacy usdt route present", "payment_usdt_submit" in rules)
    check("legacy bank route present", "payment_bank_submit" in rules)
    check("legacy paystack routes present", "payment_initialize" in rules and "payment_webhook" in rules)
    check("squad routes present",
          {"payment_squad_initiate", "payment_squad_callback", "payment_squad_webhook"} <= rules)

    print("ALL SQUAD TESTS PASSED")

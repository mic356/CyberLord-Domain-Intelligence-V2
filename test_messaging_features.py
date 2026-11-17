#!/usr/bin/env python3
"""Regression tests for linked messaging tutor and bank receipt uploads.
Run with: python test_messaging_features.py (after installing requirements.txt).
"""
import os
from pathlib import Path
from io import BytesIO

DB_PATH = Path(__file__).with_name("test_messaging_features.db")
os.environ["DATABASE_URL"] = "sqlite:///" + str(DB_PATH)
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
if DB_PATH.exists():
    DB_PATH.unlink()

import app as m  # noqa: E402


def run():
    with m.app.app_context():
        user = m.User(email="messaging-test@example.invalid")
        user.set_password("MessagingTestPassword123")
        m.db.session.add(user)
        m.db.session.commit()
        user_id = user.id

        # One-time linking code binds by channel identifier, not username/email.
        code = "81726354"
        token = m.MessagingLinkCode(
            user_id=user_id,
            code_hash=m.hashlib.sha256(code.encode()).hexdigest(),
            expires_at=m.datetime.utcnow() + m.timedelta(minutes=10),
        )
        m.db.session.add(token)
        m.db.session.commit()
        ok, message = m._consume_messaging_link_code("telegram", "telegram-chat-991", code)
        assert ok and "linked" in message.lower()
        assert m.MessagingAccount.query.filter_by(channel="telegram", external_id="telegram-chat-991", user_id=user_id).first()
        ok_again, _ = m._consume_messaging_link_code("telegram", "another-chat", code)
        assert not ok_again, "link code must be single use"

        # All common image-generation command forms are normalized for every messaging adapter.
        assert m._image_generation_prompt("/image a blue cyber shield") == "a blue cyber shield"
        assert m._image_generation_prompt("generate an image of a laptop") == "a laptop"
        assert m._image_generation_prompt("create a logo for CyberLord") == "CyberLord"
        assert m._image_generation_prompt("draw an illustration of a secure network") == "a secure network"
        assert m._image_generation_prompt("edit this image to use a dark background") == "use a dark background"

        # Persona, history and duplicate delivery records persist in SQL.
        state, history = m._messaging_state("telegram", "telegram-chat-991")
        state.persona = "tutor"
        state.history_json = '[{"role":"user","content":"hello"}]'
        m.db.session.commit()
        assert m._messaging_state("telegram", "telegram-chat-991")[0].persona == "tutor"
        assert m._messaging_is_duplicate("telegram", "chat-991:message-1") is False
        assert m._messaging_is_duplicate("telegram", "chat-991:message-1") is True

        # The free tutor allowance is the existing 10-per-UTC-day website quota.
        for _ in range(m.TUTOR_FREE_DAILY_LIMIT):
            m.db.session.add(m.TutorUsage(user_id=user_id, day=m.datetime.utcnow().strftime("%Y-%m-%d")))
        m.db.session.commit()
        assert m.tutor_remaining(user) == 0
        user.tutor_pro_expires_at = m.datetime.utcnow() + m.timedelta(days=20)
        m.db.session.commit()
        assert m.tutor_pro_active(user) is True
        assert m.tutor_remaining(user) is None
        user.tutor_pro_expires_at = None
        m.db.session.commit()

    # Bank receipt upload is persisted but never auto-activates the plan.
    client = m.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    response = client.post("/payment/bank/submit", data={
        "plan": "tutor_pro", "payment_method": "opay", "bank_reference": "TEST-RECEIPT-001",
        "receipt": (BytesIO(b"%PDF-1.4 sample receipt"), "receipt.pdf", "application/pdf"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    with m.app.app_context():
        payment = m.Payment.query.filter_by(reference="BANK-TEST-RECEIPT-001").first()
        assert payment and payment.status == "pending"
        receipt = m.BankReceipt.query.filter_by(payment_id=payment.id).first()
        assert receipt and receipt.data.startswith(b"%PDF")
        assert m.db.session.get(m.User, user_id).tutor_pro_expires_at is None, "bank receipt must not activate Tutor Pro"

    print("PASS: one-time linking, persistent state, deduplication, shared Tutor Pro quota and pending receipt upload")


if __name__ == "__main__":
    run()

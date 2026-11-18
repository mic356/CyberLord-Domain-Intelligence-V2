SQUAD GATEWAY IMPLEMENTATION
=============================

Customer checkout now uses Squad only. Existing subscription prices are unchanged:
- FREE: NGN 0
- PRO: NGN 6,300 / 30 days
- PRO PLUS: NGN 12,600 / 30 days
- TUTOR PRO: NGN 6,300 / 30 days

Required server environment:
- SQUAD_SECRET_KEY: secret key from the Squad merchant dashboard
- SQUAD_ENV: live (default) or sandbox

Configure the Squad dashboard:
- Redirect URL: https://YOUR-DOMAIN/payment/squad/callback
- Webhook URL: https://YOUR-DOMAIN/payment/squad/webhook

The app creates a unique reference for each checkout, sends the amount in kobo,
and associates the reference with the authenticated user and selected plan. The
callback and webhook both query Squad's verification endpoint. A plan is only
activated when the server confirms Success, NGN currency, and the exact expected
amount. The webhook itself is not trusted as proof of payment.

Before production:
1. Complete Squad merchant onboarding/KYC and obtain live API credentials.
2. Configure the environment variables and dashboard URLs above.
3. Test all checkout channels with sandbox credentials.
4. Switch SQUAD_ENV to live and set the live SQUAD_SECRET_KEY.
5. Make a low-value live transaction and confirm callback + webhook behaviour.

The old customer-facing bank-transfer and USDT flows, and the old Paystack flow,
have been removed. Historical payment rows remain in the database for audit/
compatibility; they are not offered in the customer checkout. Back up the
production database before deploying.

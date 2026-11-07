# CyberLord Domain Intelligence — Advanced Starter

A fresh Flask application with account registration/login, password reset, scan history, tier-based tool access, Paystack checkout and server-side payment verification.

## Plans
- FREE: domain scan, subdomain intelligence, email DNS, DNS intelligence, technology fingerprint and IP intelligence.
- PRO — ₦5,000: adds Phone Intelligence, Individual Email Review and Breach Exposure.
- PRO PLUS — ₦10,000: adds Attack Surface Map, CVE Intelligence, Compare Domains and Limited Port Scanner.

## Local setup
1. Install Python 3.11+.
2. `python -m venv .venv`
3. Activate the environment.
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and set a long random `SECRET_KEY`.
6. `python app.py`

## Render deployment
Use the included `render.yaml`, or set:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Environment: `SECRET_KEY`, `DATABASE_URL`, `PAYSTACK_SECRET_KEY`, `RESEND_API_KEY`, `RESEND_FROM`

Set `DATABASE_URL` to your Neon PostgreSQL connection string. Never commit secrets or `.env`.

## Paystack
Use a Paystack **test secret key** first. Configure the webhook URL as:
`https://YOUR-SERVICE.onrender.com/payment/webhook`
The callback is `/payment/callback`. Payment access is granted only after server-side verification of successful status, amount and currency. Switch to a live secret only after testing and completing Paystack business verification.

## Password reset email
Set `RESEND_API_KEY` and `RESEND_FROM` to a verified sender/domain in Resend. A Render `onrender.com` address is not a domain you own and cannot be used as a verified sender domain. Reset tokens expire after 30 minutes. Responses do not reveal whether an email address is registered.

## Bybit
The Bybit payment option is displayed in the dashboard as pending merchant integration. Do not collect payments through a personal Bybit transfer or unlock plans based on screenshots/manual claims. Implement merchant checkout only after obtaining approved merchant/API access and a verified callback flow.

## Important limitations
This is a defensive starter, not a complete commercial scanner. DNS, TLS, HTTP headers, limited common subdomain lookup, phone-number format metadata and basic IP metadata are implemented. Breach database lookup requires a licensed provider; CVE matching needs verified product/version data; broad port scanning is disabled by design; domain comparison is not yet implemented. These modules explicitly avoid inventing results. Use only on domains and systems you own or are authorized to assess.

Before public launch: add CSRF protection, email verification, rate limiting, audit logging, backup/restore, privacy/terms pages, stricter SSRF protections, background jobs, robust error monitoring and security review. Set a strong secret and use HTTPS.

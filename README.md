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
- Environment: `SECRET_KEY`, `DATABASE_URL`, `PAYSTACK_SECRET_KEY`, `RESEND_API_KEY`, `RESEND_FROM`; optional `KALI_WORKER_URL` and `KALI_WORKER_TOKEN`

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
## Expanded defensive scanning

The existing tools have been expanded without adding new dashboard tools:
- Domain/DNS: A, AAAA, MX, NS, TXT, CAA and SOA evidence, TLS protocol/certificate issuer/expiry/SAN details, HTTP security headers and cookie attribute review.
- Subdomains: curated common-name DNS discovery with A/AAAA/CNAME evidence (not exhaustive).
- Email security and Individual Email Review: MX, SPF, DMARC policy, common DKIM selector checks and explicit limitations around mailbox verification.
- Technology Fingerprint: response headers, HTML technology hints, generator metadata and script/stylesheet paths. Hints can be spoofed and do not prove exact versions.
- IP Intelligence: public-IP validation, reverse DNS and an RDAP lookup reference.
- Phone Intelligence: numbering validity, region, carrier and timezone hints; no identity or live-location lookup.
- Compare Domains: side-by-side DNS, TLS, HTTP and findings comparison for two domains.
- Attack Surface Map: combined domain, subdomain and technology inventory, with optional Kali worker checks.
- Limited Port Scanner: optional low-intensity TCP top-100 service identification through the isolated Kali worker.

## Optional Kali Linux integration

Render does not contain Kali Linux. The `kali-worker/` folder provides a separate, restricted worker to run on a dedicated Kali VM/VPS. It supports only low-intensity Nmap TCP service identification, basic WhatWeb fingerprinting and fast testssl checks. It requires an explicit authorization confirmation and a domain allowlist (`KALI_ALLOWED_DOMAINS`), rejects private/non-public IP resolution, and does not run exploit scripts, brute force, credential attacks or unrestricted scans. Keep it behind a private VPN or strict HTTPS/firewall controls; never expose its port directly to the public internet. Configure `KALI_WORKER_URL` and `KALI_WORKER_TOKEN` in Render only after securely hosting it. See `kali-worker/README.md`.

Breach database lookup still requires a licensed provider; CVE matches are intentionally withheld unless exact product/version evidence is verified. The app reports these limitations rather than inventing breach or vulnerability findings. Use only on domains and systems you own or are explicitly authorized to assess.

Before public launch: add CSRF protection, email verification, rate limiting, audit logging, backup/restore, privacy/terms pages, stricter SSRF protections, background jobs, robust error monitoring and security review. Set a strong secret and use HTTPS.


## Phone Intelligence deep enrichment and downloadable scan history

The Phone Intelligence tool now requests an additional passive metadata enrichment from the optional Kali worker at `/phone-intel` when `KALI_WORKER_URL` and `KALI_WORKER_TOKEN` are configured. The worker requires `phonenumbers` (included in `kali-worker/requirements.txt`). This is numbering-plan metadata only; it does not identify subscribers, verify ownership, locate phones, or access calls, SMS or messaging accounts.

Users can download each of their own saved scan records from the dashboard as JSON or readable TXT. The download route checks the authenticated user's ownership of the scan record.

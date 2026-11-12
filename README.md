# CyberLord Domain Intelligence — Advanced Starter

A Flask application with account registration/login, password reset, scan history, tier-based tool access, blockchain payment verification and 30-day subscriptions.

## Customer care
For account, subscription or payment assistance, contact [CyberLord Customer Care](mailto:michaelelvistito@gmail.com). Include your registered account email and payment reference; never send passwords, private keys or wallet recovery phrases.

## Plans
- FREE: domain scan, subdomain intelligence, email DNS, DNS intelligence, technology fingerprint and IP intelligence.
- PRO — ₦6,300 or 4.50 USDT: adds Phone Intelligence, Individual Email Review and Breach Exposure; 30 days.
- PRO PLUS — ₦12,600 or 9.00 USDT: adds Attack Surface Map, CVE Intelligence, Compare Domains and Limited Port Scanner; 30 days.

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
- Environment: `SECRET_KEY`, `DATABASE_URL`, `PAYMENT_ADMIN_TOKEN`, `PAYSTACK_ENABLED=false`; optional `TRONGRID_API_KEY`, `BSC_RPC_URL`, `RESEND_API_KEY`, `RESEND_FROM`, `KALI_WORKER_URL` and `KALI_WORKER_TOKEN`

Set `DATABASE_URL` to your Neon PostgreSQL connection string. Never commit secrets or `.env`.

## Paystack (temporarily disabled)
Paystack code is retained but both initialization and webhook processing are disabled unless `PAYSTACK_ENABLED=true`. Keep it false until the merchant account is approved and live credentials have been configured. When re-enabled, configure the webhook URL as `https://YOUR-SERVICE.onrender.com/payment/webhook`.

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


## Subscription payments (current configuration)

- PRO: NGN 6,300 or 4.50 USDT; 30 days after verified payment.
- PRO PLUS: NGN 12,600 or 9.00 USDT; 30 days after verified payment.
- USDT networks: TRC20 and BEP20 only. The app checks the incoming transfer, destination wallet, supported USDT token contract, exact amount, and confirmation state before activation. A transaction hash can only be used once. A screenshot is never accepted as proof of a blockchain payment.
- Bank transfer references are recorded as pending. An administrator must independently confirm receipt and approve using the protected `/admin/payments/<payment_id>/approve` endpoint. Set a strong `PAYMENT_ADMIN_TOKEN` environment variable; send it only in the Authorization Bearer header. Do not approve based on a receipt image alone. Bank account details are not configured in this package yet.
- Paystack code is retained but disabled by default. Set `PAYSTACK_ENABLED=true` only after the merchant account is approved and live credentials are configured.

### Payment-related Render environment variables

- `PAYSTACK_ENABLED=false` (leave false until approved)
- `PAYMENT_ADMIN_TOKEN` (long random secret, required for manual bank approvals)
- `TRONGRID_API_KEY` (optional, recommended for TRON API reliability)
- `BSC_RPC_URL` (optional; defaults to a public BNB Smart Chain mainnet RPC)

The app includes an additive startup database migration for the new subscription-expiry and payment-verification fields. Always back up the production database before deploying schema changes. Test a small payment first on the intended mainnet network; do not use testnet transfers for production activation.

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

## Cyber Academy exercises: how to add questions

Lesson content and exercise questions live in `academy_questions.py` (imported by `app.py`). Each lesson has a `questions` list. To add a question, copy one question block in that lesson and change `question`, `choices`, `answer` (index of the correct option, starting at 0) and `explain`. Scenario, log-snippet and config-review questions are supported: put the scenario in the `question` string using line breaks. Save and restart the app (or redeploy). No database migration is needed. To add a whole lesson, copy one lesson block with a unique `slug`. See the header comment at the top of `academy_questions.py` for the full how-to.

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


## CyberLord Intelligence Assistant

CyberLord AI calls Google's Gemini API from the Flask backend when `GEMINI_API_KEY` is configured. It uses the `gemini-3.8-flash` model by default and can be changed with `GEMINI_MODEL`. The API key stays on the server and is never sent to browser JavaScript. If the key is absent or Gemini is temporarily unavailable, the app uses the built-in cybersecurity knowledge assistant as a fallback. The built-in module can also retrieve public CVE and CISA KEV information when outbound network access is available.


## New workspace experience

- The public landing page now uses a bright, responsive violet/aqua/mint design with custom inline security illustrations, product explanations, onboarding workflow and clear account-creation calls to action.
- Signed-in users can open **CyberLord Academy** at `/academy` for structured lessons, knowledge checks and saved completion progress. Academy content is separate from the AI assistant.
- Signed-in users can open the **Interaction Board** at `/interaction-board` to publish discussions and reply to other members. Posts and replies are stored in the application database and are written by members, not generated as fake AI activity.
- Signed-in users can open **Security Centre** at `/security-centre` to review recent saved scan activity and export reports.
- The dashboard includes direct CyberLord AI guide prompts for domain scans, Nmap, scan interpretation, subscriptions and learning roadmaps.
- Gemini API usage is subject to the quota and billing limits of the Google AI Studio project. Do not assume unlimited free requests.

**Important capability note:** Security Centre currently summarises saved scan history. It does not run background monitoring or scheduled scans. Do not advertise automatic 24/7 monitoring until a separately deployed scheduler/worker has been implemented and verified.


## Clear monetization and monitoring status

- FREE is the entry plan: core domain/DNS intelligence, Cyber Academy learning guides and the built-in CyberLord knowledge assistant.
- PRO is NGN 6,300 or 4.50 USDT for 30 days after independently verified payment.
- PRO PLUS is NGN 12,600 or 9.00 USDT for 30 days after independently verified payment.
- Public pricing information explains that paid plans unlock additional tools; server-side tool access remains governed by the existing plan checks.
- Individual/manual checks are available according to the user's plan. Continuous background monitoring with scheduled rechecks and notifications is a planned paid add-on, not an active feature in this release. Do not advertise it as currently available until a scheduler, persistent monitoring configuration, safe scan queue, and notification delivery have been implemented and tested.


## Automated domain monitoring

- Domain ownership is verified by a unique DNS TXT record at `_cyberlord-verification.<domain>`.
- PRO: one verified domain, checks every 24 hours.
- PRO PLUS: up to five verified domains, checks every 6 hours.
- Scheduled checks use public DNS and TLS certificate observations only; no exploit attempts, brute force or port scans are part of monitoring.
- The first successful check establishes a baseline. Later changes to observed DNS/TLS/HTTP data create in-app alerts. Email alerts are attempted when `RESEND_API_KEY` and `RESEND_FROM` are configured.
- Expired subscriptions stop monitoring when the worker processes the account again.
- Deploy `cyberlord-monitoring-worker` as a persistent Render worker. Set its `DATABASE_URL` to the exact same persistent PostgreSQL connection string as the web service, and set the same `SECRET_KEY` on both. Configure Resend variables for email delivery.
- Back up the persistent database. The worker must remain running; the web `/health` route does not confirm worker status.
- Only register domains you own or are authorized to monitor.


## Advanced Intelligence Lab (new)
The dashboard now links to three PRO PLUS passive investigation modules: Digital Footprint Investigator, Shadow API Hunter, and Website Impersonation Detector. They run inside the existing Flask service; no separate worker or hosting service is required for these passive checks. The modules use public DNS, certificate-transparency data, and limited same-origin public HTTP requests. They do not perform exploitation, authentication bypass, intrusive port scans, or access private data. Findings are indicators and require human validation.


## Private administrator payment dashboard
The admin area is served by this same Flask application at `/admin`. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the existing Render service environment. The admin login is separate from customer authentication. Confirm bank/OPay funds independently before approving a pending request; approval activates the customer's 30-day plan. Customer payment forms show a successful submission notice without falsely claiming that funds have been received.

### CyberLord AI, Academy and Interaction Board

- **CyberLord AI** uses the Google Gemini API from the Flask server when `GEMINI_API_KEY` is configured in Render. The key is never sent to the browser. `GEMINI_MODEL` defaults to `gemini-3.8-flash`; if Gemini is temporarily unavailable, the app falls back to the built-in cybersecurity knowledge assistant. Gemini API quotas and pricing are controlled by the Google AI Studio project.
- **CyberLord Academy** is a structured lesson-and-quiz area. Members read the lesson notes, answer knowledge checks and retain their completion status and best score. It is not an AI chat.
- **Interaction Board** is a member discussion forum. Signed-in members create posts and reply to other members. Posts are stored in the application database and are not AI-generated sample conversations.

Set `GEMINI_API_KEY` under the Render service's Environment settings. Do not place the key in `static/`, HTML templates, JavaScript, GitHub files or public messages.

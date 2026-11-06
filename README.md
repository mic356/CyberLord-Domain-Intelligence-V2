# CyberLord Domain Intelligence

A fresh, login-first cybersecurity intelligence workspace built with Flask. This is a **new project**, separate from any older CyberLord repository or deployment.

## Included modules
- Domain security overview: DNS, HTTPS/TLS certificate check, response headers and configuration observations.
- Passive subdomain intelligence using Certificate Transparency data.
- DNS record intelligence (A, AAAA, MX, NS, TXT, CAA).
- Email-domain security: MX, SPF, DMARC and common DKIM selector checks.
- Individual email risk review: address format and domain mail posture; optional breach lookup when a Have I Been Pwned API key is configured.
- Phone intelligence: numbering-plan validation and public number metadata only. It does not track live location, identify private subscribers, or access call records.
- IP intelligence using public IP metadata; geolocation is approximate.
- Technology fingerprinting using public web response signals.
- CVE intelligence using the NIST NVD public API.
- Domain comparison.
- Premium attack-surface summary.
- Limited TCP port connectivity check with explicit authorization and a fixed port allowlist.
- Per-user scan history and downloadable JSON reports.

## Safety boundaries
Only assess domains and systems you own or have written permission to test. The domain overview and limited port check require an authorization confirmation. The port checker uses a fixed allowlist, short timeouts and a small number of ports. This is not an exploit framework.

Email checks do not log into mailboxes, test passwords, or enumerate private accounts. Phone intelligence does not perform live tracking or reveal private subscriber information. Breach lookup requires your own HIBP API key. No private data is sold or inferred.

## Run locally
1. Install Python 3.11+.
2. Create and activate a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and set a strong `SECRET_KEY`.
5. Start: `python app.py`
6. Open `http://127.0.0.1:5000`.

## Deploy to Render
1. Create a **new, separate GitHub repository** for this fresh project.
2. Upload the contents of this ZIP to the repository root (not the enclosing folder).
3. In Render, create a new Web Service from that new repository, or use the included Blueprint `render.yaml`.
4. Set `PAYSTACK_PUBLIC_KEY` and `PAYSTACK_SECRET_KEY` to your **live production keys** in Render Environment. Never put keys in GitHub or in browser JavaScript.
5. Configure a persistent disk mounted at `/var/data` (the included Render blueprint requests one). Keep `DATABASE_PATH=/var/data/cyberlord.db`.
6. Set the Paystack webhook URL to `https://YOUR-SITE/payment/webhook`.
7. Test with a small authorized domain first. Premium is activated only after the server verifies a successful ₦5,000 NGN transaction with Paystack. A browser redirect alone cannot unlock Premium.

## Payment notes
- Premium price is ₦5,000.
- The backend initializes and verifies Paystack transactions server-side and validates webhook signatures.
- If live keys are not configured, payment is unavailable and Premium remains locked.
- Do not paste API secrets, passwords, OTPs, or private keys into chat or commit them to GitHub.
- Bybit/USDT is not wired into this first clean build; do not treat a wallet transfer screenshot as verified payment. It should only be added with a server-verifiable payment flow.

## Environment variables
See `.env.example`. `HIBP_API_KEY` is optional. Without it, the breach exposure module explains that the provider is not configured.

## Important production checklist
- Set a unique, high-entropy `SECRET_KEY`.
- Use HTTPS and secure cookies.
- Configure the persistent disk before real user accounts are created.
- Add rate limiting, email verification, password reset, audit logging, and a privacy policy before opening registration publicly.
- Review third-party API terms, retention policies and applicable laws.


## Account retention and sign-in protection
- Account records are keyed by a normalized (lowercase) email address and are not deleted by logout or temporary sign-in lockout.
- After 10 failed sign-in attempts in a 15-minute window, that email's sign-in is paused for 15 minutes. A successful sign-in clears the failed-attempt counter.
- SQLite is configured to use `/var/data/cyberlord.db` on Render. The Render service must have the persistent disk mounted at `/var/data`; the included `render.yaml` declares a 1 GB disk. If deploying through a manually created Render service, attach a persistent disk at `/var/data` and set `DATABASE_PATH=/var/data/cyberlord.db` yourself. Without persistent storage, accounts and scan history can be lost when the service filesystem is replaced.
- Keep the Render `SECRET_KEY` stable between deploys. Do not regenerate it on every deployment, or existing browser sessions will be invalidated.

## Phone intelligence scope
Phone results include international/national/E.164 formats, country calling code, region metadata, number type, possible/valid numbering-plan checks, carrier label when available in numbering metadata, and associated time zones. These are not live subscriber or SIM records. Number portability can make carrier labels outdated. No live scam reputation source, subscriber identity, call records, or live location tracking is included.


## Premium payment section
The dashboard includes a dedicated Premium payment section. Paystack is the currently implemented checkout method: the server initializes the transaction, verifies the transaction amount and reference with Paystack, and only then activates Premium. Set `PAYSTACK_PUBLIC_KEY` and `PAYSTACK_SECRET_KEY` in the deployment environment. Never put secret keys in source code.

Bybit USDT is displayed as a disabled payment option until a Bybit merchant/payment API account and server-side verification flow are configured. Do not manually unlock Premium from a transfer screenshot or a client-side button. Premium must remain locked until a verified payment event is received by the server.


## Combined account, recovery and subscription features
- Registered accounts remain associated with their unique email; logout and temporary login lockout do not delete accounts or scan history. Ten consecutive failed attempts trigger a 15-minute lockout; a successful login or password reset clears the lockout counter.
- Forgot Password sends a one-time email link that expires after 30 minutes. Configure RESEND_API_KEY in Render for password-reset email delivery. RESEND_FROM_EMAIL defaults to onboarding@resend.dev for initial testing; Resend may restrict test-mode recipients to the email address associated with your Resend account. To send to other recipients, verify a domain in Resend and set RESEND_FROM_EMAIL to an address on that verified domain. Never commit API keys.
- PRO is ₦5,000 and includes phone intelligence, individual email review and breach exposure. PRO PLUS is ₦10,000 and includes PRO plus attack surface map, CVE intelligence, domain comparison and the limited port scanner. Server-side checks enforce the selected tier.
- Paystack initialization, callback verification and webhook processing check the exact stored plan amount before activating access. Bybit is shown as unavailable until a verified merchant/API integration is configured.
- For persistent production storage, configure Neon PostgreSQL and set `DATABASE_URL` in the Render service. When `DATABASE_URL` is set, the app uses Neon instead of the local SQLite file. Keep the connection URI private and never commit it to GitHub.
- This package does not run Kali Linux commands on Render. Existing scanners remain passive/limited and must only be used on systems the operator owns or is authorized to assess.


## Persistent PostgreSQL storage (Neon)

For Render, create a PostgreSQL project in Neon and add its pooled or direct PostgreSQL connection URI as the `DATABASE_URL` environment variable in the Render service. Keep the URI private and do not commit it to GitHub. The application uses PostgreSQL whenever `DATABASE_URL` is present; SQLite is retained only as a local-development fallback. The PostgreSQL connection enforces TLS (`sslmode=require`) when the URI does not already specify an SSL mode.

The first deployment creates the required tables and applies the existing `plan` column migrations. This change does not automatically copy any accounts that were previously stored in Render's temporary SQLite file. Users whose accounts disappeared will need to register again after PostgreSQL is connected.


## Password reset email via Resend
- Set `RESEND_API_KEY` in Render Environment.
- Optional: set `RESEND_FROM_EMAIL`. The default `onboarding@resend.dev` is suitable for limited testing; Resend test mode may only deliver to the account owner email.
- For delivery to other users, verify a domain in Resend, then set `RESEND_FROM_EMAIL` to an address on that domain.
- Email is sent through the Resend HTTPS API, not SMTP, so it avoids Render free-service SMTP port restrictions.

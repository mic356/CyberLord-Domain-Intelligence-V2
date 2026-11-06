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

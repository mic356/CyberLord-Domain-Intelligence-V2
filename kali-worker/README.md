# CyberLord restricted Kali worker

This is an optional, separately hosted worker. Render does not include Kali Linux, so the main website cannot execute Kali commands inside its own service. Host this worker on a dedicated Kali VM/VPS. Do not expose port 8787 directly to the public internet. Prefer a private VPN (for example, a site-to-site VPN) or HTTPS reverse proxy with firewall restrictions, in addition to the bearer token.

## Install on an authorized Kali VM

```bash
sudo apt update
sudo apt install -y nmap whatweb testssl.sh python3-venv
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export KALI_WORKER_TOKEN='use-a-long-random-secret'
export KALI_ALLOWED_DOMAINS='yourdomain.com,anotherdomain.com'
gunicorn --bind 127.0.0.1:8787 worker:app
```

Configure `KALI_WORKER_URL` and the same `KALI_WORKER_TOKEN` in the main Render service. `KALI_ALLOWED_DOMAINS` is a comma-separated list of domains you own or have written permission to test. The worker refuses targets outside this list and refuses non-public IP resolution. Phone Intelligence is a separate passive metadata endpoint (`POST /phone-intel`) protected by the same bearer token; it enriches numbering-plan information using libphonenumber and does not contact telecom networks or locate/identify subscribers. It runs only a low-intensity TCP top-100 service/version scan, basic WhatWeb fingerprinting and fast TLS checks. It does not run exploit scripts, brute force, credential attacks, stealth/evasion, or unrestricted port scans. Phone enrichment reports possible/valid format, region, number type, carrier hint and timezone hints only; carrier data may be stale and it cannot verify number ownership or provide live location.

The worker is not a replacement for a professional penetration test. Use it only within written scope and rate limits. Review local Kali package availability; package names can differ by Kali release.

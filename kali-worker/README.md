# CyberLord Kali Worker

This is the complete, separately hosted worker used by the CyberLord website.
It preserves the API paths and JSON fields used by the website:

- `GET /health`
- `POST /scan`
- `POST /phone-intel`

## Render service setup

Deploy this folder as a separate **Web Service** using the included Dockerfile.
If Render asks for a Root Directory, set it to `kali-worker` when deploying from
the main repository. If you upload this folder as a standalone repository,
leave Root Directory blank.

Do not configure the main website's Render service to run this worker.

Set these environment variables on the **CyberLord Kali Worker** Render service:

| Key | Value |
|---|---|
| `KALI_WORKER_TOKEN` | A long random secret. Use the same value as the main website service. |
| `KALI_ALLOWED_DOMAINS` | `cyberlord.name.ng` |

`KALI_ALLOWED_DOMAINS` accepts comma-, semicolon-, or newline-separated domains.
The worker reads this variable when the process starts, so save changes and
redeploy/restart the worker after editing it.

On the **main CyberLord website** Render service, set:

| Key | Value |
|---|---|
| `KALI_WORKER_URL` | The worker's Render URL, e.g. `https://your-worker-name.onrender.com` |
| `KALI_WORKER_TOKEN` | The exact same secret used by the worker |

Never paste the token into GitHub, chat, or source files.

## GitHub folder replacement

The archive contains one top-level directory named `kali-worker`.
Use it to replace the repository's existing `kali-worker` directory. Keep the
rest of the repository unchanged. GitHub's web interface may require deleting
the old directory's tracked files and then uploading the new folder contents;
Git does not track empty directories.

## Safety

The scan endpoint requires bearer-token authentication, an explicit
authorization confirmation, a matching allowlisted domain, and public IP
resolution. The Nmap profile is a low-intensity TCP top-100 service/version
check. No exploit scripts, brute force, credential attacks, stealth/evasion,
or UDP scans are run. Only test domains you own or have written permission to
assess.

Phone intelligence uses offline libphonenumber metadata. It does not query
telecom networks, identify subscribers, verify ownership, or locate phones.

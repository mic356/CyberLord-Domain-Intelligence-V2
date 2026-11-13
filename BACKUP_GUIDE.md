# CyberLord backup guide

Owner copy. Your data lives in a database. Where the backup must land, and how
to take it. Nothing here connects CyberLord to an outside backup service.

## Where the live data goes

1. **PostgreSQL (live)**: `DATABASE_URL` points at Render Postgres. The free
   plan keeps only one point-in-time snapshot on Render.
2. **Local fallback (already in the repo layout)**: when `DATABASE_URL` is
   unset the app falls back to `sqlite:///cyberlord.db` inside `instance/`.
   That file is ephemeral on Render, so it must be copied out regularly.

## Weekly backup (do this every week, it is five minutes)

### A. Postgres dump (Render free tier)

1. Open your team at `https://dashboard.render.com`
2. Go to the Postgres database service for `cyberlord-domain-intelligence`.
3. Click the database. Use the **Connect** panel. Your `DATABASE_URL` is shown.
4. On your own computer, install the Postgres client tools (Postgres.app,
   Homebrew `postgresql`, or your distro package). Then run:

   pg_dump "$DATABASE_URL" -Fc -f cyberlord-$(date +%F).dump

5. Move the file somewhere only you control:
   - your own computer, **and**
   - a private GitHub repo (e.g. `mic356/cyberlord-backups`) with **never**
     public, nothing else inside it. Push with `git add` only that file, or
     upload through the web UI.
6. Delete dumps older than 90 days after the file is verified readable.

### B. If a local SQLite file appears under `instance/`

1. On Render, open your web service, click **Shell** (temporary, idle-out in
   a few minutes).
2. Copy the database file out:

   cp instance/cyberlord.db /tmp/cyberlord-copy.db && ls -la /tmp/cyberlord-copy.db

3. Open `https://dashboard.render.com` > your service > **Logs** and chase
   this down if that fails; the Shell session is short-lived on free tier.
4. Instead of fighting the Shell, prefer the Postgres dump above. It is the
   canonical path for production.

## How to restore (when you need it)

1. Create a fresh Render Postgres database (free).
2. Copy the new database's `DATABASE_URL`.
3. Restore your latest dump:

   pg_restore -d "$NEW_DATABASE_URL" -c cyberlord-YYYY-MM-DD.dump

4. Point the CyberLord web service at the new `DATABASE_URL` in
   Environment, then **Manual Deploy > Redeploy last commit**.
5. Run the app once. It builds tables and applies the current schema on
   boot.

## Where backups must live, and what must never happen

- Keep dumps in **two private places**: your laptop **and** a private
  GitHub repo or an encrypted folder you control.
- Do not upload dumps to Google Drive, public repos, or a shared folder
  without strong access control. A dump has every user's email and password
  hash.
- Do not paste `DATABASE_URL`, `SECRET_KEY`, API keys, or wallet records
  into anything public. The repo `.gitignore` already excludes the SQLite
  file and any `cyberlord-*.dump` file.
- Test a restore at least twice a year. An untested backup is just a hope.

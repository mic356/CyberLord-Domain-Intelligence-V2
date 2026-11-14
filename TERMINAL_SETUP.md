# Terminal setup (ai-real-terminal)

## What replaced what
The old `/academy/terminal` page was a simulated whitelist terminal: the browser POSTed each command to
`POST /api/terminal/run` and the Flask server answered from a fixed in-memory model (`terminal_execute` in
`app.py`) that only understood a dozen commands against `lab.local`.

The new page is a **real in-browser terminal**. All command execution happens on the visitor's own device:

- **Shell UI:** xterm.js 5.5.0 + addon-fit (loaded from jsDelivr CDN, `cdn.jsdelivr.net`).
- **Python:** Pyodide 0.26.4 from `cdn.jsdelivr.net/pyodide/v0.26.4/full/`, so `python3` runs real Python
  code (REPL + `python3 -c "..."`).
- **Filesystem:** an in-browser virtual filesystem seeded with `readme` and `practice/scan-notes.txt`,
  `practice/dns-notes.txt`. `ls, cd, pwd, cat, echo, grep, mkdir, touch, rm, cp, mv, wc, head, tail, sort`
  are implemented against it in JavaScript and genuinely operate on it (mkdir/touch/rm persist across
  commands for the session; everything resets on refresh). Nothing touches disk.
- **AI assist panel:** POSTs to the existing `/api/ai-assistant` with `persona: "main"` (the main
  persona, not the tutor) plus `lesson_slug: ""`, attaching the last 10 terminal commands as context, and
  renders the reply in the side panel. Falls back gracefully when the assistant is unreachable; the
  terminal itself works fully offline of the server.

## Server-side cleanup
- `terminal_execute`, `_terminal_state`, `TERMINAL_ALLOWED`, the lab file maps, and the
  `POST /api/terminal/run` route are **deleted** from `app.py`. A grep for `terminal_execute`,
  `/api/terminal/run`, `TERMINAL_ALLOWED` across the repo returns nothing except an explanatory comment
  and this file.
- The only remaining `subprocess.run` in `app.py` is the unrelated Code Lab sandbox (Tutor Pro), which
  runs user **Python** snippets in a locked-down child process. The terminal page never POSTs to it; the
  browser-side terminal has no path to any server shell.
- Verified: no `os.system`, no `shell=True`, no user input reaching a server shell anywhere in `app.py`
  or `cyberlord_ai.py`.

## CSP change (no COEP/COOP needed)
The app's Content-Security-Policy was widened in `app.py`:

```
script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net;
connect-src 'self' https:;
```

`connect-src 'self' https:` was already open, so the jsDelivr fetches and the `/api/ai-assistant` call
work as-is. The xterm.css stylesheet needs the jsDelivr entry in `style-src`.

**No `Cross-Origin-Embedder-Policy` / `Cross-Origin-Opener-Policy` headers are needed.** Those headers
are only required for `@webcontainer/api` (StackBlitz's WebContainer), which needs
`COEP: require-corp` + `COOP: same-origin` to unlock `SharedArrayBuffer`, and Render's proxy makes that
unreliable. The shipped fallback is the recommended architecture here:

- Chosen: **xterm.js + Pyodide** (no special headers). Works on any static/iframe/embed setup, including
  Render.
- If a future version swaps in `@webcontainer/api`, it would require document-level
  `Cross-Origin-Embedder-Policy: require-corp` and `Cross-Origin-Opener-Policy: same-origin` on
  `cyberlord.name.ng`, served without interference by Render, and `crossOriginIsolated` true in the
  browser. On a free Render proxy that is fragile, so it was deliberately not chosen.

## Fallbacks
- Pyodide CDN unreachable: the shell still runs; `python3` reports it is still loading. No server
  round-trip is involved.
- jsDelivr unreachable for xterm.js: the page cannot render the terminal; everything else on the site is
  unaffected (CSP only widens, it does not break other pages).

## Tests
- `python -m py_compile app.py`
- `python test_academy.py` (academy surfaces)
- `python test_terminal_tutor.py` (updated: the old whitelist assertions now assert the endpoint is
  **gone** and the page loads the new client-side terminal)
- `python test_real_terminal.py` (new: asserts the template uses xterm.js + Pyodide, does not POST to
  `/api/terminal/run`, wires the AI panel to `/api/ai-assistant` with `persona:"main"`, and the server
  rejects POSTs to the removed endpoint)

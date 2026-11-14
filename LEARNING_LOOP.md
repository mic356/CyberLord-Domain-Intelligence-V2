# Oga self-learning loop

Oga (the main CyberLord AI) improves by remembering what it could not
answer, turning those gaps into learned knowledge, and shipping the new
knowledge through the normal branch-review flow. It never retrains a
neural model; it grows the curated built-in brain from real visitor
questions and real academy-terminal struggles.

## The three pieces

1. **Logging (`learning_log.py`)**
   - `ai_questions`: every `/api/ai-assistant` call records the persona
     (main/tutor), the user's question, which path answered it
     (gemini, groq, built-in-fallback, tutor-redirect, datetime-direct,
     images, weather/news-direct), whether it fell back to "I don't
     know", and a short snippet of the reply.
   - `terminal_events`: every command run in the academy real terminal
     (`/academy/terminal`, `templates/terminal.html`) is POSTed to the new
     `/api/terminal-log` endpoint as kind `command` or `error`, with the
     command and a short output snippet.
   - Storage is SQLite, capped at 10,000 rows per table with the oldest
     pruned. All input is sanitized: passwords, OTPs, API keys, Nigerian
     phone numbers, emails and long token-like blobs are replaced with
     `[REDACTED]` before storage, control characters are stripped, and
     every field is length-capped. Every write is best-effort; logging
     can never break chat or the terminal.
   - The db lives at `$LEARNING_LOG_PATH`, defaulting to
     `/tmp/cyberlord_learning.db` (see Render caveat below).

2. **Daily trainer (`train_daily.py`)**
   - Reads the logs, groups fallback (unanswered) questions by
     normalized text, and groups terminal errors by command root plus
     error essence.
   - With `GEMINI_API_KEY` set it asks Gemini for up to 5 short, stable
     knowledge entries and appends them to `learned_topics.py`, then runs
     the test batteries (`test_learning_loop.py`, `test_academy.py`,
     `test_brand_toyota.py`, `test_personas.py`) before committing to the
     `oga-learning` branch and pushing that branch only.
   - Without `GEMINI_API_KEY` it writes `LEARNING_TODO.md`, a plain
     grouped list of what to teach next. It never invents content.
   - Hard limits, enforced in code: refuses to run on `main`/`master`,
     never pushes to `main`, never merges. Learned topics are checked by
     `cyberlord_ai._general_lookup` only AFTER the built-in topics, so
     they fill gaps without overriding existing knowledge.
   - `python3 train_daily.py --dry-run` shows the groups without
     changing anything. `--fixture PATH` reads a JSON fixture instead of
     the real db (used by the tests).

3. **Learned topics (`learned_topics.py`)**
   - A plain list of (keyword phrase, answer body) pairs, merged into the
     built-in brain at import time in `cyberlord_ai.py`. Never store
     secrets, personal data, prices or news here; stable knowledge only.

## Daily cycle

1. Visitors ask Oga questions (Gemini/Groq/built-in chain) and practise in
   the academy terminal. Gaps and errors are logged.
2. Once a day the owner (or a scheduled job) runs `train_daily.py` on
   the `oga-learning` branch, e.g.
   `git checkout oga-learning && python3 train_daily.py`.
3. The trainer merges newly learned topics, runs the batteries, and
   pushes to `oga-learning`.
4. The owner reviews the diff on GitHub and merges `oga-learning` into
   `main` by hand. Render redeploys and the new topics are live.
5. Oga's "I don't know" rate falls over time as the gaps close.

## Render free-tier caveat

The Render free tier has **no persistent disk**. The learning database
lives in `/tmp` and is wiped on every deploy and every restart. That
means:
- after a restart the trainer sees an empty log (it reports "No
  unanswered questions... Nothing to do") and the day's learning
  evidence is gone; learned topics already committed to git are safe.
- If you want logs to survive, enable a Render persistent disk and set
  `LEARNING_LOG_PATH` to a path on it, or copy the learning db out
  before each deploy.

## What the loop will never do

- Never push to or merge into `main` on its own. (Owner rules: branch
  only, no merge without the owner's explicit word.)
- Never log passwords, keys, or personal data.
- Never change the tutor persona; the tutor keeps its academy-only
  behavior. Learned topics are for the main persona's general brain only.
- Never touch anything outside this loop's files.

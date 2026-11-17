# CyberLord Artificial Brain

## What it does

The Artificial Brain is a shared orchestration layer used by Dashboard AI, Academy Tutor, and linked WhatsApp/Telegram conversations through the common `/api/ai-assistant` path. It is implemented in `artificial_brain.py`.

- **Request routing hints:** recognises research, image, document, video, audio, creation, planning and general conversation requests. It does not pretend a tool ran merely because a request was classified.
- **Relevant memory retrieval:** selects relevant saved facts, preferences, progress and knowledge from the authenticated user's private memory store.
- **Private answer review:** instructs the selected AI provider to check whether it answered the request, distinguish evidence from inference, identify uncertainty and avoid invented actions or citations.
- **Persona boundaries:** keeps Dashboard AI general-purpose and routes cybersecurity learning to the Academy Tutor; Tutor remains lesson-focused.
- **User-approved knowledge:** Super Mode includes a form that saves up to 1,800 characters per note to the signed-in user's private memory. The note is available to that user's linked channels when they share the account.

## Important technical boundary

This is a software orchestration and retrieval-memory system. It does **not** train or alter Gemini/Groq model weights, autonomously rewrite its own code, or learn private information from every conversation. Users explicitly choose what to save. Secrets are redacted by `user_memory.py`.

## API

`POST /api/brain/teach` (login required) accepts JSON `{ "topic": "...", "note": "..." }`. Notes are private to the authenticated account. The endpoint is rate-limited and returns `model_retrained: false` to make the boundary clear.

## Tests

Run `pytest -q test_artificial_brain.py test_user_memory.py test_super_mode.py`.
